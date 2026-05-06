"""
Test: replace price-based TQQQ re-entry with SP500 forward P/E z-score re-entry.

Logic:
  - GSPC < SMA160  →  wait_mix  (unchanged from canonical)
  - While in wait_mix: if SP500 fwd P/E z-score(Wm) < threshold → buy back TQQQ

Scans threshold from -0.25 to -3.0 (step 0.25) for z-windows 18, 24, 36 months.
Finds the threshold that maximises CAGR.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR   = Path(__file__).resolve().parent
REPO_DIR   = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"

CANONICAL_PATHS = {
    "from_20051220": OUTPUT_DIR / (
        "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
        "_low_rsi_tqqq_from_20051220_daily_path.csv"
    ),
    "from_20100212": OUTPUT_DIR / (
        "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
        "_low_rsi_tqqq_from_20100212_daily_path.csv"
    ),
}
VALUATION_PATH   = OUTPUT_DIR / "valuation_forward_pe_daily.csv"
MARKET_PATH      = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
UVIX_PATH        = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"
TRADING_DAYS     = 252

Z_WINDOWS    = [18, 24, 36]
THRESHOLDS   = np.round(np.arange(-0.25, -3.01, -0.25), 2)   # -0.25 … -3.0


# ── helpers ───────────────────────────────────────────────────────────────────

def normalize_leg(s: str) -> str:
    if s in {"TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"}:
        return "TQQQ"
    return "UVIX" if s == "UVIX" else "wait_mix"


def compute_metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.astype(float).clip(lower=-0.999999)
    eq = (1 + r).cumprod()
    years = len(r) / TRADING_DAYS
    vol   = r.std(ddof=0) * np.sqrt(TRADING_DAYS)
    cagr  = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    return {
        "cagr":          cagr,
        "annualized_vol": float(vol),
        "max_drawdown":  float((eq / eq.cummax() - 1.0).min()),
        "cagr_over_vol": cagr / vol if vol else np.nan,
        "final_eq":      float(eq.iloc[-1]),
    }


def simulate(frame: pd.DataFrame, selected: pd.Series) -> dict[str, float]:
    def leg_ret(state: pd.Series, suffix: str) -> pd.Series:
        n    = state.map(normalize_leg)
        wait = 0.5 * frame[f"TMF_{suffix}_RETURN"] + 0.5 * frame[f"GLD_{suffix}_RETURN"]
        return pd.Series(
            np.select(
                [n.eq("UVIX"), n.eq("TQQQ")],
                [frame[f"UVIX_{suffix}_RETURN"], frame[f"TQQQ_{suffix}_RETURN"]],
                default=wait,
            ),
            index=frame.index, dtype=float,
        )
    prev = selected.shift(1); prev.iloc[0] = selected.iloc[0]
    ret  = (1 + leg_ret(prev, "CTO")) * (1 + leg_ret(selected, "OTC")) - 1.0
    return compute_metrics(ret)


def compute_z_daily(val: pd.DataFrame, daily_idx: pd.DatetimeIndex, window: int) -> pd.Series:
    monthly = val["sp500_forward_pe"].resample("MS").first()
    z       = (monthly - monthly.rolling(window).mean()) / monthly.rolling(window).std(ddof=0)
    z_lag   = z.shift(1)   # 1-month look-ahead shift already baked in to daily file
    all_idx = daily_idx.union(z_lag.index).sort_values()
    return z_lag.reindex(all_idx).ffill().reindex(daily_idx)


def load_frame(canon_path: Path, val: pd.DataFrame,
               mkt: pd.DataFrame, uvix: pd.DataFrame) -> pd.DataFrame:
    canon = pd.read_csv(canon_path, parse_dates=["Date"]).set_index("Date").sort_index()
    frame = (
        canon[["selected_leg", "base_target_regime_at_open"]]
        .join(val[["sp500_forward_pe"]], how="inner")
        .join(mkt[["TQQQ_CTO_RETURN", "TQQQ_OTC_RETURN",
                   "TMF_CTO_RETURN",  "TMF_OTC_RETURN",
                   "GLD_CTO_RETURN",  "GLD_OTC_RETURN"]], how="inner")
        .join(uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]], how="inner")
        .dropna(subset=["selected_leg", "TQQQ_CTO_RETURN"])
    )
    return frame


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    val  = pd.read_csv(VALUATION_PATH,  parse_dates=["date"]).set_index("date").sort_index()
    mkt  = pd.read_csv(MARKET_PATH,     parse_dates=["Date"]).set_index("Date")
    uvix = pd.read_csv(UVIX_PATH,       parse_dates=["Date"]).set_index("Date")

    all_rows: list[dict] = []

    for period_label, canon_path in CANONICAL_PATHS.items():
        frame = load_frame(canon_path, val, mkt, uvix)

        # baseline
        base_metrics = simulate(frame, frame["selected_leg"])
        all_rows.append({"period": period_label, "z_window": "baseline",
                          "threshold": np.nan, **base_metrics,
                          "changed_days": 0, "changed_pct": 0.0})

        print(f"\n{'='*70}")
        print(f" {period_label}  baseline: "
              f"CAGR={base_metrics['cagr']*100:.2f}%  "
              f"Vol={base_metrics['annualized_vol']*100:.2f}%  "
              f"MDD={base_metrics['max_drawdown']*100:.2f}%  "
              f"Ratio={base_metrics['cagr_over_vol']:.3f}")
        print(f"{'='*70}")

        for w in Z_WINDOWS:
            z_daily = compute_z_daily(val, frame.index, w)
            is_wait = frame["selected_leg"].map(normalize_leg).eq("wait_mix")

            rows_w: list[dict] = []
            for th in THRESHOLDS:
                mask        = is_wait & (z_daily < th)
                new_sel     = frame["selected_leg"].copy()
                new_sel.loc[mask] = "TQQQ"
                metrics     = simulate(frame, new_sel)
                changed     = int(mask.sum())
                rows_w.append({
                    "period":       period_label,
                    "z_window":     w,
                    "threshold":    float(th),
                    **metrics,
                    "changed_days": changed,
                    "changed_pct":  changed / len(frame),
                })

            df_w = pd.DataFrame(rows_w)
            best = df_w.loc[df_w["cagr"].idxmax()]
            print(f"\n  z{w}m  best threshold={best['threshold']:.2f}  "
                  f"CAGR={best['cagr']*100:.2f}% ({(best['cagr']-base_metrics['cagr'])*100:+.2f})  "
                  f"Vol={best['annualized_vol']*100:.2f}%  "
                  f"MDD={best['max_drawdown']*100:.2f}%  "
                  f"Ratio={best['cagr_over_vol']:.3f}  "
                  f"changed={best['changed_days']}d ({best['changed_pct']*100:.1f}%)")
            all_rows.extend(rows_w)

            # print full table for this window
            print(f"\n  {'th':>6}  {'CAGR':>8}  {'delta':>7}  {'Vol':>8}  "
                  f"{'MDD':>8}  {'Ratio':>6}  {'changed_d':>10}")
            for _, r in df_w.iterrows():
                delta = (r['cagr'] - base_metrics['cagr']) * 100
                marker = " ◀ best" if r['threshold'] == best['threshold'] else ""
                print(f"  {r['threshold']:>6.2f}  "
                      f"{r['cagr']*100:>7.2f}%  "
                      f"{delta:>+7.2f}  "
                      f"{r['annualized_vol']*100:>7.2f}%  "
                      f"{r['max_drawdown']*100:>7.2f}%  "
                      f"{r['cagr_over_vol']:>6.3f}  "
                      f"{r['changed_days']:>6}d ({r['changed_pct']*100:.1f}%)"
                      f"{marker}")

    # save results
    result_df = pd.DataFrame(all_rows)
    out_csv   = OUTPUT_DIR / "pe_zscore_reentry_results.csv"
    result_df.to_csv(out_csv, index=False)
    print(f"\nSaved → {out_csv}")

    # ── plot ──────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), sharey="row")
    fig.suptitle(
        "SP500 fwd P/E z-score re-entry: CAGR & CAGR/Vol vs threshold\n"
        "(when wait_mix AND z-score < threshold → buy back TQQQ)",
        fontsize=12,
    )
    colors_w = {18: "#E74C3C", 24: "#3498DB", 36: "#27AE60"}

    for col_i, period_label in enumerate(CANONICAL_PATHS):
        base_row = result_df[(result_df["period"] == period_label) &
                             (result_df["z_window"] == "baseline")].iloc[0]

        for row_i, metric in enumerate(["cagr", "cagr_over_vol"]):
            ax = axes[row_i][col_i]
            for w in Z_WINDOWS:
                sub = result_df[(result_df["period"] == period_label) &
                                (result_df["z_window"] == w)].sort_values("threshold")
                ax.plot(sub["threshold"], sub[metric] * (100 if metric == "cagr" else 1),
                        color=colors_w[w], marker="o", markersize=4,
                        label=f"z{w}m")
                # mark best
                best_idx = sub[metric].idxmax()
                bv = sub.loc[best_idx, metric] * (100 if metric == "cagr" else 1)
                bt = sub.loc[best_idx, "threshold"]
                ax.scatter([bt], [bv], color=colors_w[w], s=120, zorder=5,
                           edgecolors="black", linewidths=1)

            # baseline
            bv_base = base_row[metric] * (100 if metric == "cagr" else 1)
            ax.axhline(bv_base, color="black", lw=1.2, linestyle="--",
                       label=f"baseline ({bv_base:.2f}{'%' if metric=='cagr' else ''})")
            ax.axvline(-2.0, color="gray", lw=0.8, linestyle=":", alpha=0.6,
                       label="−2.0σ")
            ax.set_title(f"{period_label}\n{metric}", fontsize=10)
            ax.set_xlabel("z-score threshold", fontsize=9)
            ax.set_ylabel("CAGR (%)" if metric == "cagr" else "CAGR/Vol", fontsize=9)
            ax.invert_xaxis()
            ax.legend(fontsize=7.5)
            ax.grid(alpha=0.3)

    plt.tight_layout()
    out_png = OUTPUT_DIR / "pe_zscore_reentry_plot.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Saved → {out_png}")


if __name__ == "__main__":
    main()
