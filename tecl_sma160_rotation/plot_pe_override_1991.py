"""
1991-start simulation: full canonical logic with UVIX/wait_mix replaced by Cash.

Canonical mechanics (identical to simulate_canonical_bb20z_gspc_profit_exit_from_2005.py):
  Base signal:
    GSPC > SMA160                                    → TQQQ
    GSPC < SMA160  AND  drawdown_pct >= ALPHA(94%)   → TQQQ (drawdown re-entry)
    GSPC < SMA160  (while in_reentry)                → TQQQ
    otherwise                                        → wait_mix
  Overlays:
    RSI >= 67.5 AND BB20z >= 1.6  → enter "UVIX" state (here: Cash)
    exit UVIX: RSI <= 66.0  OR  GSPC <= entry_gspc * 1.001 (0.1% profit exit)
    RSI < 30  AND  base == wait_mix  → low_rsi_tqqq_override (TQQQ)
    exit low_rsi: RSI >= 32.5

Substitutions for pre-UVIX / no-TMF-GLD era:
  UVIX   → Cash  (^IRX daily rate, entire sim period)
  wait_mix → Cash  (^IRX daily rate, entire sim period)

P/E z-score override (on top of canonical):
  z36m(SP500 fwd P/E) > 2.0  AND  selected_leg is TQQQ  → Cash

Output: 3-panel plot + numeric summary.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR   = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OHLC_PATH  = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
VAL_PATH   = OUTPUT_DIR / "valuation_forward_pe_daily.csv"

SIM_START      = "1991-01-01"
GSPC_DL_START  = "1987-01-01"   # warmup for SMA160 (160 trading days ≈ 8 months)
IRX_DL_START   = "1988-01-01"

# ── canonical params ──────────────────────────────────────────────────────────
SMA_WINDOW             = 160
ALPHA_DRAWDOWN_PCT     = 100.0  # 94% in canonical but never fires from 2005; use 100 to disable for 1991 (dot-com crash would hit 99.9%)
UVIX_ENTRY_RSI         = 67.5
UVIX_ENTRY_MIN_BB_Z    = 1.6
UVIX_EXIT_RSI          = 66.0
UVIX_GSPC_PROFIT_EXIT  = 0.1    # % GSPC drop from entry triggers UVIX exit
LOW_RSI_ENTRY          = 30.0
LOW_RSI_EXIT           = 32.5
RSI_PERIOD             = 14
BB_WINDOW              = 20

# ── PE filter ─────────────────────────────────────────────────────────────────
Z_WINDOW      = 36
Z_THRESHOLD   = 2.0

TRADING_DAYS  = 252


# ── data loading ──────────────────────────────────────────────────────────────

def _dl(ticker: str, start: str) -> pd.Series:
    raw = yf.download(ticker, start=start, end="2026-05-05",
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.squeeze()


def load_gspc() -> pd.Series:
    return _dl("^GSPC", GSPC_DL_START).rename("GSPC")


def load_irx() -> pd.Series:
    """^IRX annualized % → daily decimal return."""
    return (_dl("^IRX", IRX_DL_START) / 100.0 / TRADING_DAYS).rename("cash_daily")


def load_tqqq_cc() -> pd.Series:
    ohlc = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    return ohlc["TQQQ_CC_RETURN_REBUILT"].rename("tqqq_ret")


def load_valuation() -> pd.DataFrame:
    return pd.read_csv(VAL_PATH, parse_dates=["date"]).set_index("date").sort_index()[["sp500_forward_pe"]]


# ── technical indicators ──────────────────────────────────────────────────────

def rsi_wilder(closes: list[float], open_price: float, period: int = RSI_PERIOD) -> float | None:
    values = closes + [open_price]
    if len(values) <= period:
        return None
    gains, losses = [], []
    for p, c in zip(values, values[1:]):
        d = c - p
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        ag = (ag * (period - 1) + g) / period
        al = (al * (period - 1) + l) / period
    return 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)


def bb20z(prev_closes: list[float], open_price: float) -> float | None:
    window = prev_closes[-BB_WINDOW:]
    if len(window) < BB_WINDOW:
        return None
    mean = sum(window) / len(window)
    var  = sum((v - mean) ** 2 for v in window) / len(window)
    std  = math.sqrt(var)
    return None if std == 0 else (open_price - mean) / std


# ── z-score (monthly → daily, look-ahead safe) ────────────────────────────────

def compute_z_daily(val: pd.DataFrame, daily_idx: pd.DatetimeIndex) -> pd.Series:
    monthly = val["sp500_forward_pe"].resample("MS").first()
    z = (monthly - monthly.rolling(Z_WINDOW).mean()) / monthly.rolling(Z_WINDOW).std(ddof=0)
    z_lag = z.shift(1)
    all_idx = daily_idx.union(z_lag.index).sort_values()
    return z_lag.reindex(all_idx).ffill().reindex(daily_idx)


# ── canonical simulation ───────────────────────────────────────────────────────

def simulate_canonical_no_uvix(
    gspc: pd.Series,
    tqqq_ret: pd.Series,
    cash_ret: pd.Series,
) -> pd.DataFrame:
    """
    Full canonical logic from SIM_START, substituting Cash for UVIX and wait_mix.
    Returns daily DataFrame with columns: selected_leg, strategy_return, strategy_equity.
    """
    # Build sorted daily index from SIM_START
    idx = gspc.index[gspc.index >= SIM_START]
    idx = idx.intersection(tqqq_ret.dropna().index)

    gspc_arr  = gspc.reindex(idx).values
    tqqq_arr  = tqqq_ret.reindex(idx).values
    cash_arr  = cash_ret.reindex(idx).ffill().values

    # Precompute indicators using all GSPC history up to each day
    gspc_full  = gspc.dropna()
    sma160     = gspc_full.rolling(SMA_WINDOW).mean()
    sma160_lag = sma160.shift(1)   # previous close SMA (used at open)

    # Build GSPC feature arrays indexed to idx
    gspc_sma_prev = sma160_lag.reindex(idx).values

    # RSI and BB20z need full history → compute incrementally
    gspc_full_sorted = gspc_full.sort_index()
    gspc_closes: list[float] = []
    # prefill history up to SIM_START
    pre_sim = gspc_full_sorted[gspc_full_sorted.index < SIM_START]
    gspc_closes = list(pre_sim.values)

    # --- main simulation loop ---
    n = len(idx)
    legs     = np.empty(n, dtype=object)
    rets     = np.empty(n, dtype=float)
    equities = np.empty(n, dtype=float)

    tqqq_peak    = 0.0
    in_reentry   = False
    active_cash_uvix  = False      # "UVIX" state → but we hold Cash
    active_low_rsi    = False
    uvix_entry_gspc   = None
    equity            = 1.0

    # seed TQQQ peak from full pre-sim history (canonical uses running peak)
    ohlc = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    pre_tqqq_open = ohlc["TQQQ_OPEN"].dropna()
    pre_tqqq_open = pre_tqqq_open[pre_tqqq_open.index < SIM_START]
    if not pre_tqqq_open.empty:
        tqqq_peak = float(pre_tqqq_open.max())

    # For the daily loop we need TQQQ_OPEN for drawdown tracking
    tqqq_open_ser = ohlc["TQQQ_OPEN"].reindex(idx)

    prev_leg = None

    for i in range(n):
        date       = idx[i]
        gspc_open  = gspc_arr[i]
        sma_prev   = gspc_sma_prev[i]
        tqqq_cc    = tqqq_arr[i]
        cash_daily = cash_arr[i]
        tqqq_open_i = tqqq_open_ser.iloc[i]

        if np.isnan(gspc_open) or np.isnan(sma_prev) or np.isnan(tqqq_cc):
            legs[i] = prev_leg or "cash"
            rets[i] = 0.0
            equity  *= 1.0
            equities[i] = equity
            continue

        # update TQQQ peak
        if not np.isnan(tqqq_open_i):
            tqqq_peak = max(tqqq_peak, float(tqqq_open_i))

        drawdown_pct = (1.0 - float(tqqq_open_i) / tqqq_peak) * 100.0 if (tqqq_peak > 0 and not np.isnan(tqqq_open_i)) else 0.0

        rsi_val = rsi_wilder(gspc_closes, gspc_open)
        z_val   = bb20z(gspc_closes, gspc_open)

        # ── base signal ───────────────────────────────────────────────
        below_sma = gspc_open < sma_prev if not np.isnan(sma_prev) else False
        triggered = below_sma and drawdown_pct >= ALPHA_DRAWDOWN_PCT

        if not below_sma:
            in_reentry = False
            base = "TQQQ"
        elif in_reentry or triggered:
            in_reentry = True
            base = "TQQQ"
        else:
            base = "wait_mix"

        # ── overlays ──────────────────────────────────────────────────
        if active_cash_uvix:
            rsi_exit   = (rsi_val is not None) and rsi_val <= UVIX_EXIT_RSI
            gspc_exit  = (uvix_entry_gspc is not None) and (gspc_open <= uvix_entry_gspc * (1.0 + UVIX_GSPC_PROFIT_EXIT / 100.0))
            if rsi_exit or gspc_exit:
                active_cash_uvix  = False
                uvix_entry_gspc   = None
                selected = base
            else:
                selected = "cash_uvix"   # in UVIX state → Cash
        elif active_low_rsi:
            if (rsi_val is not None) and rsi_val >= LOW_RSI_EXIT:
                active_low_rsi = False
                selected = base
            else:
                selected = "low_rsi_tqqq"
        else:
            if (rsi_val is not None) and rsi_val >= UVIX_ENTRY_RSI:
                if (z_val is not None) and z_val >= UVIX_ENTRY_MIN_BB_Z:
                    active_cash_uvix = True
                    uvix_entry_gspc  = gspc_open
                    selected = "cash_uvix"
                else:
                    selected = base
            elif (rsi_val is not None) and rsi_val < LOW_RSI_ENTRY and base == "wait_mix":
                active_low_rsi = True
                selected = "low_rsi_tqqq"
            else:
                selected = base

        # ── return ────────────────────────────────────────────────────
        is_tqqq = selected in {"TQQQ", "low_rsi_tqqq"}
        ret = tqqq_cc if is_tqqq else cash_daily
        equity *= 1.0 + max(ret, -0.999999)

        legs[i]     = selected
        rets[i]     = ret
        equities[i] = equity

        prev_leg = selected
        # update GSPC close history (use open as proxy since we only have daily OHLC)
        gspc_closes.append(gspc_open)

    df = pd.DataFrame({
        "selected_leg":    legs,
        "strategy_return": rets,
        "strategy_equity": equities,
    }, index=idx)
    return df


# ── metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(equity: pd.Series) -> dict[str, float]:
    r = equity.pct_change().dropna().clip(lower=-0.999999)
    years = len(r) / TRADING_DAYS
    vol   = float(r.std(ddof=0) * np.sqrt(TRADING_DAYS))
    cagr  = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd   = float((equity / equity.cummax() - 1.0).min())
    return {"cagr": cagr, "vol": vol, "mdd": mdd, "cagr_vol": cagr / vol if vol else np.nan}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading data ...")
    gspc     = load_gspc()
    irx      = load_irx()
    tqqq     = load_tqqq_cc()
    val      = load_valuation()

    print("Running canonical simulation (no UVIX, Cash substituted) ...")
    sim = simulate_canonical_no_uvix(gspc, tqqq, irx)

    # PE z-score
    z_daily = compute_z_daily(val, sim.index)

    # Identify TQQQ positions (including low_rsi_tqqq)
    is_tqqq = sim["selected_leg"].isin({"TQQQ", "low_rsi_tqqq"})
    override_mask = is_tqqq & (z_daily > Z_THRESHOLD)

    # Simulate PE-filtered strategy
    irx_aligned = irx.reindex(sim.index).ffill()
    tqqq_aligned = tqqq.reindex(sim.index)

    filt_rets = sim["strategy_return"].copy()
    for d in sim.index[override_mask]:
        filt_rets.loc[d] = float(irx_aligned.loc[d])
    filt_eq = (1 + filt_rets.clip(lower=-0.999999)).cumprod()

    base_eq = sim["strategy_equity"]
    base_m  = compute_metrics(base_eq)
    filt_m  = compute_metrics(filt_eq)

    print(f"\nBaseline (canonical, no PE filter)")
    print(f"  CAGR={base_m['cagr']*100:.2f}%  Vol={base_m['vol']*100:.2f}%  "
          f"MDD={base_m['mdd']*100:.2f}%  CAGR/Vol={base_m['cagr_vol']:.3f}")
    print(f"\nz{Z_WINDOW}m > {Z_THRESHOLD} override (TQQQ→Cash)")
    n_ov = int(override_mask.sum())
    print(f"  Override days={n_ov} ({n_ov/len(sim)*100:.1f}%)")
    print(f"  CAGR={filt_m['cagr']*100:.2f}% ({(filt_m['cagr']-base_m['cagr'])*100:+.2f})  "
          f"Vol={filt_m['vol']*100:.2f}% ({(filt_m['vol']-base_m['vol'])*100:+.2f})  "
          f"MDD={filt_m['mdd']*100:.2f}%  CAGR/Vol={filt_m['cagr_vol']:.3f} "
          f"({filt_m['cagr_vol']-base_m['cagr_vol']:+.3f})")

    # GSPC normalised
    gspc_norm = gspc.reindex(sim.index) / gspc.reindex(sim.index).iloc[0]

    # ── plot ─────────────────────────────────────────────────────────────────
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(20, 13), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2, 1]},
    )
    fig.suptitle(
        f"SP500 fwd P/E z{Z_WINDOW}m > {Z_THRESHOLD} → TQQQ override  |  1991–2026\n"
        f"Canonical (UVIX/wait_mix→Cash) base  +  P/E z-score filter",
        fontsize=13, y=0.99,
    )

    def shade_spans(ax, mask: pd.Series, color: str, alpha: float) -> None:
        in_span = False; start = None
        for d in sim.index:
            if mask.loc[d] and not in_span:
                start = d; in_span = True
            elif not mask.loc[d] and in_span:
                ax.axvspan(start, d, color=color, alpha=alpha, linewidth=0)
                in_span = False
        if in_span:
            ax.axvspan(start, sim.index[-1], color=color, alpha=alpha, linewidth=0)

    # Panel 1: equity curves
    shade_spans(ax1, override_mask,          "#E74C3C", 0.18)
    shade_spans(ax1, is_tqqq & ~override_mask, "#27AE60", 0.07)

    ax1.semilogy(sim.index, base_eq,   color="#2C3E50", lw=1.3, label="Canonical (no PE filter)")
    ax1.semilogy(sim.index, filt_eq,   color="#E74C3C", lw=1.5, linestyle="--",
                 label=f"+ PE z{Z_WINDOW}m > {Z_THRESHOLD} override")
    ax1.semilogy(sim.index, gspc_norm, color="#BDC3C7", lw=0.7, label="GSPC (norm)")

    p1 = [
        mpatches.Patch(color="#E74C3C", alpha=0.45, label="Override active: TQQQ→Cash"),
        mpatches.Patch(color="#27AE60", alpha=0.25, label="TQQQ held"),
    ]
    h1, _ = ax1.get_legend_handles_labels()
    ax1.legend(handles=h1 + p1, fontsize=8, loc="upper left", ncol=2)

    base_txt  = f"CAGR {base_m['cagr']*100:.1f}%  Vol {base_m['vol']*100:.1f}%  MDD {base_m['mdd']*100:.1f}%"
    filt_txt  = f"CAGR {filt_m['cagr']*100:.1f}% ({(filt_m['cagr']-base_m['cagr'])*100:+.1f})  Vol {filt_m['vol']*100:.1f}% ({(filt_m['vol']-base_m['vol'])*100:+.1f})  MDD {filt_m['mdd']*100:.1f}%"
    ax1.set_title(f"Base: {base_txt}\nFiltered: {filt_txt}", fontsize=9)
    ax1.set_ylabel("Equity (log scale)", fontsize=10)
    ax1.grid(axis="y", alpha=0.25)

    # Panel 2: leg indicator
    leg_norm = sim["selected_leg"].map(
        lambda s: "TQQQ" if s in {"TQQQ", "low_rsi_tqqq"} else
                  "cash_uvix" if s == "cash_uvix" else "cash"
    )
    LEG_COLOR = {"TQQQ": "#27AE60", "cash": "#95A5A6", "cash_uvix": "#3498DB"}
    for leg, color in LEG_COLOR.items():
        shade_spans(ax2, leg_norm.eq(leg), color, 0.65)

    ax2.fill_between(sim.index, 0, 1, where=override_mask.values,
                     transform=ax2.get_xaxis_transform(),
                     color="#E74C3C", alpha=0.55, label="PE override→Cash")
    ax2.set_yticks([])
    ax2.set_ylabel("Leg", fontsize=10)
    p2 = [mpatches.Patch(color=c, alpha=0.8, label=l) for l, c in LEG_COLOR.items()]
    p2.append(mpatches.Patch(color="#E74C3C", alpha=0.6, label="PE override→Cash"))
    ax2.legend(handles=p2, fontsize=8, loc="upper left", ncol=4)

    # Panel 3: z-score
    z_plot = z_daily.reindex(sim.index)
    ax3.plot(sim.index, z_plot, color="#8E44AD", lw=0.9, label=f"SP500 fwd P/E z{Z_WINDOW}m")
    ax3.axhline(Z_THRESHOLD, color="#E74C3C", lw=1.2, linestyle="--",
                label=f"+{Z_THRESHOLD}σ threshold")
    ax3.axhline(0, color="#BDC3C7", lw=0.6)
    ax3.fill_between(sim.index, Z_THRESHOLD, z_plot,
                     where=(z_plot > Z_THRESHOLD), color="#E74C3C", alpha=0.20)
    ax3.set_ylabel("Z-score", fontsize=10)
    ax3.set_xlabel("Date", fontsize=9)
    ax3.legend(fontsize=8, loc="upper left")
    ax3.grid(axis="y", alpha=0.25)

    plt.tight_layout()
    out = OUTPUT_DIR / "plot_pe_override_1991.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"\nSaved → {out}")

    # Override period list (z36m)
    print(f"\n=== z{Z_WINDOW}m override periods ===")
    in_run = False; run_start = None; runs = []
    for d in sim.index:
        if override_mask.loc[d] and not in_run:
            run_start = d; in_run = True
        elif not override_mask.loc[d] and in_run:
            runs.append((run_start, d)); in_run = False
    if in_run:
        runs.append((run_start, sim.index[-1]))
    for s, e in runs:
        print(f"  {s.date()} – {e.date()}  ({(e-s).days}d)")

    # Leg composition
    print(f"\n=== Leg composition ===")
    for leg, cnt in sim["selected_leg"].value_counts().items():
        print(f"  {leg:25s}  {cnt:5d}d  ({cnt/len(sim)*100:.1f}%)")


if __name__ == "__main__":
    main()
