from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

TQQQ_TMF_GLD_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
GSPC_OHLC_PATH = OUTPUT_DIR / "gspc_actual_ohlc_for_soxl_sma200_exit.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"

BACKTEST_START = "2005-12-20"
FETCH_GSPC_START = "2004-01-01"
FETCH_GSPC_END = "2009-01-02"
SMA_WINDOW = 160
UVIX_ENTRY_RSI = 67.5
UVIX_ENTRY_MIN_BB_Z = 1.6
UVIX_EXIT_RSI = 66.0
UVIX_GSPC_PROFIT_EXIT_PCT = 0.1
LOW_RSI_ENTRY = 30.0
LOW_RSI_EXIT = 32.5
OUTPUT_STEM = "canonical_running_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220"


def as_float(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def read_by_date(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["Date"]: row for row in csv.DictReader(f)}


def fetch_gspc_ohlc(start: str, end: str) -> dict[str, dict[str, str]]:
    period1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp()) + 24 * 60 * 60
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
        f"?interval=1d&period1={period1}&period2={period2}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    rows: dict[str, dict[str, str]] = {}
    for i, ts in enumerate(result["timestamp"]):
        quote = result["indicators"]["quote"][0]
        open_price = quote["open"][i]
        close_price = quote["close"][i]
        if open_price is None or close_price is None:
            continue
        date = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        rows[date] = {"Date": date, "GSPC_OPEN": str(open_price), "GSPC_CLOSE": str(close_price)}
    return rows


def rsi_wilder(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, current in zip(values, values[1:]):
        delta = current - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def bb20_z(previous_closes: list[float], open_price: float) -> float | None:
    window = previous_closes[-20:]
    if len(window) < 20:
        return None
    mean = sum(window) / 20
    variance = sum((value - mean) ** 2 for value in window) / 20
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (open_price - mean) / std


def build_gspc_features(rows: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    closes: list[float] = []
    features: dict[str, dict[str, float]] = {}
    for date in sorted(rows):
        open_price = as_float(rows[date].get("GSPC_OPEN"))
        close_price = as_float(rows[date].get("GSPC_CLOSE"))
        if open_price is None or close_price is None:
            continue
        sma160_prev = sum(closes[-SMA_WINDOW:]) / SMA_WINDOW if len(closes) >= SMA_WINDOW else None
        rsi = rsi_wilder(closes + [open_price])
        z_score = bb20_z(closes, open_price)
        if sma160_prev is not None and rsi is not None and z_score is not None:
            features[date] = {
                "gspc_open": open_price,
                "gspc_close": close_price,
                "gspc_sma160_prev_close": sma160_prev,
                "gspc_open_implied_rsi14": rsi,
                "GSPC_BB20_Z": z_score,
            }
        closes.append(close_price)
    return features


def market_float(row: dict[str, str], key: str) -> float:
    value = as_float(row.get(key))
    if value is None:
        raise ValueError(f"missing numeric value for {key}")
    return value


def compute_metrics(returns: list[float]) -> dict[str, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    safe_returns = [max(r, -0.999999) for r in returns]
    for daily_return in safe_returns:
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    years = len(safe_returns) / TRADING_DAYS
    mean = sum(safe_returns) / len(safe_returns)
    variance = sum((r - mean) ** 2 for r in safe_returns) / len(safe_returns)
    return {
        "cagr": equity ** (1.0 / years) - 1.0,
        "annualized_vol": math.sqrt(variance) * math.sqrt(TRADING_DAYS),
        "max_drawdown": max_drawdown,
        "final_multiple": equity,
    }


def load_inputs() -> tuple[list[str], dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, float]]]:
    market = read_by_date(TQQQ_TMF_GLD_OHLC_PATH)
    uvix = read_by_date(UVIX_OHLC_PATH)
    gspc = {**fetch_gspc_ohlc(FETCH_GSPC_START, FETCH_GSPC_END), **read_by_date(GSPC_OHLC_PATH)}
    gspc_features = build_gspc_features(gspc)
    dates = sorted(date for date in market if date >= BACKTEST_START and date in uvix and date in gspc_features)
    return dates, market, uvix, gspc_features


def build_base_states(
    dates: list[str],
    market: dict[str, dict[str, str]],
    gspc_features: dict[str, dict[str, float]],
    alpha_drawdown_pct: float,
) -> dict[str, dict[str, float | str | bool]]:
    # The running peak must include pre-backtest synthetic TQQQ history so drawdown at 2005 start is not reset.
    tqqq_peak = 0.0
    in_reentry = False
    states: dict[str, dict[str, float | str | bool]] = {}
    for date in sorted(market):
        tqqq_open = as_float(market[date].get("TQQQ_OPEN"))
        if tqqq_open is None:
            continue
        tqqq_peak = max(tqqq_peak, tqqq_open)
        if date not in gspc_features:
            continue
        feat = gspc_features[date]
        below_sma = feat["gspc_open"] < feat["gspc_sma160_prev_close"]
        drawdown_pct = (1.0 - tqqq_open / tqqq_peak) * 100.0 if tqqq_peak > 0 else 0.0
        triggered = below_sma and drawdown_pct >= alpha_drawdown_pct
        if not below_sma:
            in_reentry = False
            base = "TQQQ"
        elif in_reentry or triggered:
            in_reentry = True
            base = "TQQQ"
        else:
            base = "wait_mix"
        if date in dates:
            states[date] = {
                "base": base,
                "signal_below_sma": below_sma,
                "tqqq_peak_open": tqqq_peak,
                "tqqq_running_drawdown_pct": drawdown_pct,
                "drawdown_trigger": triggered,
            }
    return states


def simulate(
    dates: list[str],
    market: dict[str, dict[str, str]],
    uvix: dict[str, dict[str, str]],
    gspc_features: dict[str, dict[str, float]],
    alpha_drawdown_pct: float,
    keep_path: bool = False,
) -> tuple[dict[str, float], list[dict[str, str | float]]]:
    base_states = build_base_states(dates, market, gspc_features, alpha_drawdown_pct)

    def close_to_open_return(state: str, market_row: dict[str, str], hedge_row: dict[str, str]) -> float:
        if state == "UVIX":
            return market_float(hedge_row, "UVIX_CTO_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_priority"}:
            return market_float(market_row, "TQQQ_CTO_RETURN")
        return 0.5 * market_float(market_row, "TMF_CTO_RETURN") + 0.5 * market_float(market_row, "GLD_CTO_RETURN")

    def open_to_close_return(state: str, market_row: dict[str, str], hedge_row: dict[str, str]) -> float:
        if state == "UVIX":
            return market_float(hedge_row, "UVIX_OTC_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_priority"}:
            return market_float(market_row, "TQQQ_OTC_RETURN")
        return 0.5 * market_float(market_row, "TMF_OTC_RETURN") + 0.5 * market_float(market_row, "GLD_OTC_RETURN")

    usable_dates = [date for date in dates if date in base_states]
    active_uvix = False
    active_low_rsi_priority = False
    uvix_entry_gspc_open: float | None = None
    previous_state = str(base_states[usable_dates[0]]["base"])
    returns: list[float] = []
    path: list[dict[str, str | float]] = []
    equity = 1.0
    counts = {
        "uvix_entries": 0,
        "uvix_exits": 0,
        "uvix_gspc_profit_exit_only": 0,
        "uvix_rsi_exit_only": 0,
        "uvix_rsi_and_gspc_profit_exit": 0,
        "low_rsi_entries": 0,
        "low_rsi_exits": 0,
        "skipped_uvix_entry_days": 0,
    }

    for date in usable_dates:
        market_row = market[date]
        hedge_row = uvix[date]
        feat = gspc_features[date]
        base = str(base_states[date]["base"])
        rsi = feat["gspc_open_implied_rsi14"]
        z_score = feat["GSPC_BB20_Z"]
        gspc_open = feat["gspc_open"]
        tqqq_open = as_float(market_row.get("TQQQ_OPEN"))
        required = [
            tqqq_open,
            as_float(market_row.get("TQQQ_CTO_RETURN")),
            as_float(market_row.get("TQQQ_OTC_RETURN")),
            as_float(market_row.get("TMF_CTO_RETURN")),
            as_float(market_row.get("TMF_OTC_RETURN")),
            as_float(market_row.get("GLD_CTO_RETURN")),
            as_float(market_row.get("GLD_OTC_RETURN")),
            as_float(hedge_row.get("UVIX_CTO_RETURN")),
            as_float(hedge_row.get("UVIX_OTC_RETURN")),
        ]
        if any(value is None for value in required):
            continue

        target_state = base
        actions: list[str] = []
        skip_reason = ""
        if active_uvix:
            assert uvix_entry_gspc_open is not None
            rsi_exit = rsi <= UVIX_EXIT_RSI
            gspc_profit_exit = gspc_open <= uvix_entry_gspc_open * (1.0 + UVIX_GSPC_PROFIT_EXIT_PCT / 100.0)
            if rsi_exit or gspc_profit_exit:
                active_uvix = False
                uvix_entry_gspc_open = None
                counts["uvix_exits"] += 1
                if rsi_exit and gspc_profit_exit:
                    counts["uvix_rsi_and_gspc_profit_exit"] += 1
                    actions.append("exit_uvix_rsi_and_gspc_profit")
                elif rsi_exit:
                    counts["uvix_rsi_exit_only"] += 1
                    actions.append("exit_uvix_rsi")
                else:
                    counts["uvix_gspc_profit_exit_only"] += 1
                    actions.append("exit_uvix_gspc_profit")
            else:
                target_state = "UVIX"
        elif active_low_rsi_priority:
            if rsi >= LOW_RSI_EXIT:
                active_low_rsi_priority = False
                counts["low_rsi_exits"] += 1
                actions.append("exit_low_rsi_tqqq_priority")
            else:
                target_state = "low_rsi_tqqq_priority"
        else:
            if rsi >= UVIX_ENTRY_RSI:
                if z_score >= UVIX_ENTRY_MIN_BB_Z:
                    active_uvix = True
                    uvix_entry_gspc_open = gspc_open
                    target_state = "UVIX"
                    counts["uvix_entries"] += 1
                    actions.append("enter_uvix_high_rsi_bb20z")
                else:
                    counts["skipped_uvix_entry_days"] += 1
                    skip_reason = "skip_gspc_bb20_z_lt_1p60"
            elif rsi < LOW_RSI_ENTRY and base == "wait_mix":
                active_low_rsi_priority = True
                target_state = "low_rsi_tqqq_priority"
                counts["low_rsi_entries"] += 1
                actions.append("enter_low_rsi_tqqq_priority")

        strategy_return = (1.0 + close_to_open_return(previous_state, market_row, hedge_row)) * (
            1.0 + open_to_close_return(target_state, market_row, hedge_row)
        ) - 1.0
        returns.append(strategy_return)
        equity *= 1.0 + max(strategy_return, -0.999999)
        if keep_path:
            path.append(
                {
                    "Date": date,
                    "gspc_open_implied_rsi14": rsi,
                    "GSPC_BB20_Z": z_score,
                    "GSPC_OPEN": gspc_open,
                    "GSPC_SMA160_PREV_CLOSE": feat["gspc_sma160_prev_close"],
                    "TQQQ_OPEN": tqqq_open,
                    "TQQQ_PEAK_OPEN": base_states[date]["tqqq_peak_open"],
                    "TQQQ_RUNNING_DRAWDOWN_PCT": base_states[date]["tqqq_running_drawdown_pct"],
                    "DRAWDOWN_ALPHA_PCT": alpha_drawdown_pct,
                    "signal_below_sma": base_states[date]["signal_below_sma"],
                    "drawdown_trigger": base_states[date]["drawdown_trigger"],
                    "base_target_regime_at_open": base,
                    "selected_leg": target_state,
                    "action": "|".join(actions),
                    "skip_reason": skip_reason,
                    "strategy_return": strategy_return,
                    "strategy_equity": equity,
                }
            )
        previous_state = target_state

    metrics = compute_metrics(returns)
    metrics.update(counts)
    metrics["start"] = BACKTEST_START
    metrics["end"] = usable_dates[-1]
    metrics["alpha_drawdown_pct"] = alpha_drawdown_pct
    metrics["uvix_entry_rsi"] = UVIX_ENTRY_RSI
    metrics["uvix_entry_min_bb_z"] = UVIX_ENTRY_MIN_BB_Z
    metrics["uvix_exit_rsi"] = UVIX_EXIT_RSI
    metrics["uvix_gspc_profit_exit_pct"] = UVIX_GSPC_PROFIT_EXIT_PCT
    metrics["low_rsi_entry"] = LOW_RSI_ENTRY
    metrics["low_rsi_exit"] = LOW_RSI_EXIT
    metrics["uvix_day_share"] = sum(1 for row in path if row.get("selected_leg") == "UVIX") / len(path) if path else 0.0
    metrics["low_rsi_day_share"] = (
        sum(1 for row in path if row.get("selected_leg") == "low_rsi_tqqq_priority") / len(path) if path else 0.0
    )
    metrics["base_reentry_rule"] = "tqqq_open_running_drawdown_from_peak"
    metrics["transition_policy"] = "one_open_transition_per_day"
    return metrics, path


def main() -> None:
    dates, market, uvix, gspc_features = load_inputs()
    grid: list[dict[str, float]] = []
    alpha_values = [round(i * 0.5, 1) for i in range(0, 200)]
    for alpha in alpha_values:
        metrics, _ = simulate(dates, market, uvix, gspc_features, alpha, keep_path=False)
        grid.append(metrics)
    grid.sort(key=lambda row: row["cagr"], reverse=True)
    best_alpha = float(grid[0]["alpha_drawdown_pct"])
    best_metrics, best_path = simulate(dates, market, uvix, gspc_features, best_alpha, keep_path=True)

    grid_path = OUTPUT_DIR / f"{OUTPUT_STEM}_alpha0to99p5step0p5_grid.csv"
    top20_path = OUTPUT_DIR / f"{OUTPUT_STEM}_alpha0to99p5step0p5_top20.csv"
    summary_path = OUTPUT_DIR / f"{OUTPUT_STEM}_summary.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_STEM}_daily_path.csv"

    with grid_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(grid[0]))
        writer.writeheader()
        writer.writerows(sorted(grid, key=lambda row: row["alpha_drawdown_pct"]))
    with top20_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(grid[0]))
        writer.writeheader()
        writer.writerows(grid[:20])
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(best_metrics))
        writer.writeheader()
        writer.writerow(best_metrics)
    with daily_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(best_path[0]))
        writer.writeheader()
        writer.writerows(best_path)

    print(f"Saved: {grid_path}")
    print(f"Saved: {top20_path}")
    print(f"Saved: {summary_path}")
    print(f"Saved: {daily_path}")
    print(
        "Best running drawdown canonical: "
        f"alpha={best_alpha:.1f}%, "
        f"CAGR={best_metrics['cagr'] * 100:.2f}%, "
        f"MDD={best_metrics['max_drawdown'] * 100:.2f}%, "
        f"UVIX entries={int(best_metrics['uvix_entries'])}"
    )


if __name__ == "__main__":
    main()
