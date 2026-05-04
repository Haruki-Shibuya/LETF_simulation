from __future__ import annotations

import csv
import json
import math
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import optimize_canonical_running_drawdown_from_2005 as base


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
TRADING_DAYS = 252
SOXL_ANNUAL_FEE = 0.0075
SOXL_SWITCH_DATE = "2021-08-25"
OUTPUT_STEM = (
    "canonical_sma160_anchor_n_le60_soxl_m_synthetic_ohlc_bb20z_gspc_profit_"
    "entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220"
)


def fetch_yahoo_chart(ticker: str, start: str, end: str | None = None) -> dict[str, dict[str, float]]:
    period1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    if end is None:
        period2 = int(datetime.now(timezone.utc).timestamp())
    else:
        period2 = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp()) + 24 * 60 * 60
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(ticker)}"
        f"?interval=1d&period1={period1}&period2={period2}&events=history"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    rows: dict[str, dict[str, float]] = {}
    for i, ts in enumerate(result["timestamp"]):
        open_price = quote["open"][i]
        close_price = quote["close"][i]
        if open_price is None or close_price is None:
            continue
        adj_close = adj[i] if i < len(adj) and adj[i] is not None else close_price
        factor = adj_close / close_price if close_price else 1.0
        date = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        rows[date] = {
            "open": float(open_price) * factor,
            "close": float(adj_close),
        }
    return rows


def fetch_fred_rate(start: str, end: str | None = None) -> dict[str, float]:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode("utf-8")
            break
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(2.0)
    rows: dict[str, float] = {}
    for row in csv.DictReader(text.splitlines()):
        date = row["observation_date"]
        if date < start or (end is not None and date > end):
            continue
        value = base.as_float(row["DGS3MO"])
        if value is not None:
            rows[date] = value / 100.0
    return rows


def ffill_rates(dates: list[str], raw_rates: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    last = 0.0
    for date in sorted(raw_rates):
        if date <= dates[0]:
            last = raw_rates[date]
        else:
            break
    for date in dates:
        if date in raw_rates:
            last = raw_rates[date]
        out[date] = last
    return out


def build_benchmark_ohlc(start: str) -> dict[str, dict[str, float]]:
    sox = fetch_yahoo_chart("^SOX", start)
    soxx = fetch_yahoo_chart("SOXX", start)
    dates = sorted(set(sox) | set(soxx))
    rows: dict[str, dict[str, float]] = {}
    for date in dates:
        source = soxx if date >= SOXL_SWITCH_DATE and date in soxx else sox
        if date not in source:
            continue
        rows[date] = source[date]
    return rows


def build_soxl_ohlc(start: str = "2004-01-01") -> tuple[dict[str, dict[str, str]], dict[str, float | str]]:
    benchmark = build_benchmark_ohlc(start)
    actual = fetch_yahoo_chart("SOXL", start)
    dates = sorted(benchmark)
    rates = ffill_rates(dates, fetch_fred_rate(start))

    bench_cc: dict[str, float] = {}
    bench_cto: dict[str, float] = {}
    prev_close: float | None = None
    for date in dates:
        row = benchmark[date]
        if prev_close is None:
            prev_close = row["close"]
            continue
        bench_cto[date] = row["open"] / prev_close - 1.0
        bench_cc[date] = row["close"] / prev_close - 1.0
        prev_close = row["close"]

    actual_cc: dict[str, float] = {}
    prev_actual_close: float | None = None
    for date in sorted(actual):
        row = actual[date]
        if prev_actual_close is not None:
            actual_cc[date] = row["close"] / prev_actual_close - 1.0
        prev_actual_close = row["close"]

    overlap = [date for date in sorted(actual_cc) if date in bench_cc and date in rates]
    best_multiplier = 0.0
    best_error = float("inf")
    for step in range(0, 1001):
        multiplier = step / 100.0
        error = 0.0
        count = 0
        for date in overlap:
            drag = SOXL_ANNUAL_FEE / TRADING_DAYS + multiplier * rates[date] / TRADING_DAYS
            modeled = max(3.0 * bench_cc[date] - drag, -0.999999)
            actual_return = max(actual_cc[date], -0.999999)
            error += (math.log1p(modeled) - math.log1p(actual_return)) ** 2
            count += 1
        if count and error / count < best_error:
            best_error = error / count
            best_multiplier = multiplier

    rows: dict[str, dict[str, str]] = {}
    synthetic_close = 1.0
    previous_output_close: float | None = None
    first_actual_date = min(actual) if actual else ""
    for date in dates:
        if date not in bench_cc or date not in bench_cto:
            continue
        if date in actual:
            actual_open = actual[date]["open"]
            actual_close = actual[date]["close"]
            cto = "" if previous_output_close is None else actual_open / previous_output_close - 1.0
            otc = actual_close / actual_open - 1.0
            output_open = actual_open
            output_close = actual_close
            source = "actual_soxl_adjusted_ohlc"
        else:
            drag = SOXL_ANNUAL_FEE / TRADING_DAYS + best_multiplier * rates.get(date, 0.0) / TRADING_DAYS
            cc = max(3.0 * bench_cc[date] - drag, -0.999999)
            cto_value = max(3.0 * bench_cto[date] - drag / 2.0, -0.999999)
            if 1.0 + cto_value <= 0:
                cto_value = -0.999999
            otc_value = (1.0 + cc) / (1.0 + cto_value) - 1.0
            output_open = synthetic_close * (1.0 + cto_value)
            output_close = synthetic_close * (1.0 + cc)
            synthetic_close = output_close
            cto = cto_value if previous_output_close is not None else ""
            otc = otc_value
            source = "synthetic_3x_semiconductor_ohlc_fee_financing"
        rows[date] = {
            "SOXL_OPEN": str(output_open),
            "SOXL_CLOSE": str(output_close),
            "SOXL_CTO_RETURN": "" if cto == "" else str(cto),
            "SOXL_OTC_RETURN": str(otc),
            "SOXL_SOURCE": source,
        }
        previous_output_close = output_close
    diagnostics = {
        "annual_fee": SOXL_ANNUAL_FEE,
        "financing_multiplier": best_multiplier,
        "overlap_days": len(overlap),
        "overlap_log_mse": best_error,
        "first_actual_soxl_date": first_actual_date,
        "benchmark_before_switch": "^SOX",
        "benchmark_after_switch": "SOXX",
        "switch_date": SOXL_SWITCH_DATE,
    }
    return rows, diagnostics


def load_inputs():
    dates, market, uvix, gspc_features = base.load_inputs()
    soxl, diagnostics = build_soxl_ohlc("2004-01-01")
    merged = {}
    for date, row in market.items():
        out = dict(row)
        if date in soxl:
            out.update(soxl[date])
        merged[date] = out
    dates = [
        date
        for date in dates
        if date in merged
        and base.as_float(merged[date].get("SOXL_CTO_RETURN")) is not None
        and base.as_float(merged[date].get("SOXL_OTC_RETURN")) is not None
    ]
    return dates, merged, uvix, gspc_features, diagnostics


def build_states(dates, market, gspc_features, n_tqqq_pct, m_soxl_pct):
    states = {}
    previous_below = False
    anchor = None
    in_tqqq = False
    in_soxl = False
    for date in sorted(market):
        tqqq_open = base.as_float(market[date].get("TQQQ_OPEN"))
        if tqqq_open is None or date not in gspc_features:
            continue
        below = gspc_features[date]["gspc_open"] < gspc_features[date]["gspc_sma160_prev_close"]
        if below and not previous_below:
            anchor = tqqq_open
            in_tqqq = False
            in_soxl = False
        if not below:
            anchor = None
            in_tqqq = False
            in_soxl = False
            dd = 0.0
            state = "TQQQ"
            tqqq_trigger = False
            soxl_trigger = False
        else:
            if anchor is None:
                anchor = tqqq_open
            dd = (1.0 - tqqq_open / anchor) * 100.0 if anchor > 0 else 0.0
            tqqq_trigger = dd >= n_tqqq_pct
            soxl_trigger = dd >= m_soxl_pct
            if in_soxl or soxl_trigger:
                in_soxl = True
                in_tqqq = True
                state = "SOXL"
            elif in_tqqq or tqqq_trigger:
                in_tqqq = True
                state = "TQQQ"
            else:
                state = "wait_mix"
        previous_below = below
        if date in dates:
            states[date] = {
                "base": state,
                "signal_below_sma": below,
                "tqqq_sma160_anchor_drawdown_pct": dd,
                "tqqq_drawdown_trigger": tqqq_trigger,
                "soxl_drawdown_trigger": soxl_trigger,
            }
    return states


def compute_base_counts(states):
    counts = {
        "below_sma_periods": 0,
        "tqqq_triggered_periods": 0,
        "soxl_triggered_periods": 0,
        "base_wait_days": 0,
        "base_tqqq_days": 0,
        "base_soxl_days": 0,
    }
    in_below = False
    saw_tqqq = False
    saw_soxl = False
    for date in sorted(states):
        row = states[date]
        below = bool(row["signal_below_sma"])
        if below and not in_below:
            counts["below_sma_periods"] += 1
            saw_tqqq = False
            saw_soxl = False
        if below:
            if row["tqqq_drawdown_trigger"] and not saw_tqqq:
                counts["tqqq_triggered_periods"] += 1
                saw_tqqq = True
            if row["soxl_drawdown_trigger"] and not saw_soxl:
                counts["soxl_triggered_periods"] += 1
                saw_soxl = True
        state = row["base"]
        if state == "wait_mix":
            counts["base_wait_days"] += 1
        elif state == "TQQQ":
            counts["base_tqqq_days"] += 1
        elif state == "SOXL":
            counts["base_soxl_days"] += 1
        in_below = below
    return counts


def simulate(dates, market, uvix, gspc_features, n_tqqq_pct, m_soxl_pct, keep_path=False):
    states = build_states(dates, market, gspc_features, n_tqqq_pct, m_soxl_pct)
    usable_dates = [date for date in dates if date in states]

    def cto(state, market_row, uvix_row):
        if state == "UVIX":
            return base.market_float(uvix_row, "UVIX_CTO_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_priority"}:
            return base.market_float(market_row, "TQQQ_CTO_RETURN")
        if state == "SOXL":
            return base.market_float(market_row, "SOXL_CTO_RETURN")
        return 0.5 * base.market_float(market_row, "TMF_CTO_RETURN") + 0.5 * base.market_float(market_row, "GLD_CTO_RETURN")

    def otc(state, market_row, uvix_row):
        if state == "UVIX":
            return base.market_float(uvix_row, "UVIX_OTC_RETURN")
        if state in {"TQQQ", "low_rsi_tqqq_priority"}:
            return base.market_float(market_row, "TQQQ_OTC_RETURN")
        if state == "SOXL":
            return base.market_float(market_row, "SOXL_OTC_RETURN")
        return 0.5 * base.market_float(market_row, "TMF_OTC_RETURN") + 0.5 * base.market_float(market_row, "GLD_OTC_RETURN")

    active_uvix = False
    active_low = False
    uvix_entry_gspc = None
    previous_state = str(states[usable_dates[0]]["base"])
    returns = []
    path = []
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
        uvix_row = uvix[date]
        feat = gspc_features[date]
        base_state = str(states[date]["base"])
        rsi = feat["gspc_open_implied_rsi14"]
        z = feat["GSPC_BB20_Z"]
        gspc_open = feat["gspc_open"]
        target = base_state
        actions = []
        if active_uvix:
            assert uvix_entry_gspc is not None
            rsi_exit = rsi <= base.UVIX_EXIT_RSI
            gspc_exit = gspc_open <= uvix_entry_gspc * (1.0 + base.UVIX_GSPC_PROFIT_EXIT_PCT / 100.0)
            if rsi_exit or gspc_exit:
                active_uvix = False
                uvix_entry_gspc = None
                counts["uvix_exits"] += 1
                if rsi_exit and gspc_exit:
                    counts["uvix_rsi_and_gspc_profit_exit"] += 1
                elif rsi_exit:
                    counts["uvix_rsi_exit_only"] += 1
                else:
                    counts["uvix_gspc_profit_exit_only"] += 1
                actions.append("exit_uvix")
            else:
                target = "UVIX"
        elif active_low:
            if rsi >= base.LOW_RSI_EXIT:
                active_low = False
                counts["low_rsi_exits"] += 1
                actions.append("exit_low_rsi_tqqq_priority")
            else:
                target = "low_rsi_tqqq_priority"
        else:
            if rsi >= base.UVIX_ENTRY_RSI:
                if z >= base.UVIX_ENTRY_MIN_BB_Z:
                    active_uvix = True
                    uvix_entry_gspc = gspc_open
                    target = "UVIX"
                    counts["uvix_entries"] += 1
                    actions.append("enter_uvix_high_rsi_bb20z")
                else:
                    counts["skipped_uvix_entry_days"] += 1
            elif rsi < base.LOW_RSI_ENTRY and base_state == "wait_mix":
                active_low = True
                target = "low_rsi_tqqq_priority"
                counts["low_rsi_entries"] += 1
                actions.append("enter_low_rsi_tqqq_priority")
        daily_return = (1.0 + cto(previous_state, market_row, uvix_row)) * (1.0 + otc(target, market_row, uvix_row)) - 1.0
        returns.append(daily_return)
        equity *= 1.0 + max(daily_return, -0.999999)
        if keep_path:
            row = {
                "Date": date,
                "n_tqqq_pct": n_tqqq_pct,
                "m_soxl_pct": m_soxl_pct,
                "gspc_open_implied_rsi14": rsi,
                "GSPC_BB20_Z": z,
                "GSPC_OPEN": gspc_open,
                "TQQQ_OPEN": market_row["TQQQ_OPEN"],
                "SOXL_OPEN": market_row["SOXL_OPEN"],
                **states[date],
                "base_target_regime_at_open": base_state,
                "selected_leg": target,
                "action": "|".join(actions),
                "strategy_return": daily_return,
                "strategy_equity": equity,
                "SOXL_SOURCE": market_row.get("SOXL_SOURCE", ""),
            }
            path.append(row)
        previous_state = target
    metrics = base.compute_metrics(returns)
    metrics.update(counts)
    metrics.update(compute_base_counts(states))
    metrics["start"] = usable_dates[0]
    metrics["end"] = usable_dates[-1]
    metrics["n_tqqq_pct"] = n_tqqq_pct
    metrics["m_soxl_pct"] = m_soxl_pct
    metrics["uvix_entry_rsi"] = base.UVIX_ENTRY_RSI
    metrics["uvix_exit_rsi"] = base.UVIX_EXIT_RSI
    metrics["uvix_entry_min_bb_z"] = base.UVIX_ENTRY_MIN_BB_Z
    metrics["uvix_gspc_profit_exit_pct"] = base.UVIX_GSPC_PROFIT_EXIT_PCT
    metrics["low_rsi_entry"] = base.LOW_RSI_ENTRY
    metrics["low_rsi_exit"] = base.LOW_RSI_EXIT
    metrics["base_reentry_rule"] = "sma160_break_anchor_tqqq_n_then_soxl_m_until_sma160_recovery"
    metrics["transition_policy"] = "one_open_transition_per_day"
    return metrics, path


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    dates, market, uvix, gspc_features, diagnostics = load_inputs()
    grid = []
    for n_step in range(0, 121):
        n = round(n_step * 0.5, 1)
        for m_step in range(0, 200):
            m = round(m_step * 0.5, 1)
            if m < n:
                continue
            metrics, _ = simulate(dates, market, uvix, gspc_features, n, m, keep_path=False)
            metrics.update(diagnostics)
            grid.append(metrics)
    top = sorted(grid, key=lambda row: row["cagr"], reverse=True)
    best = top[0]
    best_metrics, best_path = simulate(dates, market, uvix, gspc_features, best["n_tqqq_pct"], best["m_soxl_pct"], keep_path=True)
    best_metrics.update(diagnostics)
    prefix = OUTPUT_DIR / f"{OUTPUT_STEM}_n0to60_mgeqn_step0p5"
    write_csv(Path(f"{prefix}_grid.csv"), sorted(grid, key=lambda row: (row["n_tqqq_pct"], row["m_soxl_pct"])))
    write_csv(Path(f"{prefix}_top20.csv"), top[:20])
    write_csv(Path(f"{prefix}_summary.csv"), [best_metrics])
    write_csv(Path(f"{prefix}_daily_path.csv"), best_path)
    soxl_rows = [
        {
            "Date": date,
            "SOXL_OPEN": market[date].get("SOXL_OPEN", ""),
            "SOXL_CLOSE": market[date].get("SOXL_CLOSE", ""),
            "SOXL_CTO_RETURN": market[date].get("SOXL_CTO_RETURN", ""),
            "SOXL_OTC_RETURN": market[date].get("SOXL_OTC_RETURN", ""),
            "SOXL_SOURCE": market[date].get("SOXL_SOURCE", ""),
        }
        for date in dates
    ]
    write_csv(OUTPUT_DIR / "soxl_synthetic_ohlc_fee_financing_for_canonical_from_2005.csv", soxl_rows)
    print(
        f"Best n={best_metrics['n_tqqq_pct']:.1f}% m={best_metrics['m_soxl_pct']:.1f}% "
        f"CAGR={best_metrics['cagr']*100:.2f}% MDD={best_metrics['max_drawdown']*100:.2f}% "
        f"TQQQ periods={best_metrics['tqqq_triggered_periods']} SOXL periods={best_metrics['soxl_triggered_periods']} "
        f"start={best_metrics['start']} fee={SOXL_ANNUAL_FEE:.2%} financing_multiplier={diagnostics['financing_multiplier']:.2f}"
    )


if __name__ == "__main__":
    main()
