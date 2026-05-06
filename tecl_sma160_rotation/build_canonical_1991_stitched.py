"""
Build 1991 stitched canonical daily-path and summary CSVs.

Output files (in output/):
  canonical_stitched_1991_daily_path.csv
  canonical_stitched_1991_summary.csv

Series construction:
  1991-01-02 – 2005-12-19  : Synthetic canonical
      Full canonical logic (SMA160, BB20z, RSI overlays, drawdown alpha=100 disabled)
      UVIX → Cash (^IRX daily rate)
      wait_mix → Cash (^IRX)
      TQQQ → TQQQ_CC_RETURN_REBUILT synthetic returns
  2005-12-20 – end         : Actual canonical (from_20051220 CSV), columns copied directly.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ── paths ──────────────────────────────────────────────────────────────────────
HERE      = Path(__file__).resolve().parent
OUT_DIR   = HERE / "output"
OHLC_PATH = OUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
CANON_2005_PATH = OUT_DIR / (
    "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
    "_low_rsi_tqqq_from_20051220_daily_path.csv"
)
OUT_DAILY   = OUT_DIR / "canonical_stitched_1991_daily_path.csv"
OUT_SUMMARY = OUT_DIR / "canonical_stitched_1991_summary.csv"

# ── constants ──────────────────────────────────────────────────────────────────
SIM_START           = "1991-01-01"
CANON_START         = "2005-12-20"   # first day of actual canonical
GSPC_DL_START       = "1987-01-01"
IRX_DL_START        = "1988-01-01"
SMA_WINDOW          = 160
ALPHA_DRAWDOWN_PCT  = 100.0          # disabled (dot-com crash ≈ 99.9% dd would fire at 94%)
UVIX_ENTRY_RSI      = 67.5
UVIX_ENTRY_MIN_BB_Z = 1.6
UVIX_EXIT_RSI       = 66.0
UVIX_GSPC_PROFIT    = 0.1            # % drop from UVIX-entry GSPC → exit
LOW_RSI_ENTRY       = 30.0
LOW_RSI_EXIT        = 32.5
RSI_PERIOD          = 14
BB_WINDOW           = 20
TRADING_DAYS        = 252

DAILY_PATH_COLS = [
    "Date", "gspc_open_implied_rsi14", "GSPC_BB20_Z", "GSPC_OPEN",
    "GSPC_SMA160_PREV_CLOSE", "TQQQ_OPEN", "TQQQ_PEAK_OPEN",
    "TQQQ_RUNNING_DRAWDOWN_PCT", "DRAWDOWN_ALPHA_PCT",
    "signal_below_sma", "drawdown_trigger", "base_target_regime_at_open",
    "selected_leg", "action", "skip_reason", "strategy_return", "strategy_equity",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def _dl(ticker: str, start: str) -> pd.Series:
    raw = yf.download(ticker, start=start, end="2026-05-10",
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.squeeze()


def rsi_wilder(closes: list[float], open_price: float) -> float | None:
    values = closes + [open_price]
    if len(values) <= RSI_PERIOD:
        return None
    gains, losses = [], []
    for p, c in zip(values, values[1:]):
        d = c - p
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    al = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    for g, l in zip(gains[RSI_PERIOD:], losses[RSI_PERIOD:]):
        ag = (ag * (RSI_PERIOD - 1) + g) / RSI_PERIOD
        al = (al * (RSI_PERIOD - 1) + l) / RSI_PERIOD
    return 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)


def bb20z(prev_closes: list[float], open_price: float) -> float | None:
    window = prev_closes[-BB_WINDOW:]
    if len(window) < BB_WINDOW:
        return None
    mean = sum(window) / len(window)
    std  = math.sqrt(sum((v - mean) ** 2 for v in window) / len(window))
    return None if std == 0 else (open_price - mean) / std


# ── pre-2005 simulation ────────────────────────────────────────────────────────

def simulate_pre2005(
    gspc: pd.Series,
    tqqq_cc: pd.Series,
    irx: pd.Series,
) -> list[dict]:
    ohlc      = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    tqqq_open = ohlc["TQQQ_OPEN"]

    idx = (
        gspc.index[gspc.index >= SIM_START]
        .intersection(tqqq_cc.dropna().index)
    )
    idx = idx[idx < CANON_START]

    sma160_lag = gspc.rolling(SMA_WINDOW).mean().shift(1)

    # seed TQQQ peak from history before SIM_START
    pre_open   = tqqq_open.dropna()
    pre_open   = pre_open[pre_open.index < SIM_START]
    tqqq_peak  = float(pre_open.max()) if not pre_open.empty else 0.0

    # pre-populate GSPC close history
    pre_gspc      = gspc.dropna()
    gspc_closes: list[float] = list(pre_gspc[pre_gspc.index < SIM_START].values)

    irx_ff = irx.reindex(idx).ffill()

    rows: list[dict] = []
    in_reentry       = False
    active_cash_uvix = False
    active_low_rsi   = False
    uvix_entry_gspc  = None
    equity           = 1.0

    cash_uvix_entries   = 0
    cash_uvix_exits     = 0
    cash_uvix_rsi_exits = 0
    cash_uvix_gspc_exits= 0
    low_rsi_entries     = 0
    low_rsi_exits       = 0

    for d in idx:
        gspc_open = float(gspc.loc[d])
        sma_prev  = sma160_lag.loc[d]
        tqqq_r    = float(tqqq_cc.loc[d])
        cash_r    = float(irx_ff.loc[d]) if not np.isnan(irx_ff.loc[d]) else 0.0
        to        = tqqq_open.get(d, np.nan)
        to_val    = float(to) if (not isinstance(to, float) or not np.isnan(to)) else np.nan

        if not np.isnan(to_val):
            tqqq_peak = max(tqqq_peak, to_val)

        drawdown_pct = (
            (1 - to_val / tqqq_peak) * 100
            if (tqqq_peak > 0 and not np.isnan(to_val))
            else 0.0
        )

        rsi_v = rsi_wilder(gspc_closes, gspc_open)
        z_v   = bb20z(gspc_closes, gspc_open)

        below_sma  = (not np.isnan(float(sma_prev))) and (gspc_open < float(sma_prev))
        triggered  = below_sma and (drawdown_pct >= ALPHA_DRAWDOWN_PCT)

        if not below_sma:
            in_reentry = False
            base = "TQQQ"
        elif in_reentry or triggered:
            in_reentry = True
            base = "TQQQ"
        else:
            base = "wait_mix"

        action = ""
        prev_cash_uvix = active_cash_uvix
        prev_low_rsi   = active_low_rsi

        if active_cash_uvix:
            rsi_exit  = (rsi_v is not None) and rsi_v <= UVIX_EXIT_RSI
            gspc_exit = (uvix_entry_gspc is not None) and (
                gspc_open <= uvix_entry_gspc * (1 + UVIX_GSPC_PROFIT / 100)
            )
            if rsi_exit or gspc_exit:
                active_cash_uvix = False
                uvix_entry_gspc  = None
                selected         = base
                action           = "exit_cash_uvix_rsi" if rsi_exit else "exit_cash_uvix_gspc_profit"
                cash_uvix_exits += 1
                if rsi_exit:
                    cash_uvix_rsi_exits += 1
                if gspc_exit:
                    cash_uvix_gspc_exits += 1
            else:
                selected = "cash_uvix"
        elif active_low_rsi:
            if (rsi_v is not None) and rsi_v >= LOW_RSI_EXIT:
                active_low_rsi = False
                selected       = base
                action         = "exit_low_rsi_tqqq"
                low_rsi_exits += 1
            else:
                selected = "low_rsi_tqqq"
        else:
            if (rsi_v is not None) and rsi_v >= UVIX_ENTRY_RSI:
                if (z_v is not None) and z_v >= UVIX_ENTRY_MIN_BB_Z:
                    active_cash_uvix = True
                    uvix_entry_gspc  = gspc_open
                    selected         = "cash_uvix"
                    action           = "enter_cash_uvix_high_rsi_bb20z"
                    cash_uvix_entries += 1
                else:
                    selected = base
            elif (rsi_v is not None) and rsi_v < LOW_RSI_ENTRY and base == "wait_mix":
                active_low_rsi = True
                selected       = "low_rsi_tqqq"
                action         = "enter_low_rsi_tqqq"
                low_rsi_entries += 1
            else:
                selected = base

        is_tqqq = selected in {"TQQQ", "low_rsi_tqqq"}
        ret     = tqqq_r if is_tqqq else cash_r
        equity  *= (1.0 + ret)

        sma_str = "" if np.isnan(float(sma_prev)) else str(float(sma_prev))

        rows.append({
            "Date":                         d.date().isoformat(),
            "gspc_open_implied_rsi14":      "" if rsi_v is None else str(rsi_v),
            "GSPC_BB20_Z":                  "" if z_v is None else str(z_v),
            "GSPC_OPEN":                    str(gspc_open),
            "GSPC_SMA160_PREV_CLOSE":       sma_str,
            "TQQQ_OPEN":                    "" if np.isnan(to_val) else str(to_val),
            "TQQQ_PEAK_OPEN":               str(tqqq_peak),
            "TQQQ_RUNNING_DRAWDOWN_PCT":    str(drawdown_pct),
            "DRAWDOWN_ALPHA_PCT":           str(ALPHA_DRAWDOWN_PCT),
            "signal_below_sma":             str(below_sma),
            "drawdown_trigger":             str(triggered),
            "base_target_regime_at_open":   base,
            "selected_leg":                 selected,
            "action":                       action,
            "skip_reason":                  "",
            "strategy_return":              str(ret),
            "strategy_equity":              str(equity),
        })

        gspc_closes.append(gspc_open)

    return rows, {
        "cash_uvix_entries":   cash_uvix_entries,
        "cash_uvix_exits":     cash_uvix_exits,
        "cash_uvix_rsi_exits": cash_uvix_rsi_exits,
        "cash_uvix_gspc_exits":cash_uvix_gspc_exits,
        "low_rsi_entries":     low_rsi_entries,
        "low_rsi_exits":       low_rsi_exits,
    }


# ── metrics ────────────────────────────────────────────────────────────────────

def compute_metrics(returns: np.ndarray, start: str, end: str) -> dict:
    r    = np.clip(returns, -0.999999, None)
    eq   = np.cumprod(1.0 + r)
    yrs  = len(r) / TRADING_DAYS
    cagr = float(eq[-1] ** (1.0 / yrs) - 1.0)
    vol  = float(np.std(r, ddof=0) * np.sqrt(TRADING_DAYS))
    mdd  = float(np.min(eq / np.maximum.accumulate(eq) - 1.0))
    return {
        "cagr": cagr, "annualized_vol": vol, "max_drawdown": mdd,
        "final_multiple": float(eq[-1]),
        "start": start, "end": end,
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Downloading market data ...")
    gspc   = _dl("^GSPC", GSPC_DL_START).rename("GSPC")
    irx    = (_dl("^IRX", IRX_DL_START) / 100.0 / TRADING_DAYS).rename("cash")
    ohlc   = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    tqqq_cc = ohlc["TQQQ_CC_RETURN_REBUILT"].rename("tqqq_cc")

    # ── Pre-2005 synthetic canonical ──────────────────────────────────────────
    print("Simulating pre-2005 synthetic canonical ...")
    pre_rows, pre_stats = simulate_pre2005(gspc, tqqq_cc, irx)
    print(f"  {pre_rows[0]['Date']} – {pre_rows[-1]['Date']}  ({len(pre_rows)} days)")

    # ── Post-2005: start from actual canonical, patch α=100% ─────────────────
    # The actual canonical uses α=94%, which fires on 5 days in March 2009.
    # For α=100% consistency, replace those trigger days with wait_mix returns.
    print("Loading post-2005 actual canonical (patching α=94%→100%) ...")
    post_df = pd.read_csv(CANON_2005_PATH, parse_dates=["Date"]).sort_values("Date").set_index("Date")
    print(f"  {post_df.index[0].date()} – {post_df.index[-1].date()}  "
          f"({len(post_df)} days)")

    trigger_dates = post_df[post_df["drawdown_trigger"] == True].index
    print(f"  α=94% trigger days being patched to wait_mix: "
          f"{[d.date().isoformat() for d in trigger_dates]}")

    # For trigger days: substitute wait_mix return (0.5*TMF + 0.5*GLD CC return)
    for d in trigger_dates:
        if d in ohlc.index:
            tmf_r = ohlc.loc[d, "TMF_RETURN"] if "TMF_RETURN" in ohlc.columns else np.nan
            gld_r = ohlc.loc[d, "GLD_RETURN"] if "GLD_RETURN" in ohlc.columns else np.nan
            if not (np.isnan(tmf_r) or np.isnan(gld_r)):
                post_df.loc[d, "strategy_return"]           = 0.5 * tmf_r + 0.5 * gld_r
                post_df.loc[d, "selected_leg"]              = "wait_mix"
                post_df.loc[d, "drawdown_trigger"]          = False
                post_df.loc[d, "base_target_regime_at_open"]= "wait_mix"
                post_df.loc[d, "DRAWDOWN_ALPHA_PCT"]        = ALPHA_DRAWDOWN_PCT

    # Recompute cumulative equity from the patched returns (post-2005 starts at 1.0)
    post_returns = post_df["strategy_return"].values.astype(float)
    post_equity  = np.cumprod(1.0 + np.clip(post_returns, -0.999999, None))
    post_df["strategy_equity"] = post_equity

    # Re-base equity to continue from last pre-2005 value
    pre_last_equity = float(pre_rows[-1]["strategy_equity"])
    post_df["strategy_equity"] = post_df["strategy_equity"] * pre_last_equity

    post_rows: list[dict] = []
    for d, r in post_df.iterrows():
        row = {c: str(r[c]) if c in r.index else "" for c in DAILY_PATH_COLS}
        row["Date"] = d.date().isoformat()
        post_rows.append(row)

    # ── Stitch ────────────────────────────────────────────────────────────────
    all_rows = pre_rows + post_rows
    print(f"\nStitched: {all_rows[0]['Date']} – {all_rows[-1]['Date']}  "
          f"({len(all_rows)} days)")

    # compute full-series metrics
    returns = np.array([float(r["strategy_return"]) for r in all_rows])
    met = compute_metrics(returns, all_rows[0]["Date"], all_rows[-1]["Date"])

    print(f"  CAGR={met['cagr']*100:.2f}%  "
          f"Vol={met['annualized_vol']*100:.2f}%  "
          f"MDD={met['max_drawdown']*100:.2f}%  "
          f"Final multiple={met['final_multiple']:.0f}x")

    # ── Write daily path CSV ──────────────────────────────────────────────────
    with OUT_DAILY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DAILY_PATH_COLS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nSaved → {OUT_DAILY.name}")

    # ── Compute UVIX/low_rsi stats from post-2005 (actual UVIX exists there) ─
    post_summary_path = CANON_2005_PATH.with_name(
        CANON_2005_PATH.name.replace("_daily_path.csv", "_summary.csv")
    )
    post_sum = {}
    with post_summary_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            post_sum = row

    # ── Write summary CSV ─────────────────────────────────────────────────────
    summary = {
        "cagr":                       str(met["cagr"]),
        "annualized_vol":             str(met["annualized_vol"]),
        "max_drawdown":               str(met["max_drawdown"]),
        "final_multiple":             str(met["final_multiple"]),
        # UVIX metrics come from the post-2005 actual canonical
        "uvix_entries":               post_sum.get("uvix_entries", ""),
        "uvix_exits":                 post_sum.get("uvix_exits", ""),
        "uvix_gspc_profit_exit_only": post_sum.get("uvix_gspc_profit_exit_only", ""),
        "uvix_rsi_exit_only":         post_sum.get("uvix_rsi_exit_only", ""),
        "uvix_rsi_and_gspc_profit_exit": post_sum.get("uvix_rsi_and_gspc_profit_exit", ""),
        # low_rsi: both pre- and post-2005 contribute
        "low_rsi_entries":            str(
            pre_stats["low_rsi_entries"] + int(float(post_sum.get("low_rsi_entries", 0) or 0))
        ),
        "low_rsi_exits":              str(
            pre_stats["low_rsi_exits"]   + int(float(post_sum.get("low_rsi_exits", 0) or 0))
        ),
        "skipped_uvix_entry_days":    post_sum.get("skipped_uvix_entry_days", ""),
        "start":                      all_rows[0]["Date"],
        "end":                        all_rows[-1]["Date"],
        "alpha_drawdown_pct":         str(ALPHA_DRAWDOWN_PCT),
        "uvix_entry_rsi":             str(UVIX_ENTRY_RSI),
        "uvix_entry_min_bb_z":        str(UVIX_ENTRY_MIN_BB_Z),
        "uvix_exit_rsi":              str(UVIX_EXIT_RSI),
        "uvix_gspc_profit_exit_pct":  str(UVIX_GSPC_PROFIT),
        "low_rsi_entry":              str(LOW_RSI_ENTRY),
        "low_rsi_exit":               str(LOW_RSI_EXIT),
        "uvix_day_share":             post_sum.get("uvix_day_share", ""),
        "low_rsi_day_share":          "",
        "base_reentry_rule":          "tqqq_open_drawdown_from_immediate_prior_peak",
        "transition_policy":          "one_open_transition_per_day",
        "series_note": (
            "α=100% (drawdown re-entry disabled) applied consistently throughout 1991–2026. "
            "1991-01-02 to 2005-12-19: synthetic canonical (UVIX→Cash, wait_mix→Cash, "
            "TQQQ→TQQQ_CC_RETURN_REBUILT). "
            "2005-12-20 onward: actual canonical logic with α=94% trigger days patched to wait_mix."
        ),
    }

    with OUT_SUMMARY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)
    print(f"Saved → {OUT_SUMMARY.name}")


if __name__ == "__main__":
    main()
