from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

DEFAULT_REFERENCE_DAILY_PATH = (
    OUTPUT_DIR
    / "canonical_prev_close_sma_same_open_running_dd_uvix_bb20z_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212_daily_path.csv"
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
    parser.add_argument("--uvix-entry-min-bb-z", type=float, default=1.6)
    parser.add_argument("--uvix-exit-rsi", type=float, default=68.5)
    parser.add_argument("--low-rsi-entry", type=float, default=30.0)
    parser.add_argument("--low-rsi-exit", type=float, default=32.5)
    parser.add_argument("--wait-tmf", type=float, default=50.0)
    parser.add_argument("--wait-gld", type=float, default=50.0)
    parser.add_argument(
        "--output-stem",
        default="canonical_prev_close_sma_same_open_running_dd_uvix_bb20z_rsi_exit_low_rsi_tqqq_rsi_exit_from_20100212",
    )
    return parser.parse_args()


def as_float(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def read_by_date(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["Date"]: row for row in csv.DictReader(f)}


def compute_metrics(returns: list[float]) -> dict[str, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    safe_returns = [max(r, -0.999999) for r in returns]
    for daily_return in safe_returns:
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)

    mean = sum(safe_returns) / len(safe_returns)
    variance = sum((r - mean) ** 2 for r in safe_returns) / len(safe_returns)
    years = len(safe_returns) / TRADING_DAYS
    return {
        "cagr": equity ** (1.0 / years) - 1.0,
        "annualized_vol": math.sqrt(variance) * math.sqrt(TRADING_DAYS),
        "max_drawdown": max_drawdown,
        "final_multiple": equity,
    }


def required_float(row: dict[str, str], key: str) -> float | None:
    return as_float(row.get(key))


def main() -> None:
    args = parse_args()
    reference = read_by_date(args.reference_daily_path)
    ohlc = read_by_date(args.tqqq_tmf_gld_ohlc_path)
    uvix = read_by_date(args.uvix_ohlc_path)

    wait_total = args.wait_tmf + args.wait_gld
    if wait_total <= 0:
        raise ValueError("wait weights must sum to a positive value")
    wait_tmf_weight = args.wait_tmf / wait_total
    wait_gld_weight = args.wait_gld / wait_total

    def base_state(row: dict[str, str]) -> str:
        return "wait_mix" if row.get("base_target_regime_at_open") == "wait_mix" else "TQQQ"

    def close_to_open_return(state: str, market: dict[str, str], hedge: dict[str, str]) -> float:
        if state == "UVIX":
            return required_float(hedge, "UVIX_CTO_RETURN") or 0.0
        if state in {"TQQQ", "low_rsi_tqqq_override"}:
            return required_float(market, "TQQQ_CTO_RETURN") or 0.0
        tmf = required_float(market, "TMF_CTO_RETURN") or 0.0
        gld = required_float(market, "GLD_CTO_RETURN") or 0.0
        return wait_tmf_weight * tmf + wait_gld_weight * gld

    def open_to_close_return(state: str, market: dict[str, str], hedge: dict[str, str]) -> float:
        if state == "UVIX":
            return required_float(hedge, "UVIX_OTC_RETURN") or 0.0
        if state in {"TQQQ", "low_rsi_tqqq_override"}:
            return required_float(market, "TQQQ_OTC_RETURN") or 0.0
        tmf = required_float(market, "TMF_OTC_RETURN") or 0.0
        gld = required_float(market, "GLD_OTC_RETURN") or 0.0
        return wait_tmf_weight * tmf + wait_gld_weight * gld

    dates = sorted(date for date in reference if date >= args.backtest_start and date in ohlc and date in uvix)
    active_uvix = False
    active_low_rsi_override = False
    previous_state = base_state(reference[dates[0]])
    equity = 1.0
    returns: list[float] = []
    path: list[dict[str, str | float]] = []
    uvix_entries = 0
    uvix_exits = 0
    low_rsi_entries = 0
    low_rsi_exits = 0
    skipped_uvix_entry_days = 0

    for date in dates:
        ref = reference[date]
        market = ohlc[date]
        hedge = uvix[date]
        rsi = required_float(ref, "gspc_open_implied_rsi14")
        bb20_z = required_float(ref, "GSPC_BB20_Z")
        tqqq_open = required_float(ref, "TQQQ_OPEN")
        needed_returns = [
            required_float(market, "TQQQ_CTO_RETURN"),
            required_float(market, "TQQQ_OTC_RETURN"),
            required_float(market, "TMF_CTO_RETURN"),
            required_float(market, "TMF_OTC_RETURN"),
            required_float(market, "GLD_CTO_RETURN"),
            required_float(market, "GLD_OTC_RETURN"),
            required_float(hedge, "UVIX_CTO_RETURN"),
            required_float(hedge, "UVIX_OTC_RETURN"),
        ]
        if rsi is None or bb20_z is None or tqqq_open is None or any(v is None for v in needed_returns):
            continue

        target_state = base_state(ref)
        actions: list[str] = []
        skip_reason = ""

        if active_uvix and rsi <= args.uvix_exit_rsi:
            active_uvix = False
            uvix_exits += 1
            actions.append("exit_uvix")

        if active_low_rsi_override and rsi >= args.low_rsi_exit:
            active_low_rsi_override = False
            low_rsi_exits += 1
            actions.append("exit_low_rsi_tqqq_override")

        if not active_uvix and not active_low_rsi_override:
            if rsi >= args.uvix_entry_rsi:
                if bb20_z >= args.uvix_entry_min_bb_z:
                    active_uvix = True
                    uvix_entries += 1
                    target_state = "UVIX"
                    actions.append("enter_uvix_high_rsi_bb20z")
                else:
                    skipped_uvix_entry_days += 1
                    skip_reason = "skip_gspc_bb20_z_lt_1p60"
            elif rsi < args.low_rsi_entry and base_state(ref) == "wait_mix":
                active_low_rsi_override = True
                low_rsi_entries += 1
                target_state = "low_rsi_tqqq_override"
                actions.append("enter_low_rsi_tqqq_override")
        elif active_uvix:
            target_state = "UVIX"
        elif active_low_rsi_override:
            target_state = "low_rsi_tqqq_override"

        strategy_return = (1.0 + close_to_open_return(previous_state, market, hedge)) * (
            1.0 + open_to_close_return(target_state, market, hedge)
        ) - 1.0
        returns.append(strategy_return)
        equity *= 1.0 + max(strategy_return, -0.999999)
        path.append(
            {
                "Date": date,
                "gspc_open_implied_rsi14": rsi,
                "GSPC_BB20_Z": bb20_z,
                "TQQQ_OPEN": tqqq_open,
                "base_target_regime_at_open": ref.get("base_target_regime_at_open", ""),
                "selected_leg": target_state,
                "action": "|".join(actions),
                "skip_reason": skip_reason,
                "strategy_return": strategy_return,
                "strategy_equity": equity,
            }
        )
        previous_state = target_state

    if not returns:
        raise RuntimeError("no valid rows were simulated")

    metrics = compute_metrics(returns)
    uvix_days = sum(1 for row in path if row["selected_leg"] == "UVIX")
    low_rsi_days = sum(1 for row in path if row["selected_leg"] == "low_rsi_tqqq_override")
    metrics.update(
        {
            "start": args.backtest_start,
            "uvix_entry_rsi": args.uvix_entry_rsi,
            "uvix_entry_min_bb_z": args.uvix_entry_min_bb_z,
            "uvix_exit_rsi": args.uvix_exit_rsi,
            "uvix_exit_rule": "rsi_only",
            "low_rsi_entry": args.low_rsi_entry,
            "low_rsi_exit": args.low_rsi_exit,
            "uvix_entries": uvix_entries,
            "uvix_exits": uvix_exits,
            "skipped_uvix_entry_days": skipped_uvix_entry_days,
            "uvix_day_share": uvix_days / len(path),
            "low_rsi_entries": low_rsi_entries,
            "low_rsi_exits": low_rsi_exits,
            "low_rsi_day_share": low_rsi_days / len(path),
        }
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / f"{args.output_stem}_summary.csv"
    daily_path = OUTPUT_DIR / f"{args.output_stem}_daily_path.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    with daily_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(path[0]))
        writer.writeheader()
        writer.writerows(path)

    print(f"Saved: {summary_path}")
    print(f"Saved: {daily_path}")
    print(
        "Canonical BB20Z RSI-only exit: "
        f"CAGR={metrics['cagr'] * 100:.2f}%, "
        f"Vol={metrics['annualized_vol'] * 100:.2f}%, "
        f"MDD={metrics['max_drawdown'] * 100:.2f}%, "
        f"UVIX entries={uvix_entries}, exits={uvix_exits}"
    )


if __name__ == "__main__":
    main()
