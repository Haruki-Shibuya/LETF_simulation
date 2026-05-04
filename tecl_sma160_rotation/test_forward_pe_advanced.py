"""
Advanced forward P/E factor tests.

Families:
  A. P/E momentum (month-over-month delta)
  B. P/E rolling z-score (relative valuation vs own history)
  C. NDX−SP500 spread z-score (tech premium signal)
  D. Compound P/E + BB20Z (double overextension / double cheapness)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

CANONICAL_2005_PATH = (
    OUTPUT_DIR
    / "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220_daily_path.csv"
)
CANONICAL_2010_PATH = (
    OUTPUT_DIR
    / "canonical_prev_close_signal_same_open_exec_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_daily_path.csv"
)
VALUATION_MONTHLY_PATH = OUTPUT_DIR / "valuation_forward_pe_2005_sim_monthly.csv"
VALUATION_DAILY_PATH = OUTPUT_DIR / "valuation_forward_pe_2005_sim_daily_ffill.csv"
MARKET_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"

# ── helpers ──────────────────────────────────────────────────────────────────

def compute_metrics(returns: pd.Series) -> dict[str, float]:
    returns = returns.astype(float).clip(lower=-0.999999)
    equity = (1.0 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    vol = returns.std(ddof=0) * np.sqrt(TRADING_DAYS)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    return {
        "cagr": cagr,
        "annualized_vol": float(vol),
        "max_drawdown": float((equity / equity.cummax() - 1.0).min()),
        "final_multiple": float(equity.iloc[-1]),
        "cagr_over_vol": cagr / vol if vol else np.nan,
    }


def normalize_state(s: str) -> str:
    if s in {"TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"}:
        return "TQQQ"
    if s == "UVIX":
        return "UVIX"
    return "wait_mix"


def leg_return(frame: pd.DataFrame, state: pd.Series, suffix: str) -> pd.Series:
    n = state.map(normalize_state)
    wait = 0.5 * frame[f"TMF_{suffix}_RETURN"] + 0.5 * frame[f"GLD_{suffix}_RETURN"]
    return pd.Series(
        np.select(
            [n.eq("UVIX"), n.eq("TQQQ")],
            [frame[f"UVIX_{suffix}_RETURN"], frame[f"TQQQ_{suffix}_RETURN"]],
            default=wait,
        ),
        index=frame.index,
        dtype=float,
    )


def simulate(frame: pd.DataFrame, selected: pd.Series) -> dict[str, float]:
    selected = selected.astype(str)
    prev = selected.shift(1)
    prev.iloc[0] = selected.iloc[0]
    returns = (1.0 + leg_return(frame, prev, "CTO")) * (1.0 + leg_return(frame, selected, "OTC")) - 1.0
    return compute_metrics(returns)


def tqqq_to_wait(selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    out.loc[mask & selected.isin(["TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"])] = "wait_mix"
    return out


def wait_to_tqqq(selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    out.loc[mask & selected.eq("wait_mix")] = "TQQQ"
    return out


def uvix_to_base(frame: pd.DataFrame, selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    base = frame["base_target_regime_at_open"].where(
        frame["base_target_regime_at_open"].eq("wait_mix"), "TQQQ"
    )
    out.loc[mask & selected.eq("UVIX")] = base.loc[mask & selected.eq("UVIX")]
    return out


# ── factor construction ───────────────────────────────────────────────────────

def build_monthly_factors() -> pd.DataFrame:
    m = pd.read_csv(VALUATION_MONTHLY_PATH, parse_dates=["date"]).set_index("date").sort_index()
    sp = m["sp500_forward_pe"].astype(float)
    qqq = m["qqq_forward_pe"].astype(float)

    m["sp_mom_1m"] = sp.diff(1)
    m["sp_mom_3m"] = sp.diff(3)
    m["qqq_mom_1m"] = qqq.diff(1)
    m["qqq_mom_3m"] = qqq.diff(3)

    for w in [18, 24, 36]:
        m[f"sp_z{w}m"] = (sp - sp.rolling(w, min_periods=6).mean()) / sp.rolling(w, min_periods=6).std(ddof=0)
        m[f"qqq_z{w}m"] = (qqq - qqq.rolling(w, min_periods=6).mean()) / qqq.rolling(w, min_periods=6).std(ddof=0)

    spread = qqq - sp
    m["pe_spread"] = spread
    m["spread_z24m"] = (
        (spread - spread.rolling(24, min_periods=6).mean())
        / spread.rolling(24, min_periods=6).std(ddof=0)
    )
    return m


def forward_fill_factors_to_daily(monthly: pd.DataFrame, daily_index: pd.DatetimeIndex) -> pd.DataFrame:
    factor_cols = [c for c in monthly.columns if c not in {"sp500_forward_pe", "qqq_forward_pe"}]
    combined = monthly[factor_cols].reindex(daily_index.union(monthly.index).sort_values()).ffill()
    return combined.reindex(daily_index)


def load_frame(canonical_path: Path) -> pd.DataFrame:
    canon = pd.read_csv(canonical_path, parse_dates=["Date"]).set_index("Date").sort_index()

    # Normalise BB20Z / RSI column names across both canonical paths
    bb20z_col = "GSPC_BB20_Z" if "GSPC_BB20_Z" in canon.columns else "GSPC_CLOSE_BB20_Z"

    val_daily = (
        pd.read_csv(VALUATION_DAILY_PATH, parse_dates=["date"])
        .rename(columns={"date": "Date"})
        .set_index("Date")
    )
    market = pd.read_csv(MARKET_OHLC_PATH, parse_dates=["Date"]).set_index("Date")
    uvix = pd.read_csv(UVIX_OHLC_PATH, parse_dates=["Date"]).set_index("Date")

    monthly = build_monthly_factors()
    daily_factors = forward_fill_factors_to_daily(monthly, canon.index)

    frame = (
        canon[["selected_leg", "base_target_regime_at_open", bb20z_col]]
        .rename(columns={bb20z_col: "bb20z"})
        .join(val_daily[["sp500_forward_pe", "qqq_forward_pe"]], how="inner")
        .join(daily_factors, how="left")
        .join(
            market[
                ["TQQQ_CTO_RETURN", "TQQQ_OTC_RETURN",
                 "TMF_CTO_RETURN", "TMF_OTC_RETURN",
                 "GLD_CTO_RETURN", "GLD_OTC_RETURN"]
            ],
            how="inner",
        )
        .join(uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]], how="inner")
    )
    return frame.dropna(subset=["selected_leg", "TQQQ_CTO_RETURN"]).copy()


# ── trial builder ─────────────────────────────────────────────────────────────

def build_trials(frame: pd.DataFrame) -> list[dict]:
    sel = frame["selected_leg"]
    trials: list[dict] = [{"family": "baseline", "name": "baseline", "params": {}, "selected": sel.copy()}]

    # ── A. P/E momentum ──────────────────────────────────────────────────────
    # negative momentum → TQQQ→wait (caution when market de-rates)
    # positive momentum → wait→TQQQ (stay long when market re-rates up)
    for series_label, mom1, mom3 in [
        ("sp", "sp_mom_1m", "sp_mom_3m"),
        ("qqq", "qqq_mom_1m", "qqq_mom_3m"),
    ]:
        for mom_col, mom_tag in [(mom1, "1m"), (mom3, "3m")]:
            col = frame[mom_col]
            for th in [-2.0, -1.5, -1.0, -0.5, -0.3]:
                mask = col < th
                trials.append({
                    "family": "A_mom_neg_tqqq_to_wait",
                    "name": f"A_{series_label}_mom{mom_tag}_lt_{th}__tqqq_to_wait",
                    "params": {f"{series_label}_mom{mom_tag}_lt": th},
                    "selected": tqqq_to_wait(sel, mask),
                })
                trials.append({
                    "family": "A_mom_neg_block_uvix",
                    "name": f"A_{series_label}_mom{mom_tag}_lt_{th}__block_uvix",
                    "params": {f"{series_label}_mom{mom_tag}_lt": th},
                    "selected": uvix_to_base(frame, sel, mask),
                })
            for th in [0.3, 0.5, 1.0, 1.5, 2.0]:
                mask = col > th
                trials.append({
                    "family": "A_mom_pos_wait_to_tqqq",
                    "name": f"A_{series_label}_mom{mom_tag}_gt_{th}__wait_to_tqqq",
                    "params": {f"{series_label}_mom{mom_tag}_gt": th},
                    "selected": wait_to_tqqq(sel, mask),
                })

    # ── B. P/E rolling z-score ───────────────────────────────────────────────
    for series_label, z_prefix in [("sp", "sp_z"), ("qqq", "qqq_z")]:
        for w in [18, 24, 36]:
            zcol = frame[f"{z_prefix}{w}m"]
            for th in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
                mask = zcol > th
                trials.append({
                    "family": "B_zscore_high_tqqq_to_wait",
                    "name": f"B_{series_label}_z{w}m_gt_{th}__tqqq_to_wait",
                    "params": {f"{series_label}_z{w}m_gt": th},
                    "selected": tqqq_to_wait(sel, mask),
                })
            for th in [-0.5, -0.75, -1.0, -1.25, -1.5]:
                mask = zcol < th
                trials.append({
                    "family": "B_zscore_low_wait_to_tqqq",
                    "name": f"B_{series_label}_z{w}m_lt_{th}__wait_to_tqqq",
                    "params": {f"{series_label}_z{w}m_lt": th},
                    "selected": wait_to_tqqq(sel, mask),
                })
                trials.append({
                    "family": "B_zscore_low_block_uvix",
                    "name": f"B_{series_label}_z{w}m_lt_{th}__block_uvix",
                    "params": {f"{series_label}_z{w}m_lt": th},
                    "selected": uvix_to_base(frame, sel, mask),
                })

    # ── C. NDX−SP500 spread z-score ──────────────────────────────────────────
    sz = frame["spread_z24m"]
    for th in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        mask = sz > th
        trials.append({
            "family": "C_spread_high_tqqq_to_wait",
            "name": f"C_spread_z24m_gt_{th}__tqqq_to_wait",
            "params": {"spread_z24m_gt": th},
            "selected": tqqq_to_wait(sel, mask),
        })
    for th in [-0.5, -0.75, -1.0, -1.25, -1.5]:
        mask = sz < th
        trials.append({
            "family": "C_spread_low_wait_to_tqqq",
            "name": f"C_spread_z24m_lt_{th}__wait_to_tqqq",
            "params": {"spread_z24m_lt": th},
            "selected": wait_to_tqqq(sel, mask),
        })

    # ── D. Compound P/E level + BB20Z ────────────────────────────────────────
    bb = frame["bb20z"]
    sp_pe = frame["sp500_forward_pe"]
    qqq_pe = frame["qqq_forward_pe"]

    # Both overbought: high P/E AND high BB20Z → reduce TQQQ
    for pe_th in [14.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0]:
        for bb_th in [0.0, 0.5, 1.0, 1.5, 2.0]:
            mask_sp = (sp_pe > pe_th) & (bb > bb_th)
            trials.append({
                "family": "D_sp_pe_AND_bb20z_tqqq_to_wait",
                "name": f"D_sp_pe_gt_{pe_th}_AND_bb_gt_{bb_th}__tqqq_to_wait",
                "params": {"sp_pe_gt": pe_th, "bb20z_gt": bb_th},
                "selected": tqqq_to_wait(sel, mask_sp),
            })
            mask_qqq = (qqq_pe > pe_th + 4) & (bb > bb_th)
            trials.append({
                "family": "D_qqq_pe_AND_bb20z_tqqq_to_wait",
                "name": f"D_qqq_pe_gt_{pe_th+4}_AND_bb_gt_{bb_th}__tqqq_to_wait",
                "params": {"qqq_pe_gt": pe_th + 4, "bb20z_gt": bb_th},
                "selected": tqqq_to_wait(sel, mask_qqq),
            })

    # Both oversold: low P/E AND low BB20Z → add TQQQ
    for pe_th in [13.0, 14.0, 15.0, 16.0, 17.0]:
        for bb_th in [0.0, -0.5, -1.0, -1.5]:
            mask_sp = (sp_pe < pe_th) & (bb < bb_th)
            trials.append({
                "family": "D_sp_pe_AND_bb20z_wait_to_tqqq",
                "name": f"D_sp_pe_lt_{pe_th}_AND_bb_lt_{bb_th}__wait_to_tqqq",
                "params": {"sp_pe_lt": pe_th, "bb20z_lt": bb_th},
                "selected": wait_to_tqqq(sel, mask_sp),
            })

    # High P/E → TQQQ to wait, simultaneously low P/E → wait to TQQQ (bidirectional)
    for high_pe, low_pe, bb_high, bb_low in [
        (20.0, 15.0, 0.5, -0.5),
        (19.0, 14.0, 1.0, -1.0),
        (18.0, 13.0, 1.0, -1.0),
    ]:
        mask_high = (sp_pe > high_pe) & (bb > bb_high)
        mask_low = (sp_pe < low_pe) & (bb < bb_low)
        trials.append({
            "family": "D_bidirectional_sp_AND_bb20z",
            "name": f"D_sp_bidi_pe{high_pe}/{low_pe}_bb{bb_high}/{bb_low}",
            "params": {"sp_pe_high": high_pe, "sp_pe_low": low_pe, "bb_high": bb_high, "bb_low": bb_low},
            "selected": wait_to_tqqq(tqqq_to_wait(sel, mask_high), mask_low),
        })

    return trials


# ── runner ────────────────────────────────────────────────────────────────────

def run_suite(label: str, canonical_path: Path) -> pd.DataFrame:
    frame = load_frame(canonical_path)
    trials = build_trials(frame)

    rows = []
    for t in trials:
        sel = t["selected"].astype(str)
        m = simulate(frame, sel)
        changed = sel.ne(frame["selected_leg"])
        rows.append({
            "period": label,
            "family": t["family"],
            "name": t["name"],
            **t["params"],
            **m,
            "changed_day_share": float(changed.mean()),
            "uvix_share": float(sel.eq("UVIX").mean()),
            "tqqq_share": float(sel.isin(["TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"]).mean()),
            "wait_share": float(sel.eq("wait_mix").mean()),
        })

    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_DIR / f"forward_pe_advanced_tests_{label}.csv", index=False)
    return result


def print_report(results: pd.DataFrame, period: str) -> None:
    g = results[results["period"] == period].copy()
    baseline = g[g["family"] == "baseline"].iloc[0]
    b_cagr = baseline["cagr"]
    b_vol = baseline["annualized_vol"]
    b_mdd = baseline["max_drawdown"]
    b_ratio = baseline["cagr_over_vol"]

    print(f"\n{'='*70}")
    print(f" {period}  baseline: CAGR={b_cagr*100:.2f}%  Vol={b_vol*100:.2f}%  MDD={b_mdd*100:.2f}%  Ratio={b_ratio:.3f}")
    print(f"{'='*70}")

    cols = ["family", "name", "cagr", "annualized_vol", "max_drawdown", "cagr_over_vol", "changed_day_share"]

    print("\n--- TOP 20 by CAGR ---")
    top = g.sort_values("cagr", ascending=False).head(20)
    for _, r in top.iterrows():
        delta_c = (r["cagr"] - b_cagr) * 100
        delta_v = (r["annualized_vol"] - b_vol) * 100
        delta_d = (r["max_drawdown"] - b_mdd) * 100
        marker = "★" if r["cagr"] > b_cagr else " "
        print(f"  {marker} {r['family']:<38} CAGR={r['cagr']*100:6.2f}% ({delta_c:+.2f})  "
              f"Vol={r['annualized_vol']*100:5.2f}% ({delta_v:+.2f})  "
              f"MDD={r['max_drawdown']*100:6.2f}% ({delta_d:+.2f})  "
              f"chg={r['changed_day_share']*100:.1f}%")

    print("\n--- TOP 20 by CAGR/Vol ---")
    top_r = g.sort_values("cagr_over_vol", ascending=False).head(20)
    for _, r in top_r.iterrows():
        delta_c = (r["cagr"] - b_cagr) * 100
        delta_v = (r["annualized_vol"] - b_vol) * 100
        marker = "★" if r["cagr_over_vol"] > b_ratio else " "
        print(f"  {marker} {r['family']:<38} Ratio={r['cagr_over_vol']:5.3f}  "
              f"CAGR={r['cagr']*100:6.2f}% ({delta_c:+.2f})  "
              f"Vol={r['annualized_vol']*100:5.2f}% ({delta_v:+.2f})  "
              f"chg={r['changed_day_share']*100:.1f}%")

    print("\n--- Cases where CAGR >= baseline AND Vol < baseline ---")
    both = g[(g["cagr"] >= b_cagr) & (g["annualized_vol"] < b_vol)].sort_values("cagr", ascending=False)
    if both.empty:
        print("  (none)")
    else:
        for _, r in both.iterrows():
            delta_c = (r["cagr"] - b_cagr) * 100
            delta_v = (r["annualized_vol"] - b_vol) * 100
            print(f"  ★ {r['name'][:70]:<70}  "
                  f"CAGR={r['cagr']*100:.2f}% ({delta_c:+.2f})  Vol={r['annualized_vol']*100:.2f}% ({delta_v:+.2f})")

    # Best per family summary
    print("\n--- Best per family (by CAGR) ---")
    for fam, sub in g.groupby("family"):
        best = sub.sort_values("cagr", ascending=False).iloc[0]
        delta_c = (best["cagr"] - b_cagr) * 100
        delta_v = (best["annualized_vol"] - b_vol) * 100
        marker = "★" if best["cagr"] > b_cagr else " "
        print(f"  {marker} {fam:<40} CAGR={best['cagr']*100:6.2f}% ({delta_c:+.2f})  "
              f"Vol={best['annualized_vol']*100:5.2f}% ({delta_v:+.2f})  "
              f"name={best['name'][:50]}")


def main() -> None:
    print("Running advanced forward P/E factor tests...")
    r2005 = run_suite("from_20051220", CANONICAL_2005_PATH)
    r2010 = run_suite("from_20100212", CANONICAL_2010_PATH)
    all_results = pd.concat([r2005, r2010], ignore_index=True)
    all_results.to_csv(OUTPUT_DIR / "forward_pe_advanced_tests_summary.csv", index=False)
    print(f"Total trials: {len(r2005)} per period")
    print_report(all_results, "from_20051220")
    print_report(all_results, "from_20100212")


if __name__ == "__main__":
    main()
