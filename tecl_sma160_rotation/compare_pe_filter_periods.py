"""
Comparison table: baseline vs SP500 fwd P/E z-score filter across three periods.

  Pre-2005  (1991-01-01 – 2005-12-19) : synthetic canonical (UVIX→Cash, wait_mix→Cash)
  Post-2005 (2005-12-20 – latest)     : actual canonical CSV
  Full      (1991-01-01 – latest)     : pre-2005 synthetic stitched to post-2005 actual

Filter tested: z-score(SP500 fwd P/E, W months) > 2.0 → override TQQQ to Cash/wait_mix.
Windows W = 18, 24, 36 months.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR   = Path(__file__).resolve().parent
REPO_DIR   = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
OHLC_PATH  = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
VAL_PATH   = OUTPUT_DIR / "valuation_forward_pe_daily.csv"
UVIX_PATH  = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"
CANON_PATH = OUTPUT_DIR / (
    "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
    "_low_rsi_tqqq_from_20051220_daily_path.csv"
)

CANON_START    = "2005-12-20"
SIM_START      = "1991-01-01"
GSPC_DL_START  = "1987-01-01"
IRX_DL_START   = "1988-01-01"

SMA_WINDOW          = 160
ALPHA_DRAWDOWN_PCT  = 100.0   # effectively disabled (dot-com crash hits 99.9%)
UVIX_ENTRY_RSI      = 67.5
UVIX_ENTRY_MIN_BB_Z = 1.6
UVIX_EXIT_RSI       = 66.0
UVIX_GSPC_PROFIT    = 0.1     # % drop from UVIX entry gspc → exit
LOW_RSI_ENTRY       = 30.0
LOW_RSI_EXIT        = 32.5
RSI_PERIOD          = 14
BB_WINDOW           = 20
TRADING_DAYS        = 252

Z_WINDOWS   = [18, 24, 36]
Z_THRESHOLD = 2.0


# ── helpers ───────────────────────────────────────────────────────────────────

def _dl(ticker: str, start: str) -> pd.Series:
    raw = yf.download(ticker, start=start, end="2026-05-05",
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.squeeze()


def compute_metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.astype(float).clip(lower=-0.999999)
    eq = (1 + r).cumprod()
    years = len(r) / TRADING_DAYS
    vol   = float(r.std(ddof=0) * np.sqrt(TRADING_DAYS))
    cagr  = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    mdd   = float((eq / eq.cummax() - 1.0).min())
    return {"cagr": cagr, "vol": vol, "mdd": mdd, "cagr_vol": cagr / vol if vol else np.nan}


def compute_z_daily(val: pd.DataFrame, daily_idx: pd.DatetimeIndex, window: int) -> pd.Series:
    monthly = val["sp500_forward_pe"].resample("MS").first()
    z = (monthly - monthly.rolling(window).mean()) / monthly.rolling(window).std(ddof=0)
    z_lag = z.shift(1)
    all_idx = daily_idx.union(z_lag.index).sort_values()
    return z_lag.reindex(all_idx).ffill().reindex(daily_idx)


# ── canonical indicators ──────────────────────────────────────────────────────

def rsi_wilder(closes: list[float], open_price: float, period: int = RSI_PERIOD) -> float | None:
    values = closes + [open_price]
    if len(values) <= period:
        return None
    gains, losses = [], []
    for p, c in zip(values, values[1:]):
        d = c - p
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
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


# ── pre-2005 synthetic simulation ─────────────────────────────────────────────

def simulate_pre2005(
    gspc: pd.Series,
    tqqq_cc: pd.Series,
    irx: pd.Series,
    end_excl: str = CANON_START,
) -> pd.DataFrame:
    """
    Full canonical logic (no UVIX) from SIM_START to end_excl.
    Returns: selected_leg, strategy_return
    """
    ohlc = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()

    idx = (
        gspc.index[gspc.index >= SIM_START]
        .intersection(tqqq_cc.dropna().index)
    )
    idx = idx[idx < end_excl]

    sma160     = gspc.rolling(SMA_WINDOW).mean().shift(1)   # prev-close SMA
    tqqq_open  = ohlc["TQQQ_OPEN"]

    # seed TQQQ peak from full history before SIM_START
    pre = tqqq_open.dropna()
    pre = pre[pre.index < SIM_START]
    tqqq_peak = float(pre.max()) if not pre.empty else 0.0

    # prepopulate GSPC closes before sim start
    pre_gspc = gspc.dropna()
    pre_gspc = pre_gspc[pre_gspc.index < SIM_START]
    gspc_closes: list[float] = list(pre_gspc.values)

    legs, rets = [], []
    in_reentry = False
    active_cash_uvix = False
    active_low_rsi   = False
    uvix_entry_gspc  = None
    prev_leg = None

    for d in idx:
        gspc_open  = float(gspc.loc[d])
        sma_prev   = float(sma160.loc[d]) if not np.isnan(sma160.loc[d]) else None
        tqqq_r     = float(tqqq_cc.loc[d]) if not np.isnan(tqqq_cc.loc[d]) else 0.0
        cash_r     = float(irx.reindex([d]).ffill().iloc[0]) if d in irx.index or True else 0.0
        cash_r     = float(irx.ffill().reindex([d]).iloc[0]) if not np.isnan(irx.reindex([d]).ffill().iloc[0]) else 0.0
        to         = tqqq_open.get(d, np.nan)

        if not np.isnan(to):
            tqqq_peak = max(tqqq_peak, float(to))

        drawdown_pct = (1 - float(to) / tqqq_peak) * 100 if (tqqq_peak > 0 and not np.isnan(to)) else 0.0

        rsi_v = rsi_wilder(gspc_closes, gspc_open)
        z_v   = bb20z(gspc_closes, gspc_open)

        # base signal
        below_sma = (sma_prev is not None) and (gspc_open < sma_prev)
        triggered = below_sma and drawdown_pct >= ALPHA_DRAWDOWN_PCT

        if not below_sma:
            in_reentry = False; base = "TQQQ"
        elif in_reentry or triggered:
            in_reentry = True; base = "TQQQ"
        else:
            base = "wait_mix"

        # overlays
        if active_cash_uvix:
            rsi_exit  = (rsi_v is not None) and rsi_v <= UVIX_EXIT_RSI
            gspc_exit = (uvix_entry_gspc is not None) and (gspc_open <= uvix_entry_gspc * (1 + UVIX_GSPC_PROFIT / 100))
            if rsi_exit or gspc_exit:
                active_cash_uvix = False; uvix_entry_gspc = None; selected = base
            else:
                selected = "cash_uvix"
        elif active_low_rsi:
            if (rsi_v is not None) and rsi_v >= LOW_RSI_EXIT:
                active_low_rsi = False; selected = base
            else:
                selected = "low_rsi_tqqq"
        else:
            if (rsi_v is not None) and rsi_v >= UVIX_ENTRY_RSI:
                if (z_v is not None) and z_v >= UVIX_ENTRY_MIN_BB_Z:
                    active_cash_uvix = True; uvix_entry_gspc = gspc_open; selected = "cash_uvix"
                else:
                    selected = base
            elif (rsi_v is not None) and rsi_v < LOW_RSI_ENTRY and base == "wait_mix":
                active_low_rsi = True; selected = "low_rsi_tqqq"
            else:
                selected = base

        is_tqqq = selected in {"TQQQ", "low_rsi_tqqq"}
        legs.append(selected)
        rets.append(tqqq_r if is_tqqq else cash_r)

        prev_leg = selected
        gspc_closes.append(gspc_open)

    return pd.DataFrame({"selected_leg": legs, "strategy_return": rets}, index=idx)


# ── post-2005 from canonical CSV ──────────────────────────────────────────────

def load_post2005() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (frame with returns, canon with selected_leg)."""
    canon = pd.read_csv(CANON_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    ohlc  = pd.read_csv(OHLC_PATH,  parse_dates=["Date"]).set_index("Date")
    uvix  = pd.read_csv(UVIX_PATH,  parse_dates=["Date"]).set_index("Date")

    frame = (
        canon[["selected_leg"]]
        .join(ohlc[["TQQQ_CTO_RETURN","TQQQ_OTC_RETURN",
                    "TMF_CTO_RETURN","TMF_OTC_RETURN",
                    "GLD_CTO_RETURN","GLD_OTC_RETURN"]], how="inner")
        .join(uvix[["UVIX_CTO_RETURN","UVIX_OTC_RETURN"]], how="inner")
        .dropna(subset=["selected_leg","TQQQ_CTO_RETURN"])
    )
    return frame, canon


def normalize_leg(s: str) -> str:
    if s in {"TQQQ","low_rsi_tqqq_override","low_rsi_tqqq_priority"}:
        return "TQQQ"
    return "UVIX" if s == "UVIX" else "wait_mix"


def post2005_returns(frame: pd.DataFrame, selected: pd.Series) -> pd.Series:
    def leg_ret(state: pd.Series, suf: str) -> pd.Series:
        n    = state.map(normalize_leg)
        wait = 0.5 * frame[f"TMF_{suf}_RETURN"] + 0.5 * frame[f"GLD_{suf}_RETURN"]
        return pd.Series(
            np.select([n.eq("UVIX"), n.eq("TQQQ")],
                      [frame[f"UVIX_{suf}_RETURN"], frame[f"TQQQ_{suf}_RETURN"]],
                      default=wait),
            index=frame.index, dtype=float,
        )
    prev = selected.shift(1); prev.iloc[0] = selected.iloc[0]
    return (1 + leg_ret(prev,"CTO")) * (1 + leg_ret(selected,"OTC")) - 1.0


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Downloading market data ...")
    gspc = _dl("^GSPC", GSPC_DL_START).rename("GSPC")
    irx  = (_dl("^IRX", IRX_DL_START) / 100.0 / TRADING_DAYS).rename("cash")
    ohlc = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    tqqq_cc = ohlc["TQQQ_CC_RETURN_REBUILT"].rename("tqqq_cc")
    val  = pd.read_csv(VAL_PATH, parse_dates=["date"]).set_index("date").sort_index()[["sp500_forward_pe"]]

    print("Simulating pre-2005 synthetic canonical ...")
    pre = simulate_pre2005(gspc, tqqq_cc, irx)

    print("Loading post-2005 actual canonical ...")
    post_frame, post_canon = load_post2005()

    # ── build rows for comparison table ──────────────────────────────────────
    rows: list[dict] = []

    def add_row(label: str, period: str, variant: str, rets: pd.Series) -> None:
        m = compute_metrics(rets)
        rows.append({
            "period":   period,
            "variant":  variant,
            "CAGR%":    round(m["cagr"] * 100, 2),
            "Vol%":     round(m["vol"]  * 100, 2),
            "MDD%":     round(m["mdd"]  * 100, 2),
            "CAGR/Vol": round(m["cagr_vol"], 3),
            "days":     len(rets),
        })

    # ── Pre-2005 section ──────────────────────────────────────────────────────
    pre_ret_base = pd.Series(pre["strategy_return"].values, index=pre.index, dtype=float)
    add_row("pre2005_baseline", "Pre-2005\n(1991–2005-12-19)", "Baseline (synthetic canonical)", pre_ret_base)

    for w in Z_WINDOWS:
        z = compute_z_daily(val, pre.index, w)
        is_tqqq = pre["selected_leg"].isin({"TQQQ","low_rsi_tqqq"})
        override = is_tqqq & (z > Z_THRESHOLD)
        irx_aligned = irx.reindex(pre.index).ffill()
        filt_ret = pre_ret_base.copy()
        # for overridden days, replace with cash return
        cash_cc = ohlc["TQQQ_CC_RETURN_REBUILT"].copy()   # just for alignment
        for d in pre.index[override]:
            filt_ret.loc[d] = float(irx_aligned.loc[d])
        add_row(f"pre2005_z{w}", "Pre-2005\n(1991–2005-12-19)", f"z{w}m>{Z_THRESHOLD}σ → Cash", filt_ret)

    # ── Post-2005 section ─────────────────────────────────────────────────────
    post_ret_base = post2005_returns(post_frame, post_frame["selected_leg"])
    add_row("post2005_baseline", "Post-2005\n(2005-12-20–)", "Baseline (actual canonical)", post_ret_base)

    for w in Z_WINDOWS:
        z = compute_z_daily(val, post_frame.index, w)
        is_tqqq = post_frame["selected_leg"].map(normalize_leg).eq("TQQQ")
        override = is_tqqq & (z > Z_THRESHOLD)
        filt_leg = post_frame["selected_leg"].copy()
        filt_leg.loc[override] = "wait_mix"
        filt_ret = post2005_returns(post_frame, filt_leg)
        add_row(f"post2005_z{w}", "Post-2005\n(2005-12-20–)", f"z{w}m>{Z_THRESHOLD}σ → wait_mix", filt_ret)

    # ── Full period (stitched) ─────────────────────────────────────────────────
    # pre-2005 uses CC return; post-2005 uses CTO+OTC → concatenate return series
    full_base = pd.concat([pre_ret_base, post_ret_base]).sort_index()
    full_base = full_base[~full_base.index.duplicated(keep="last")]
    add_row("full_baseline", "Full period\n(1991–)", "Baseline (stitched)", full_base)

    for w in Z_WINDOWS:
        # pre portion
        z_pre = compute_z_daily(val, pre.index, w)
        is_tqqq_pre = pre["selected_leg"].isin({"TQQQ","low_rsi_tqqq"})
        ov_pre = is_tqqq_pre & (z_pre > Z_THRESHOLD)
        irx_pre = irx.reindex(pre.index).ffill()
        filt_pre = pre_ret_base.copy()
        for d in pre.index[ov_pre]:
            filt_pre.loc[d] = float(irx_pre.loc[d])

        # post portion
        z_post = compute_z_daily(val, post_frame.index, w)
        is_tqqq_post = post_frame["selected_leg"].map(normalize_leg).eq("TQQQ")
        ov_post = is_tqqq_post & (z_post > Z_THRESHOLD)
        filt_post_leg = post_frame["selected_leg"].copy()
        filt_post_leg.loc[ov_post] = "wait_mix"
        filt_post = post2005_returns(post_frame, filt_post_leg)

        full_filt = pd.concat([filt_pre, filt_post]).sort_index()
        full_filt = full_filt[~full_filt.index.duplicated(keep="last")]
        add_row(f"full_z{w}", "Full period\n(1991–)", f"z{w}m>{Z_THRESHOLD}σ → Cash/wait_mix", full_filt)

    # ── Print table ───────────────────────────────────────────────────────────
    df = pd.DataFrame(rows).drop(columns=["label"] if "label" in rows[0] else [])

    for period_key, grp in [
        ("Pre-2005",    [r for r in rows if "Pre-2005"    in r["period"]]),
        ("Post-2005",   [r for r in rows if "Post-2005"   in r["period"]]),
        ("Full period", [r for r in rows if "Full period" in r["period"]]),
    ]:
        print(f"\n{'='*75}")
        print(f"  {period_key}")
        print(f"{'='*75}")
        print(f"  {'Variant':<38} {'CAGR%':>7} {'Vol%':>7} {'MDD%':>8} {'CAGR/Vol':>9} {'Days':>6}")
        print(f"  {'-'*75}")
        for r in grp:
            delta_cagr = ""
            delta_vol  = ""
            if r["variant"] != grp[0]["variant"]:
                dc = r["CAGR%"] - grp[0]["CAGR%"]
                dv = r["Vol%"]  - grp[0]["Vol%"]
                delta_cagr = f"({dc:+.2f})"
                delta_vol  = f"({dv:+.2f})"
            print(f"  {r['variant']:<38} {r['CAGR%']:>7.2f} {delta_cagr:>8}  "
                  f"{r['Vol%']:>7.2f} {delta_vol:>8}  "
                  f"{r['MDD%']:>7.2f}  {r['CAGR/Vol']:>8.3f}  {r['days']:>6}")

    # Save CSV
    out = OUTPUT_DIR / "pe_filter_period_comparison.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
