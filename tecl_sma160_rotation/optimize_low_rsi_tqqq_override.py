from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

DEFAULT_CANONICAL_DAILY_PATH = (
    OUTPUT_DIR
    / "prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_"
    "fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_daily_path.csv"
)
DEFAULT_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-daily-path", type=Path, default=DEFAULT_CANONICAL_DAILY_PATH)
    parser.add_argument("--ohlc-path", type=Path, default=DEFAULT_OHLC_PATH)
    parser.add_argument("--backtest-start", default="2010-02-12")
    parser.add_argument("--rsi-entry", type=float, default=30.0)
    parser.add_argument("--exit-min", type=float, default=0.0)
    parser.add_argument("--exit-max", type=float, default=50.0)
    parser.add_argument("--exit-step", type=float, default=0.5)
    parser.add_argument("--wait-tmf", type=float, default=50.0)
    parser.add_argument("--wait-gld", type=float, default=50.0)
    parser.add_argument("--output-stem", default=None)
    return parser.parse_args()


def format_param(value: float) -> str:
    return f"{value:g}".replace(".", "p")


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
    canonical = pd.read_csv(args.canonical_daily_path, parse_dates=["Date"]).set_index("Date").sort_index()
    ohlc = pd.read_csv(args.ohlc_path, parse_dates=["Date"]).set_index("Date").sort_index()

    required_canonical = {
        "close_to_open_return",
        "open_to_close_return",
        "gspc_open_implied_rsi14",
        "selected_leg",
        "base_target_regime_at_open",
    }
    required_ohlc = {
        "TQQQ_OPEN",
        "TQQQ_CTO_RETURN",
        "TQQQ_OTC_RETURN",
        "TMF_CTO_RETURN",
        "TMF_OTC_RETURN",
        "GLD_CTO_RETURN",
        "GLD_OTC_RETURN",
    }
    missing_canonical = sorted(required_canonical - set(canonical.columns))
    missing_ohlc = sorted(required_ohlc - set(ohlc.columns))
    if missing_canonical:
        raise ValueError(f"canonical daily path is missing columns: {missing_canonical}")
    if missing_ohlc:
        raise ValueError(f"OHLC path is missing columns: {missing_ohlc}")

    frame = canonical.join(ohlc[list(required_ohlc)], how="inner")
    needed = sorted(required_canonical | required_ohlc)
    return frame.loc[pd.Timestamp(args.backtest_start) :].dropna(subset=needed).copy()


def simulate(
    frame: pd.DataFrame,
    *,
    rsi_entry: float,
    exit_pct: float,
    wait_tmf: float,
    wait_gld: float,
    keep_path: bool = False,
) -> tuple[dict[str, float], pd.DataFrame | None]:
    canonical_cto = frame["close_to_open_return"].to_numpy(float)
    canonical_otc = frame["open_to_close_return"].to_numpy(float)
    rsi = frame["gspc_open_implied_rsi14"].to_numpy(float)
    tqqq_open = frame["TQQQ_OPEN"].to_numpy(float)
    tqqq_cto = frame["TQQQ_CTO_RETURN"].to_numpy(float)
    tqqq_otc = frame["TQQQ_OTC_RETURN"].to_numpy(float)
    wait_total = wait_tmf + wait_gld
    if wait_total <= 0:
        raise ValueError("wait weights must sum to a positive value")
    wait_tmf_weight = wait_tmf / wait_total
    wait_gld_weight = wait_gld / wait_total
    wait_cto = wait_tmf_weight * frame["TMF_CTO_RETURN"].to_numpy(float) + wait_gld_weight * frame[
        "GLD_CTO_RETURN"
    ].to_numpy(float)
    wait_otc = wait_tmf_weight * frame["TMF_OTC_RETURN"].to_numpy(float) + wait_gld_weight * frame[
        "GLD_OTC_RETURN"
    ].to_numpy(float)
    base_leg = frame["selected_leg"].astype(str).to_numpy()

    active = False
    entry_price = np.nan
    previous_effective_state = "base"
    returns: list[float] = []
    effective_states: list[str] = []
    actions: list[str] = []
    override_entries = 0
    override_exits = 0

    for i in range(len(frame)):
        target_state = "base"
        action = ""

        # The rebound exit is checked at the current open and trades near that open.
        if active and np.isfinite(entry_price) and tqqq_open[i] >= entry_price * (1.0 + exit_pct / 100.0):
            active = False
            entry_price = np.nan
            target_state = "wait_mix"
            action = "exit_override_to_wait_mix"
            override_exits += 1
        elif (not active) and rsi[i] < rsi_entry and base_leg[i] not in {"above", "below", "TQQQ"}:
            active = True
            entry_price = tqqq_open[i]
            target_state = "tqqq_override"
            action = "enter_low_rsi_tqqq_override"
            override_entries += 1
        elif active:
            target_state = "tqqq_override"

        if previous_effective_state == "tqqq_override":
            close_to_open_return = tqqq_cto[i]
        elif previous_effective_state == "wait_mix":
            close_to_open_return = wait_cto[i]
        else:
            close_to_open_return = canonical_cto[i]

        if target_state == "tqqq_override":
            open_to_close_return = tqqq_otc[i]
            effective_state = "tqqq_override"
        elif target_state == "wait_mix":
            open_to_close_return = wait_otc[i]
            effective_state = "wait_mix"
        else:
            open_to_close_return = canonical_otc[i]
            effective_state = "base"

        strategy_return = (1.0 + close_to_open_return) * (1.0 + open_to_close_return) - 1.0
        returns.append(float(strategy_return))
        effective_states.append(effective_state)
        actions.append(action)
        previous_effective_state = effective_state

    metrics = compute_metrics(returns)
    state_series = pd.Series(effective_states)
    metrics.update(
        {
            "low_rsi_entry": float(rsi_entry),
            "tqqq_rebound_exit_pct": float(exit_pct),
            "override_entries": int(override_entries),
            "override_exits": int(override_exits),
            "override_day_share": float((state_series == "tqqq_override").mean()),
            "wait_exit_day_share": float((state_series == "wait_mix").mean()),
        }
    )

    if not keep_path:
        return metrics, None

    path = frame[["gspc_open_implied_rsi14", "TQQQ_OPEN", "selected_leg", "base_target_regime_at_open"]].copy()
    path["effective_state"] = effective_states
    path["action"] = actions
    path["strategy_return"] = returns
    path["strategy_equity"] = (1.0 + pd.Series(returns, index=path.index).clip(lower=-0.999999)).cumprod()
    return metrics, path


def build_output_stem(args: argparse.Namespace) -> str:
    if args.output_stem:
        return args.output_stem
    start = args.backtest_start.replace("-", "")
    return (
        "provisional_canonical_low_rsi_tqqq_override_"
        f"rsi{format_param(args.rsi_entry)}_"
        f"rebound_exit_opt_from_{start}_"
        f"x{format_param(args.exit_min)}to{format_param(args.exit_max)}step{format_param(args.exit_step)}"
    )


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_frame(args)

    exit_values = np.round(np.arange(args.exit_min, args.exit_max + args.exit_step / 2.0, args.exit_step), 10)
    rows = []
    for exit_pct in exit_values:
        metrics, _ = simulate(
            frame,
            rsi_entry=args.rsi_entry,
            exit_pct=float(exit_pct),
            wait_tmf=args.wait_tmf,
            wait_gld=args.wait_gld,
        )
        metrics["start"] = args.backtest_start
        rows.append(metrics)

    grid = pd.DataFrame(rows)
    grid = grid[
        [
            "start",
            "low_rsi_entry",
            "tqqq_rebound_exit_pct",
            "cagr",
            "annualized_vol",
            "max_drawdown",
            "final_multiple",
            "override_entries",
            "override_exits",
            "override_day_share",
            "wait_exit_day_share",
        ]
    ]
    best = grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).iloc[0].to_dict()
    best_metrics, best_path = simulate(
        frame,
        rsi_entry=args.rsi_entry,
        exit_pct=float(best["tqqq_rebound_exit_pct"]),
        wait_tmf=args.wait_tmf,
        wait_gld=args.wait_gld,
        keep_path=True,
    )
    best.update(best_metrics)

    base_returns = (1.0 + frame["close_to_open_return"]) * (1.0 + frame["open_to_close_return"]) - 1.0
    base_metrics = compute_metrics(base_returns.to_numpy(float))
    base_metrics.update({"start": args.backtest_start, "strategy": "provisional_canonical_without_low_rsi_override"})

    stem = build_output_stem(args)
    grid.to_csv(OUTPUT_DIR / f"{stem}_grid.csv", index=False)
    grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).head(20).to_csv(
        OUTPUT_DIR / f"{stem}_top20.csv", index=False
    )
    pd.DataFrame([best]).to_csv(OUTPUT_DIR / f"{stem}_summary.csv", index=False)
    pd.DataFrame([base_metrics]).to_csv(OUTPUT_DIR / f"{stem}_base_comparison.csv", index=False)
    if best_path is not None:
        best_path.to_csv(OUTPUT_DIR / f"{stem}_daily_path.csv")

    print(f"Saved: {OUTPUT_DIR / stem}_*.csv")
    print(
        "Base canonical: "
        f"CAGR={base_metrics['cagr']*100:.2f}%, "
        f"Vol={base_metrics['annualized_vol']*100:.2f}%, "
        f"MDD={base_metrics['max_drawdown']*100:.2f}%"
    )
    print(
        "Best low-RSI override: "
        f"exit={best['tqqq_rebound_exit_pct']:.1f}%, "
        f"CAGR={best['cagr']*100:.2f}%, "
        f"Vol={best['annualized_vol']*100:.2f}%, "
        f"MDD={best['max_drawdown']*100:.2f}%, "
        f"entries={int(best['override_entries'])}"
    )


if __name__ == "__main__":
    main()
