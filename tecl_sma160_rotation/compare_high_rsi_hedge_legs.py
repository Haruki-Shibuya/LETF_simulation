from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
REFERENCE_DAILY_PATH = (
    OUTPUT_DIR
    / "prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_"
    "fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_daily_path.csv"
)
TQQQ_TMF_GLD_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"

START = "2010-02-12"
TRADING_DAYS = 252
UVIX_ENTRY_RSI = 69.5
UVIX_EXIT_RSI = 68.5
LOW_RSI_ENTRY = 30.0
LOW_RSI_EXIT = 32.5

YFINANCE_CANDIDATES = {
    "TECS": "Direxion Daily Technology Bear 3X",
    "SOXS": "Direxion Daily Semiconductor Bear 3X",
    "SQQQ": "ProShares UltraPro Short QQQ -3X",
    "QID": "ProShares UltraShort QQQ -2X",
    "PSQ": "ProShares Short QQQ -1X",
    "SPXU": "ProShares UltraPro Short S&P500 -3X",
    "SDS": "ProShares UltraShort S&P500 -2X",
    "SH": "ProShares Short S&P500 -1X",
    "UVXY": "ProShares Ultra VIX Short-Term Futures",
    "VIXY": "ProShares VIX Short-Term Futures",
    "VXX": "iPath Series B S&P 500 VIX Short-Term Futures ETN",
    "VIXM": "ProShares VIX Mid-Term Futures ETF",
    "VXZ": "iPath Series B S&P 500 VIX Mid-Term Futures ETN",
    "BTAL": "AGF U.S. Market Neutral Anti-Beta Fund",
    "FNGD": "MicroSectors FANG+ Index -3X Inverse Leveraged ETN",
    "WEBS": "Direxion Daily Dow Jones Internet Bear 3X Shares",
}


def compute_metrics(returns: list[float] | np.ndarray) -> dict[str, float]:
    series = pd.Series(returns, dtype=float).clip(lower=-0.999999)
    equity = (1.0 + series).cumprod()
    years = len(series) / TRADING_DAYS
    return {
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "annualized_vol": float(series.std(ddof=0) * np.sqrt(TRADING_DAYS)),
        "max_drawdown": float((equity / equity.cummax() - 1.0).min()),
        "final_multiple": float(equity.iloc[-1]),
    }


def load_base_frame() -> pd.DataFrame:
    reference = pd.read_csv(REFERENCE_DAILY_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    ohlc = pd.read_csv(TQQQ_TMF_GLD_OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    frame = reference[["gspc_open_implied_rsi14", "base_target_regime_at_open"]].join(
        ohlc[
            [
                "TQQQ_OPEN",
                "TQQQ_CTO_RETURN",
                "TQQQ_OTC_RETURN",
                "TMF_CTO_RETURN",
                "TMF_OTC_RETURN",
                "GLD_CTO_RETURN",
                "GLD_OTC_RETURN",
            ]
        ],
        how="inner",
    )
    return frame.loc[pd.Timestamp(START) :].dropna().copy()


def flatten_download(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        if ticker in frame.columns.get_level_values(-1):
            frame = frame.xs(ticker, axis=1, level=-1)
        else:
            frame.columns = frame.columns.get_level_values(0)
    return frame.dropna(how="all")


def download_candidate_ohlc(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(ticker, start=START, auto_adjust=True, progress=False, threads=False, timeout=20)
    raw = flatten_download(raw, ticker)
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    out = pd.DataFrame(index=raw.index)
    out[f"{ticker}_OPEN"] = raw["Open"].astype(float)
    out[f"{ticker}_CLOSE"] = raw["Close"].astype(float)
    out[f"{ticker}_CTO_RETURN"] = out[f"{ticker}_OPEN"] / out[f"{ticker}_CLOSE"].shift(1) - 1.0
    out[f"{ticker}_OTC_RETURN"] = out[f"{ticker}_CLOSE"] / out[f"{ticker}_OPEN"] - 1.0
    return out


def uvix_candidate() -> pd.DataFrame:
    uvix = pd.read_csv(UVIX_OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    return uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]].rename(
        columns={"UVIX_CTO_RETURN": "UVIX_CANONICAL_CTO_RETURN", "UVIX_OTC_RETURN": "UVIX_CANONICAL_OTC_RETURN"}
    )


def short_tqqq_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["SHORT_TQQQ_CTO_RETURN"] = -frame["TQQQ_CTO_RETURN"]
    out["SHORT_TQQQ_OTC_RETURN"] = -frame["TQQQ_OTC_RETURN"]
    return out


def mix_candidate(frame: pd.DataFrame, name: str, legs: list[tuple[str, float, str, str]]) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    cto = np.zeros(len(frame), dtype=float)
    otc = np.zeros(len(frame), dtype=float)
    for _, weight, cto_col, otc_col in legs:
        cto += weight * frame[cto_col].to_numpy(float)
        otc += weight * frame[otc_col].to_numpy(float)
    out[f"{name}_CTO_RETURN"] = cto
    out[f"{name}_OTC_RETURN"] = otc
    return out


def simulate(frame: pd.DataFrame, leg_name: str, cto_col: str, otc_col: str, description: str) -> tuple[dict, pd.DataFrame]:
    rsi = frame["gspc_open_implied_rsi14"].to_numpy(float)
    base_regime = frame["base_target_regime_at_open"].astype(str).to_numpy()
    tqqq_open = frame["TQQQ_OPEN"].to_numpy(float)
    tqqq_cto = frame["TQQQ_CTO_RETURN"].to_numpy(float)
    tqqq_otc = frame["TQQQ_OTC_RETURN"].to_numpy(float)
    wait_cto = 0.5 * frame["TMF_CTO_RETURN"].to_numpy(float) + 0.5 * frame["GLD_CTO_RETURN"].to_numpy(float)
    wait_otc = 0.5 * frame["TMF_OTC_RETURN"].to_numpy(float) + 0.5 * frame["GLD_OTC_RETURN"].to_numpy(float)
    hedge_cto = frame[cto_col].to_numpy(float)
    hedge_otc = frame[otc_col].to_numpy(float)

    def base_state(index: int) -> str:
        return "wait_mix" if base_regime[index] == "wait_mix" else "TQQQ"

    def close_to_open_return(previous_state: str, index: int) -> float:
        if previous_state == leg_name:
            return hedge_cto[index]
        if previous_state in {"TQQQ", "low_rsi_tqqq_override"}:
            return tqqq_cto[index]
        return wait_cto[index]

    def open_to_close_return(target_state: str, index: int) -> float:
        if target_state == leg_name:
            return hedge_otc[index]
        if target_state in {"TQQQ", "low_rsi_tqqq_override"}:
            return tqqq_otc[index]
        return wait_otc[index]

    active_hedge = False
    active_low_rsi = False
    hedge_entry_tqqq_open = np.nan
    previous_state = base_state(0)
    returns: list[float] = []
    states: list[str] = []
    actions: list[str] = []
    entries = 0
    exits = 0
    skipped_entries_missing_data = 0
    low_entries = 0
    low_exits = 0

    for i in range(len(frame)):
        target_state = base_state(i)
        daily_actions: list[str] = []
        hedge_data_ok = np.isfinite(hedge_cto[i]) and np.isfinite(hedge_otc[i])

        hedge_drop_exit = active_hedge and np.isfinite(hedge_entry_tqqq_open) and tqqq_open[i] <= hedge_entry_tqqq_open
        if active_hedge and (rsi[i] <= UVIX_EXIT_RSI or hedge_drop_exit or not hedge_data_ok):
            active_hedge = False
            hedge_entry_tqqq_open = np.nan
            exits += 1
            daily_actions.append("exit_high_rsi_hedge")

        if active_low_rsi and rsi[i] >= LOW_RSI_EXIT:
            active_low_rsi = False
            low_exits += 1
            daily_actions.append("exit_low_rsi_tqqq_override")

        if not active_hedge and not active_low_rsi:
            if rsi[i] >= UVIX_ENTRY_RSI:
                if hedge_data_ok:
                    active_hedge = True
                    hedge_entry_tqqq_open = tqqq_open[i]
                    entries += 1
                    target_state = leg_name
                    daily_actions.append("enter_high_rsi_hedge")
                else:
                    skipped_entries_missing_data += 1
            elif rsi[i] < LOW_RSI_ENTRY and base_state(i) == "wait_mix":
                active_low_rsi = True
                low_entries += 1
                target_state = "low_rsi_tqqq_override"
                daily_actions.append("enter_low_rsi_tqqq_override")
        elif active_hedge:
            target_state = leg_name
        elif active_low_rsi:
            target_state = "low_rsi_tqqq_override"

        strategy_return = (1.0 + close_to_open_return(previous_state, i)) * (
            1.0 + open_to_close_return(target_state, i)
        ) - 1.0
        returns.append(float(strategy_return))
        states.append(target_state)
        actions.append("|".join(daily_actions))
        previous_state = target_state

    summary = compute_metrics(returns)
    state_series = pd.Series(states)
    first_valid = frame.loc[frame[cto_col].notna() & frame[otc_col].notna()].index.min()
    summary.update(
        {
            "hedge_leg": leg_name,
            "description": description,
            "start": START,
            "first_valid_hedge_date": first_valid.date().isoformat() if pd.notna(first_valid) else None,
            "entry_rsi": UVIX_ENTRY_RSI,
            "exit_rsi": UVIX_EXIT_RSI,
            "tqqq_drop_exit_pct": 0.0,
            "entries": entries,
            "exits": exits,
            "hedge_day_share": float((state_series == leg_name).mean()),
            "skipped_entries_missing_data": skipped_entries_missing_data,
            "low_rsi_entries": low_entries,
            "low_rsi_exits": low_exits,
        }
    )
    path = frame[["gspc_open_implied_rsi14", "TQQQ_OPEN", "base_target_regime_at_open"]].copy()
    path["selected_leg"] = states
    path["action"] = actions
    path["strategy_return"] = returns
    path["strategy_equity"] = (1.0 + pd.Series(returns, index=path.index).clip(lower=-0.999999)).cumprod()
    return summary, path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = load_base_frame()

    candidates: list[tuple[str, pd.DataFrame, str, str, str]] = []
    uvix = uvix_candidate()
    candidates.append(("UVIX_CANONICAL", uvix, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN", "Current UVIX proxy/actual canonical"))
    short = short_tqqq_candidate(base)
    candidates.append(("SHORT_TQQQ", short, "SHORT_TQQQ_CTO_RETURN", "SHORT_TQQQ_OTC_RETURN", "Synthetic unlevered short TQQQ"))

    for ticker, description in YFINANCE_CANDIDATES.items():
        try:
            candidate = download_candidate_ohlc(ticker)
            candidates.append((ticker, candidate, f"{ticker}_CTO_RETURN", f"{ticker}_OTC_RETURN", description))
        except Exception as exc:
            print(f"skip {ticker}: {exc}")

    candidate_frames = [base]
    for _, candidate, _, _, _ in candidates:
        candidate_frames.append(candidate)
    combined = pd.concat(candidate_frames, axis=1)
    mix_specs = {
        "MIX_UVIX50_TMF50": [
            ("UVIX_CANONICAL", 0.5, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("TMF", 0.5, "TMF_CTO_RETURN", "TMF_OTC_RETURN"),
        ],
        "MIX_UVIX50_GLD50": [
            ("UVIX_CANONICAL", 0.5, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("GLD", 0.5, "GLD_CTO_RETURN", "GLD_OTC_RETURN"),
        ],
        "MIX_UVIX50_SOXS50": [
            ("UVIX_CANONICAL", 0.5, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("SOXS", 0.5, "SOXS_CTO_RETURN", "SOXS_OTC_RETURN"),
        ],
        "MIX_UVIX50_BTAL50": [
            ("UVIX_CANONICAL", 0.5, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("BTAL", 0.5, "BTAL_CTO_RETURN", "BTAL_OTC_RETURN"),
        ],
        "MIX_VIXY50_SOXS50": [
            ("VIXY", 0.5, "VIXY_CTO_RETURN", "VIXY_OTC_RETURN"),
            ("SOXS", 0.5, "SOXS_CTO_RETURN", "SOXS_OTC_RETURN"),
        ],
        "MIX_UVIX33_SOXS33_TMF34": [
            ("UVIX_CANONICAL", 0.33, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("SOXS", 0.33, "SOXS_CTO_RETURN", "SOXS_OTC_RETURN"),
            ("TMF", 0.34, "TMF_CTO_RETURN", "TMF_OTC_RETURN"),
        ],
        "MIX_UVIX34_VIXY33_TMF33": [
            ("UVIX_CANONICAL", 0.34, "UVIX_CANONICAL_CTO_RETURN", "UVIX_CANONICAL_OTC_RETURN"),
            ("VIXY", 0.33, "VIXY_CTO_RETURN", "VIXY_OTC_RETURN"),
            ("TMF", 0.33, "TMF_CTO_RETURN", "TMF_OTC_RETURN"),
        ],
        "MIX_BTAL50_TMF50": [
            ("BTAL", 0.5, "BTAL_CTO_RETURN", "BTAL_OTC_RETURN"),
            ("TMF", 0.5, "TMF_CTO_RETURN", "TMF_OTC_RETURN"),
        ],
        "MIX_SQQQ50_GLD50": [
            ("SQQQ", 0.5, "SQQQ_CTO_RETURN", "SQQQ_OTC_RETURN"),
            ("GLD", 0.5, "GLD_CTO_RETURN", "GLD_OTC_RETURN"),
        ],
    }
    for mix_name, legs in mix_specs.items():
        needed = [col for _, _, cto_col, otc_col in legs for col in (cto_col, otc_col)]
        if all(col in combined.columns for col in needed):
            candidate = mix_candidate(combined, mix_name, legs)
            candidates.append((mix_name, candidate, f"{mix_name}_CTO_RETURN", f"{mix_name}_OTC_RETURN", "Static high-RSI basket: " + ", ".join(f"{weight:.0%} {leg}" for leg, weight, _, _ in legs)))

    summaries = []
    for leg_name, candidate, cto_col, otc_col, description in candidates:
        frame = base.join(candidate[[cto_col, otc_col]], how="left")
        summary, path = simulate(frame, leg_name, cto_col, otc_col, description)
        summaries.append(summary)
        path.to_csv(OUTPUT_DIR / f"high_rsi_hedge_leg_compare_{leg_name.lower()}_daily_path.csv")

    summary_df = pd.DataFrame(summaries).sort_values(["cagr", "final_multiple"], ascending=[False, False])
    summary_df.to_csv(OUTPUT_DIR / "high_rsi_hedge_leg_compare_summary.csv", index=False)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
