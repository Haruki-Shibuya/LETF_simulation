"""
PE override period visualization.

Shows TQQQ price + strategy equity curves with background shading where
the SP500 forward P/E 24-month z-score > 2.0 filter overrides the canonical
TQQQ position to wait_mix.  Background color = original canonical leg.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# ── config ────────────────────────────────────────────────────────────────────
Z_THRESHOLD   = 2.0
Z_WINDOW      = 24   # months
PERIOD_LABEL  = "from_20051220"
CANONICAL_PATH = OUTPUT_DIR / (
    "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
    "_low_rsi_tqqq_from_20051220_daily_path.csv"
)
OUT_PNG = OUTPUT_DIR / "plot_pe_override_periods_2005.png"

LEG_COLOR = {
    "TQQQ":      "#E74C3C",   # red   – TQQQ overridden to wait
    "UVIX":      "#3498DB",   # blue  – UVIX (not affected)
    "wait_mix":  "#95A5A6",   # gray  – wait (not affected)
}
LEG_ALPHA = 0.25   # background transparency


def normalize_leg(s: str) -> str:
    if s in {"TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"}:
        return "TQQQ"
    if s == "UVIX":
        return "UVIX"
    return "wait_mix"


def compute_z24_daily(valuation: pd.DataFrame, daily_index: pd.DatetimeIndex) -> pd.Series:
    """SP500 forward P/E 24-month rolling z-score, forward-filled to daily."""
    monthly = valuation["sp500_forward_pe"].resample("MS").first()
    z = (monthly - monthly.rolling(Z_WINDOW).mean()) / monthly.rolling(Z_WINDOW).std(ddof=0)
    # shift 1 month so month M's z-score first applies from month M+1 (no look-ahead)
    z_lag = z.shift(1)
    all_idx = daily_index.union(z_lag.index).sort_values()
    return z_lag.reindex(all_idx).ffill().reindex(daily_index)


def simulate_returns(frame: pd.DataFrame, selected: pd.Series) -> pd.Series:
    """Daily strategy return given selected leg series."""
    def leg_ret(state: pd.Series, suffix: str) -> pd.Series:
        n = state.map(normalize_leg)
        wait = 0.5 * frame["TMF_CTO_RETURN"] + 0.5 * frame["GLD_CTO_RETURN"] if suffix == "CTO" \
               else 0.5 * frame["TMF_OTC_RETURN"] + 0.5 * frame["GLD_OTC_RETURN"]
        return pd.Series(
            np.select(
                [n.eq("UVIX"), n.eq("TQQQ")],
                [frame[f"UVIX_{suffix}_RETURN"], frame[f"TQQQ_{suffix}_RETURN"]],
                default=wait,
            ),
            index=frame.index, dtype=float,
        )
    prev = selected.shift(1)
    prev.iloc[0] = selected.iloc[0]
    return (1.0 + leg_ret(prev, "CTO")) * (1.0 + leg_ret(selected, "OTC")) - 1.0


def shade_spans(ax, dates: pd.DatetimeIndex, mask: pd.Series,
                color: str, alpha: float, label: str | None = None) -> None:
    """Shade contiguous True-runs in mask on ax."""
    in_span = False
    start = None
    dated = sorted(set(dates))
    for i, d in enumerate(dates):
        if mask.loc[d] and not in_span:
            start = d
            in_span = True
        elif not mask.loc[d] and in_span:
            ax.axvspan(start, d, color=color, alpha=alpha, linewidth=0)
            in_span = False
    if in_span:
        ax.axvspan(start, dates[-1], color=color, alpha=alpha, linewidth=0)


def main() -> None:
    # ── load ─────────────────────────────────────────────────────────────────
    canon = pd.read_csv(CANONICAL_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    val   = pd.read_csv(OUTPUT_DIR / "valuation_forward_pe_daily.csv",
                        parse_dates=["date"]).set_index("date").sort_index()
    mkt   = pd.read_csv(OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv",
                        parse_dates=["Date"]).set_index("Date")
    uvix  = pd.read_csv(
        BASE_DIR.parent / "uvix_backtest" / "output" / "uvix_ohlc_series.csv",
        parse_dates=["Date"]
    ).set_index("Date")

    # join to common index
    frame = (
        canon[["selected_leg", "base_target_regime_at_open", "strategy_equity"]]
        .join(val[["sp500_forward_pe"]], how="inner")
        .join(mkt[["TQQQ_CLOSE", "TQQQ_CTO_RETURN", "TQQQ_OTC_RETURN",
                   "TMF_CTO_RETURN", "TMF_OTC_RETURN",
                   "GLD_CTO_RETURN", "GLD_OTC_RETURN"]], how="inner")
        .join(uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]], how="inner")
        .dropna(subset=["selected_leg", "TQQQ_CTO_RETURN"])
    )

    # ── compute z-score & apply filter ───────────────────────────────────────
    z24 = compute_z24_daily(val, frame.index)
    orig_leg = frame["selected_leg"].map(normalize_leg)
    is_tqqq   = orig_leg.eq("TQQQ")
    is_high_z = z24 > Z_THRESHOLD

    # filter: TQQQ → wait_mix when z24 > 2.0
    filtered_leg = frame["selected_leg"].copy()
    override_mask = is_tqqq & is_high_z
    filtered_leg.loc[override_mask] = "wait_mix"

    # equity curves
    base_ret     = simulate_returns(frame, frame["selected_leg"])
    filtered_ret = simulate_returns(frame, filtered_leg)
    base_eq     = (1 + base_ret.clip(lower=-0.999999)).cumprod()
    filtered_eq = (1 + filtered_ret.clip(lower=-0.999999)).cumprod()

    # TQQQ price normalised to 1 at start
    tqqq_norm = frame["TQQQ_CLOSE"] / frame["TQQQ_CLOSE"].iloc[0]

    # ── plot ─────────────────────────────────────────────────────────────────
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(18, 12), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2, 1]},
    )
    fig.suptitle(
        f"SP500 Forward P/E Z-score({Z_WINDOW}m) > {Z_THRESHOLD} → TQQQ override period analysis\n"
        f"Period: {frame.index[0].date()} – {frame.index[-1].date()}",
        fontsize=13, y=0.98,
    )

    # ── Panel 1: equity curves ────────────────────────────────────────────────
    # shade background by original leg (only where filter is active)
    for leg in ["TQQQ", "UVIX", "wait_mix"]:
        span_mask = is_high_z & orig_leg.eq(leg)
        if span_mask.any():
            shade_spans(ax1, frame.index, span_mask,
                        color=LEG_COLOR[leg], alpha=LEG_ALPHA)

    ax1.semilogy(frame.index, base_eq,     color="#2C3E50", lw=1.4,
                 label="Canonical (no PE filter)", zorder=3)
    ax1.semilogy(frame.index, filtered_eq, color="#27AE60", lw=1.4,
                 linestyle="--", label=f"PE z{Z_WINDOW}m > {Z_THRESHOLD} override", zorder=3)
    ax1.semilogy(frame.index, tqqq_norm,   color="#BDC3C7", lw=0.8,
                 label="TQQQ price (normalised)", zorder=2)

    # legend for background colors
    patches = [
        mpatches.Patch(color=LEG_COLOR["TQQQ"],     alpha=0.6, label="Override active | orig=TQQQ → switched to wait"),
        mpatches.Patch(color=LEG_COLOR["UVIX"],     alpha=0.6, label="Override active | orig=UVIX (no change)"),
        mpatches.Patch(color=LEG_COLOR["wait_mix"], alpha=0.6, label="Override active | orig=wait_mix (no change)"),
    ]
    line_handles, _ = ax1.get_legend_handles_labels()
    ax1.legend(handles=line_handles + patches, loc="upper left", fontsize=8.5, ncol=2)
    ax1.set_ylabel("Equity (log scale)", fontsize=10)
    ax1.grid(axis="y", alpha=0.3)

    # ── Panel 2: original canonical leg over time ─────────────────────────────
    for leg, color in LEG_COLOR.items():
        mask = orig_leg.eq(leg)
        shade_spans(ax2, frame.index, mask, color=color, alpha=0.7)

    # highlight overridden days with a thick bar
    ax2.fill_between(frame.index, 0, 1,
                     where=override_mask.values, transform=ax2.get_xaxis_transform(),
                     color="black", alpha=0.35, label="Overridden (TQQQ→wait)")

    ax2.set_yticks([])
    ax2.set_ylabel("Canonical leg", fontsize=10)
    leg2_patches = [mpatches.Patch(color=c, alpha=0.8, label=l)
                    for l, c in LEG_COLOR.items()]
    leg2_patches.append(mpatches.Patch(color="black", alpha=0.4, label="Overridden (→wait)"))
    ax2.legend(handles=leg2_patches, loc="upper left", fontsize=8.5, ncol=4)

    # ── Panel 3: SP500 P/E z-score ────────────────────────────────────────────
    ax3.plot(frame.index, z24.reindex(frame.index), color="#8E44AD", lw=1.0, label=f"SP500 fwd P/E z{Z_WINDOW}m")
    ax3.axhline(Z_THRESHOLD, color="#E74C3C", lw=1.2, linestyle="--", label=f"Threshold {Z_THRESHOLD}σ")
    ax3.axhline(0, color="#BDC3C7", lw=0.7)
    ax3.fill_between(frame.index, Z_THRESHOLD, z24.reindex(frame.index),
                     where=(z24.reindex(frame.index) > Z_THRESHOLD),
                     color="#E74C3C", alpha=0.20)
    ax3.set_ylabel("Z-score", fontsize=10)
    ax3.legend(loc="upper left", fontsize=8.5)
    ax3.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Saved → {OUT_PNG}")

    # ── summary stats ─────────────────────────────────────────────────────────
    n_override = int(override_mask.sum())
    n_total    = len(frame)
    print(f"\nOverride days: {n_override} / {n_total} ({n_override/n_total*100:.1f}%)")
    print("\nOverride periods (contiguous runs):")
    in_run, run_start = False, None
    runs = []
    for d in frame.index:
        if override_mask.loc[d] and not in_run:
            run_start = d; in_run = True
        elif not override_mask.loc[d] and in_run:
            runs.append((run_start, d))
            in_run = False
    if in_run:
        runs.append((run_start, frame.index[-1]))
    for s, e in runs:
        print(f"  {s.date()} – {e.date()}  ({(e - s).days} days)")


if __name__ == "__main__":
    main()
