from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

DEFAULT_REFERENCE_DAILY_PATH = (
    OUTPUT_DIR
    / "prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_"
    "fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_daily_path.csv"
)
DEFAULT_TQQQ_TMF_GLD_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
DEFAULT_UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-daily-path", type=Path, default=DEFAULT_REFERENCE_DAILY_PATH)
    parser.add_argument("--tqqq-tmf-gld-ohlc-path", type=Path, default=DEFAULT_TQQQ_TMF_GLD_OHLC_PATH)
    parser.add_argument("--uvix-ohlc-path", type=Path, default=DEFAULT_UVIX_OHLC_PATH)
    parser.add_argument("--backtest-start", default="2010-02-12")
    parser.add_argument("--uvix-entry-rsi", type=float, default=69.5)
    parser.add_argument("--uvix-exit-rsi", type=float, default=68.5)
    parser.add_argument("--uvix-tqqq-drop-exit-pct", type=float, default=0.0)
    parser.add_argument("--low-rsi-entry", type=float, default=30.0)
    parser.add_argument("--low-rsi-exit", type=float, default=32.5)
    parser.add_argument("--wait-tmf", type=float, default=50.0)
    parser.add_argument("--wait-gld", type=float, default=50.0)
    parser.add_argument(
        "--output-stem",
        default="canonical_prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212",
    )
    return parser.parse_args()


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


def load_frame(args: argparse.Namespace) -> pd.DataFrame:
    reference = pd.read_csv(args.reference_daily_path, parse_dates=["Date"]).set_index("Date").sort_index()
    ohlc = pd.read_csv(args.tqqq_tmf_gld_ohlc_path, parse_dates=["Date"]).set_index("Date").sort_index()
    uvix = pd.read_csv(args.uvix_ohlc_path, parse_dates=["Date"]).set_index("Date").sort_index()

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
    frame = frame.join(uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]], how="inner")
    return frame.loc[pd.Timestamp(args.backtest_start) :].dropna().copy()


def simulate(frame: pd.DataFrame, args: argparse.Namespace) -> tuple[dict[str, float], pd.DataFrame]:
    rsi = frame["gspc_open_implied_rsi14"].to_numpy(float)
    base_regime = frame["base_target_regime_at_open"].astype(str).to_numpy()
    tqqq_open = frame["TQQQ_OPEN"].to_numpy(float)
    tqqq_cto = frame["TQQQ_CTO_RETURN"].to_numpy(float)
    tqqq_otc = frame["TQQQ_OTC_RETURN"].to_numpy(float)
    uvix_cto = frame["UVIX_CTO_RETURN"].to_numpy(float)
    uvix_otc = frame["UVIX_OTC_RETURN"].to_numpy(float)

    wait_total = args.wait_tmf + args.wait_gld
    if wait_total <= 0:
        raise ValueError("wait weights must sum to a positive value")
    wait_tmf_weight = args.wait_tmf / wait_total
    wait_gld_weight = args.wait_gld / wait_total
    wait_cto = wait_tmf_weight * frame["TMF_CTO_RETURN"].to_numpy(float) + wait_gld_weight * frame[
        "GLD_CTO_RETURN"
    ].to_numpy(float)
    wait_otc = wait_tmf_weight * frame["TMF_OTC_RETURN"].to_numpy(float) + wait_gld_weight * frame[
        "GLD_OTC_RETURN"
    ].to_numpy(float)

    def base_state(index: int) -> str:
        return "wait_mix" if base_regime[index] == "wait_mix" else "TQQQ"

    def close_to_open_return(previous_state: str, index: int) -> float:
        if previous_state == "UVIX":
            return uvix_cto[index]
        if previous_state in {"TQQQ", "low_rsi_tqqq_override"}:
            return tqqq_cto[index]
        return wait_cto[index]

    def open_to_close_return(target_state: str, index: int) -> float:
        if target_state == "UVIX":
            return uvix_otc[index]
        if target_state in {"TQQQ", "low_rsi_tqqq_override"}:
            return tqqq_otc[index]
        return wait_otc[index]

    active_uvix = False
    active_low_rsi_override = False
    uvix_entry_tqqq_open = np.nan
    previous_state = base_state(0)
    returns: list[float] = []
    states: list[str] = []
    actions: list[str] = []
    uvix_entries = 0
    uvix_exits = 0
    low_rsi_entries = 0
    low_rsi_exits = 0

    for i in range(len(frame)):
        target_state = base_state(i)
        daily_actions: list[str] = []

        uvix_drop_exit = (
            active_uvix
            and np.isfinite(uvix_entry_tqqq_open)
            and tqqq_open[i] <= uvix_entry_tqqq_open * (1.0 - args.uvix_tqqq_drop_exit_pct / 100.0)
        )
        if active_uvix and (rsi[i] <= args.uvix_exit_rsi or uvix_drop_exit):
            active_uvix = False
            uvix_entry_tqqq_open = np.nan
            uvix_exits += 1
            daily_actions.append("exit_uvix")

        if active_low_rsi_override and rsi[i] >= args.low_rsi_exit:
            active_low_rsi_override = False
            low_rsi_exits += 1
            daily_actions.append("exit_low_rsi_tqqq_override")

        if not active_uvix and not active_low_rsi_override:
            if rsi[i] >= args.uvix_entry_rsi:
                active_uvix = True
                uvix_entry_tqqq_open = tqqq_open[i]
                uvix_entries += 1
                target_state = "UVIX"
                daily_actions.append("enter_uvix_high_rsi")
            elif rsi[i] < args.low_rsi_entry and base_state(i) == "wait_mix":
                active_low_rsi_override = True
                low_rsi_entries += 1
                target_state = "low_rsi_tqqq_override"
                daily_actions.append("enter_low_rsi_tqqq_override")
        elif active_uvix:
            target_state = "UVIX"
        elif active_low_rsi_override:
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
    summary.update(
        {
            "start": args.backtest_start,
            "uvix_entry_rsi": float(args.uvix_entry_rsi),
            "uvix_exit_rsi": float(args.uvix_exit_rsi),
            "uvix_tqqq_drop_exit_pct": float(args.uvix_tqqq_drop_exit_pct),
            "low_rsi_entry": float(args.low_rsi_entry),
            "low_rsi_exit": float(args.low_rsi_exit),
            "uvix_entries": int(uvix_entries),
            "uvix_exits": int(uvix_exits),
            "uvix_day_share": float((state_series == "UVIX").mean()),
            "low_rsi_entries": int(low_rsi_entries),
            "low_rsi_exits": int(low_rsi_exits),
            "low_rsi_day_share": float((state_series == "low_rsi_tqqq_override").mean()),
        }
    )

    path = frame[["gspc_open_implied_rsi14", "TQQQ_OPEN", "base_target_regime_at_open"]].copy()
    path["selected_leg"] = states
    path["action"] = actions
    path["strategy_return"] = returns
    path["strategy_equity"] = (1.0 + pd.Series(returns, index=path.index).clip(lower=-0.999999)).cumprod()
    return summary, path


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_frame(args)
    summary, path = simulate(frame, args)

    pd.DataFrame([summary]).to_csv(OUTPUT_DIR / f"{args.output_stem}_summary.csv", index=False)
    path.to_csv(OUTPUT_DIR / f"{args.output_stem}_daily_path.csv")

    print(f"Saved: {OUTPUT_DIR / args.output_stem}_*.csv")
    print(
        "Combined canonical: "
        f"CAGR={summary['cagr']*100:.2f}%, "
        f"Vol={summary['annualized_vol']*100:.2f}%, "
        f"MDD={summary['max_drawdown']*100:.2f}%"
    )


if __name__ == "__main__":
    main()
