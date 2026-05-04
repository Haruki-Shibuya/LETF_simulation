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

BASE_DAILY_PATH = (
    OUTPUT_DIR
    / "tecl_sma160_gspc_above_tecl100_tqqq0_wait_tmf50_gld50_below_soxl0_tecl0_tqqq100_"
    "crossunder_price_drawdown_ref_tecl_enterdown_41p5_from_20020101_daily_path.csv"
)
TQQQ_TMF_GLD_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
GSPC_OHLC_PATH = OUTPUT_DIR / "gspc_actual_ohlc_for_soxl_sma200_exit.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"

BACKTEST_START = "2005-12-20"
UVIX_ENTRY_RSI = 67.5
UVIX_ENTRY_MIN_BB_Z = 1.6
UVIX_EXIT_RSI = 66.0
UVIX_GSPC_PROFIT_EXIT_PCT = 0.1
LOW_RSI_ENTRY = 30.0
LOW_RSI_EXIT = 32.5
OUTPUT_STEM = (
    "canonical_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220"
)


def as_float(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


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
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    rows: dict[str, dict[str, str]] = {}
    for i, ts in enumerate(timestamps):
        open_price = quote["open"][i]
        close_price = quote["close"][i]
        if open_price is None or close_price is None:
            continue
        date = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        rows[date] = {
            "Date": date,
            "GSPC_OPEN": str(open_price),
            "GSPC_CLOSE": str(close_price),
        }
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
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / len(window)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (open_price - mean) / std


def build_gspc_features(rows: dict[str, dict[str, str]]) -> dict[str, tuple[float | None, float | None, float]]:
    closes: list[float] = []
    features: dict[str, tuple[float | None, float | None, float]] = {}
    for date in sorted(rows):
        open_price = as_float(rows[date].get("GSPC_OPEN"))
        close_price = as_float(rows[date].get("GSPC_CLOSE"))
        if open_price is None or close_price is None:
            continue
        features[date] = (rsi_wilder(closes + [open_price]), bb20_z(closes, open_price), open_price)
        closes.append(close_price)
    return features


def compute_metrics(returns: list[float]) -> dict[str, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_return in returns:
        equity *= 1.0 + max(daily_return, -0.999999)
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    years = len(returns) / TRADING_DAYS
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return {
        "cagr": equity ** (1.0 / years) - 1.0,
        "annualized_vol": math.sqrt(variance) * math.sqrt(TRADING_DAYS),
        "max_drawdown": max_drawdown,
        "final_multiple": equity,
    }


def base_state(row: dict[str, str]) -> str:
    return "wait_mix" if row.get("target_regime") == "wait_mix" else "TQQQ"


def market_float(row: dict[str, str], key: str) -> float:
    value = as_float(row.get(key))
    if value is None:
        raise ValueError(f"missing numeric value for {key}")
    return value


def main() -> None:
    base = read_by_date(BASE_DAILY_PATH)
    market_ohlc = read_by_date(TQQQ_TMF_GLD_OHLC_PATH)
    uvix = read_by_date(UVIX_OHLC_PATH)
    gspc = {**fetch_gspc_ohlc("2004-11-01", "2009-01-02"), **read_by_date(GSPC_OHLC_PATH)}
    gspc_features = build_gspc_features(gspc)

    dates = sorted(
        date
        for date in base
        if date >= BACKTEST_START and date in market_ohlc and date in uvix and date in gspc_features
    )
    if not dates:
        raise RuntimeError("no overlapping dates found")

    def close_to_open_return(state: str, market: dict[str, str], hedge: dict[str, str]) -> float:
        if state == "UVIX":
            return market_float(hedge, "UVIX_CTO_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_override"}:
            return market_float(market, "TQQQ_CTO_RETURN")
        return 0.5 * market_float(market, "TMF_CTO_RETURN") + 0.5 * market_float(market, "GLD_CTO_RETURN")

    def open_to_close_return(state: str, market: dict[str, str], hedge: dict[str, str]) -> float:
        if state == "UVIX":
            return market_float(hedge, "UVIX_OTC_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_override"}:
            return market_float(market, "TQQQ_OTC_RETURN")
        return 0.5 * market_float(market, "TMF_OTC_RETURN") + 0.5 * market_float(market, "GLD_OTC_RETURN")

    active_uvix = False
    active_low_rsi_override = False
    uvix_entry_gspc_open: float | None = None
    previous_state = base_state(base[dates[0]])
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

    for date in dates:
        market = market_ohlc[date]
        hedge = uvix[date]
        rsi, z_score, gspc_open = gspc_features[date]
        tqqq_open = as_float(market.get("TQQQ_OPEN"))
        required = [
            rsi,
            z_score,
            gspc_open,
            tqqq_open,
            as_float(market.get("TQQQ_CTO_RETURN")),
            as_float(market.get("TQQQ_OTC_RETURN")),
            as_float(market.get("TMF_CTO_RETURN")),
            as_float(market.get("TMF_OTC_RETURN")),
            as_float(market.get("GLD_CTO_RETURN")),
            as_float(market.get("GLD_OTC_RETURN")),
            as_float(hedge.get("UVIX_CTO_RETURN")),
            as_float(hedge.get("UVIX_OTC_RETURN")),
        ]
        if any(value is None for value in required):
            continue

        target_state = base_state(base[date])
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
        elif active_low_rsi_override:
            if rsi >= LOW_RSI_EXIT:
                active_low_rsi_override = False
                counts["low_rsi_exits"] += 1
                actions.append("exit_low_rsi_tqqq_override")
            else:
                target_state = "low_rsi_tqqq_override"
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
            elif rsi < LOW_RSI_ENTRY and base_state(base[date]) == "wait_mix":
                active_low_rsi_override = True
                target_state = "low_rsi_tqqq_override"
                counts["low_rsi_entries"] += 1
                actions.append("enter_low_rsi_tqqq_override")

        strategy_return = (1.0 + close_to_open_return(previous_state, market, hedge)) * (
            1.0 + open_to_close_return(target_state, market, hedge)
        ) - 1.0
        returns.append(strategy_return)
        equity *= 1.0 + max(strategy_return, -0.999999)
        path.append(
            {
                "Date": date,
                "gspc_open_implied_rsi14": rsi,
                "GSPC_BB20_Z": z_score,
                "GSPC_OPEN": gspc_open,
                "TQQQ_OPEN": tqqq_open,
                "base_target_regime_at_open": base_state(base[date]),
                "selected_leg": target_state,
                "action": "|".join(actions),
                "skip_reason": skip_reason,
                "strategy_return": strategy_return,
                "strategy_equity": equity,
            }
        )
        previous_state = target_state

    metrics = compute_metrics(returns)
    uvix_days = sum(1 for row in path if row["selected_leg"] == "UVIX")
    low_rsi_days = sum(1 for row in path if row["selected_leg"] == "low_rsi_tqqq_override")
    metrics.update(
        {
            "start": BACKTEST_START,
            "end": path[-1]["Date"],
            "uvix_entry_rsi": UVIX_ENTRY_RSI,
            "uvix_entry_min_bb_z": UVIX_ENTRY_MIN_BB_Z,
            "uvix_exit_rsi": UVIX_EXIT_RSI,
            "uvix_gspc_profit_exit_pct": UVIX_GSPC_PROFIT_EXIT_PCT,
            "low_rsi_entry": LOW_RSI_ENTRY,
            "low_rsi_exit": LOW_RSI_EXIT,
            **counts,
            "uvix_day_share": uvix_days / len(path),
            "low_rsi_day_share": low_rsi_days / len(path),
            "transition_policy": "one_open_transition_per_day",
            "base_daily_path": str(BASE_DAILY_PATH.relative_to(REPO_DIR)),
            "gspc_2005_2008_source": "Yahoo Finance ^GSPC daily OHLC fetched at build time",
        }
    )

    summary_path = OUTPUT_DIR / f"{OUTPUT_STEM}_summary.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_STEM}_daily_path.csv"
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
        "Canonical 2005 BB20Z + GSPC profit exit: "
        f"CAGR={metrics['cagr'] * 100:.2f}%, "
        f"MDD={metrics['max_drawdown'] * 100:.2f}%, "
        f"UVIX entries={counts['uvix_entries']}, exits={counts['uvix_exits']}"
    )


if __name__ == "__main__":
    main()
