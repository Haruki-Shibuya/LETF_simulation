#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
MARKET_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
GSPC_PATH = OUTPUT_DIR / "gspc_actual_ohlc_for_soxl_sma200_exit.csv"
UVIX_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"

BACKTEST_START = "2010-02-12"
TRADING_DAYS = 252
SMA_WINDOW = 160
RSI_WINDOW = 14

PARAM_NAMES = [
    "alpha_drawdown_pct",
    "gspc_exit_gamma_pct",
    "uvix_entry_rsi",
    "uvix_exit_rsi",
    "bb_window_days",
    "bb_z_threshold",
    "low_rsi_entry",
    "low_rsi_exit",
]

BOUNDS = np.array(
    [
        [35.0, 46.0],  # alpha_drawdown_pct
        [0.0, 1.2],    # gspc_exit_gamma_pct
        [65.0, 68.0],  # uvix_entry_rsi
        [45.0, 66.0],  # uvix_exit_rsi
        [10.0, 20.0],  # bb_window_days, rounded to int
        [0.9, 1.6],    # bb_z_threshold
        [28.0, 32.0],  # low_rsi_entry
        [30.0, 40.0],  # low_rsi_exit
    ],
    dtype=float,
)

CANONICAL = np.array([40.5, 0.1, 67.5, 66.0, 20.0, 1.6, 30.0, 32.5], dtype=float)


def as_float(value: str | None) -> float:
    if value in {None, ""}:
        return math.nan
    try:
        number = float(value)
    except ValueError:
        return math.nan
    return number if math.isfinite(number) else math.nan


def read_csv_by_date(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["Date"]: row for row in csv.DictReader(f)}


def rsi_wilder(values: list[float], period: int = RSI_WINDOW) -> float:
    if len(values) <= period:
        return math.nan
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


@dataclass
class Inputs:
    dates: list[str]
    gspc_open: np.ndarray
    gspc_sma160_prev: np.ndarray
    rsi: np.ndarray
    bb_z_by_window: dict[int, np.ndarray]
    tqqq_open: np.ndarray
    tqqq_cto: np.ndarray
    tqqq_otc: np.ndarray
    tmf_cto: np.ndarray
    tmf_otc: np.ndarray
    gld_cto: np.ndarray
    gld_otc: np.ndarray
    uvix_cto: np.ndarray
    uvix_otc: np.ndarray


def load_inputs() -> Inputs:
    market = read_csv_by_date(MARKET_PATH)
    gspc = read_csv_by_date(GSPC_PATH)
    uvix = read_csv_by_date(UVIX_PATH)

    all_dates = sorted(set(market) & set(gspc) & set(uvix))
    closes: list[float] = []
    feature_rows: dict[str, dict[str, float]] = {}
    for d in sorted(gspc):
        op = as_float(gspc[d].get("GSPC_OPEN"))
        cl = as_float(gspc[d].get("GSPC_CLOSE"))
        if math.isnan(op) or math.isnan(cl):
            continue
        sma = sum(closes[-SMA_WINDOW:]) / SMA_WINDOW if len(closes) >= SMA_WINDOW else math.nan
        rsi = rsi_wilder(closes + [op])
        feature_rows[d] = {"open": op, "sma160_prev": sma, "rsi": rsi, "close": cl}
        closes.append(cl)

    usable_dates: list[str] = []
    for d in all_dates:
        if d < BACKTEST_START or d not in feature_rows:
            continue
        row = feature_rows[d]
        values = [
            row["open"],
            row["sma160_prev"],
            row["rsi"],
            as_float(market[d].get("TQQQ_OPEN")),
            as_float(market[d].get("TQQQ_CTO_RETURN")),
            as_float(market[d].get("TQQQ_OTC_RETURN")),
            as_float(market[d].get("TMF_CTO_RETURN")),
            as_float(market[d].get("TMF_OTC_RETURN")),
            as_float(market[d].get("GLD_CTO_RETURN")),
            as_float(market[d].get("GLD_OTC_RETURN")),
            as_float(uvix[d].get("UVIX_CTO_RETURN")),
            as_float(uvix[d].get("UVIX_OTC_RETURN")),
        ]
        if all(math.isfinite(v) for v in values):
            usable_dates.append(d)

    opens = np.array([feature_rows[d]["open"] for d in usable_dates], dtype=float)
    sma = np.array([feature_rows[d]["sma160_prev"] for d in usable_dates], dtype=float)
    rsi = np.array([feature_rows[d]["rsi"] for d in usable_dates], dtype=float)

    # Reconstruct previous closes over the full GSPC calendar, then compute Z for requested integer windows.
    close_by_date = {d: feature_rows[d]["close"] for d in feature_rows}
    sorted_gspc_dates = sorted(feature_rows)
    prev_closes: dict[str, list[float]] = {}
    rolling: list[float] = []
    for d in sorted_gspc_dates:
        prev_closes[d] = rolling.copy()
        rolling.append(close_by_date[d])

    bb_z_by_window: dict[int, np.ndarray] = {}
    for window in range(int(BOUNDS[4, 0]), int(BOUNDS[4, 1]) + 1):
        z_values = []
        for d in usable_dates:
            prev = prev_closes[d][-window:]
            if len(prev) < window:
                z_values.append(math.nan)
                continue
            mean = sum(prev) / window
            var = sum((x - mean) ** 2 for x in prev) / window
            std = math.sqrt(var)
            z_values.append((feature_rows[d]["open"] - mean) / std if std else math.nan)
        bb_z_by_window[window] = np.array(z_values, dtype=float)

    def arr(source: dict[str, dict[str, str]], key: str) -> np.ndarray:
        return np.array([as_float(source[d].get(key)) for d in usable_dates], dtype=float)

    return Inputs(
        dates=usable_dates,
        gspc_open=opens,
        gspc_sma160_prev=sma,
        rsi=rsi,
        bb_z_by_window=bb_z_by_window,
        tqqq_open=arr(market, "TQQQ_OPEN"),
        tqqq_cto=arr(market, "TQQQ_CTO_RETURN"),
        tqqq_otc=arr(market, "TQQQ_OTC_RETURN"),
        tmf_cto=arr(market, "TMF_CTO_RETURN"),
        tmf_otc=arr(market, "TMF_OTC_RETURN"),
        gld_cto=arr(market, "GLD_CTO_RETURN"),
        gld_otc=arr(market, "GLD_OTC_RETURN"),
        uvix_cto=arr(uvix, "UVIX_CTO_RETURN"),
        uvix_otc=arr(uvix, "UVIX_OTC_RETURN"),
    )


def normalize_params(x: Iterable[float]) -> np.ndarray:
    p = np.array(list(x), dtype=float)
    p = np.minimum(np.maximum(p, BOUNDS[:, 0]), BOUNDS[:, 1])
    p[0] = round(p[0] * 2.0) / 2.0
    p[1] = round(p[1] * 10.0) / 10.0
    p[2] = round(p[2] * 2.0) / 2.0
    p[3] = round(p[3] * 2.0) / 2.0
    p[4] = round(p[4])
    p[5] = round(p[5] * 20.0) / 20.0
    p[6] = round(p[6] * 2.0) / 2.0
    p[7] = round(p[7] * 2.0) / 2.0
    return p


def compute_metrics(returns: list[float]) -> dict[str, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for r in returns:
        equity *= 1.0 + max(r, -0.999999)
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    years = len(returns) / TRADING_DAYS
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    return {
        "cagr": equity ** (1.0 / years) - 1.0,
        "annualized_vol": math.sqrt(var) * math.sqrt(TRADING_DAYS),
        "max_drawdown": max_drawdown,
        "final_multiple": equity,
    }


def build_base(inputs: Inputs, alpha: float) -> tuple[list[str], np.ndarray, np.ndarray]:
    base: list[str] = []
    triggered = np.zeros(len(inputs.dates), dtype=bool)
    drawdowns = np.zeros(len(inputs.dates), dtype=float)
    in_reentry = False
    prior_peak = inputs.tqqq_open[0]
    episode_peak = prior_peak
    in_below_episode = False

    for i in range(len(inputs.dates)):
        below = inputs.gspc_open[i] < inputs.gspc_sma160_prev[i]
        tqqq_open = inputs.tqqq_open[i]
        if not below:
            in_reentry = False
            in_below_episode = False
            prior_peak = max(prior_peak, tqqq_open)
            episode_peak = prior_peak
            base.append("TQQQ")
            drawdowns[i] = 0.0
            continue

        if not in_below_episode:
            in_below_episode = True
            episode_peak = max(prior_peak, tqqq_open)

        dd = (1.0 - tqqq_open / episode_peak) * 100.0 if episode_peak > 0 else 0.0
        drawdowns[i] = dd
        hit = dd >= alpha
        triggered[i] = hit
        if in_reentry or hit:
            in_reentry = True
            base.append("TQQQ")
        else:
            base.append("wait_mix")
    return base, triggered, drawdowns


def state_returns(inputs: Inputs, state: str, i: int, leg: str) -> float:
    if state == "UVIX":
        return inputs.uvix_cto[i] if leg == "cto" else inputs.uvix_otc[i]
    if state in {"TQQQ", "low_rsi_tqqq_priority"}:
        return inputs.tqqq_cto[i] if leg == "cto" else inputs.tqqq_otc[i]
    if leg == "cto":
        return 0.5 * inputs.tmf_cto[i] + 0.5 * inputs.gld_cto[i]
    return 0.5 * inputs.tmf_otc[i] + 0.5 * inputs.gld_otc[i]


def simulate(inputs: Inputs, raw_params: Iterable[float], keep_path: bool = False) -> tuple[dict[str, float], list[dict[str, object]]]:
    p = normalize_params(raw_params)
    alpha, gamma, entry_rsi, exit_rsi, bb_window, bb_z_threshold, low_entry, low_exit = p
    bb_window = int(bb_window)

    if exit_rsi >= entry_rsi or low_exit <= low_entry:
        return {"cagr": -999.0}, []

    z = inputs.bb_z_by_window[bb_window]
    base, triggered, drawdowns = build_base(inputs, alpha)
    previous_state = base[0]
    active_uvix = False
    active_low = False
    uvix_entry_gspc = math.nan
    returns: list[float] = []
    path: list[dict[str, object]] = []
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

    for i, d in enumerate(inputs.dates):
        target = base[i]
        actions: list[str] = []
        rsi = inputs.rsi[i]
        gspc_open = inputs.gspc_open[i]

        if active_uvix:
            rsi_exit = rsi <= exit_rsi
            gspc_exit = gspc_open <= uvix_entry_gspc * (1.0 + gamma / 100.0)
            if rsi_exit or gspc_exit:
                active_uvix = False
                uvix_entry_gspc = math.nan
                counts["uvix_exits"] += 1
                if rsi_exit and gspc_exit:
                    counts["uvix_rsi_and_gspc_profit_exit"] += 1
                    actions.append("exit_uvix_rsi_and_gspc_profit")
                elif rsi_exit:
                    counts["uvix_rsi_exit_only"] += 1
                    actions.append("exit_uvix_rsi")
                else:
                    counts["uvix_gspc_profit_exit_only"] += 1
                    actions.append("exit_uvix_gspc_profit")
            else:
                target = "UVIX"
        elif active_low:
            if rsi >= low_exit:
                active_low = False
                counts["low_rsi_exits"] += 1
                actions.append("exit_low_rsi_tqqq_priority")
            else:
                target = "low_rsi_tqqq_priority"
        else:
            if rsi >= entry_rsi:
                if z[i] >= bb_z_threshold:
                    active_uvix = True
                    uvix_entry_gspc = gspc_open
                    target = "UVIX"
                    counts["uvix_entries"] += 1
                    actions.append("enter_uvix_high_rsi_bb")
                else:
                    counts["skipped_uvix_entry_days"] += 1
            elif rsi < low_entry and base[i] == "wait_mix":
                active_low = True
                target = "low_rsi_tqqq_priority"
                counts["low_rsi_entries"] += 1
                actions.append("enter_low_rsi_tqqq_priority")

        day_return = (1.0 + state_returns(inputs, previous_state, i, "cto")) * (
            1.0 + state_returns(inputs, target, i, "otc")
        ) - 1.0
        returns.append(day_return)
        equity *= 1.0 + max(day_return, -0.999999)
        if keep_path:
            path.append(
                {
                    "Date": d,
                    "gspc_open_implied_rsi14": rsi,
                    "GSPC_BB_Z": z[i],
                    "GSPC_BB_WINDOW": bb_window,
                    "GSPC_OPEN": gspc_open,
                    "GSPC_SMA160_PREV_CLOSE": inputs.gspc_sma160_prev[i],
                    "TQQQ_OPEN": inputs.tqqq_open[i],
                    "TQQQ_DIRECT_PEAK_DRAWDOWN_PCT": drawdowns[i],
                    "DRAWDOWN_ALPHA_PCT": alpha,
                    "drawdown_trigger": bool(triggered[i]),
                    "base_target_regime_at_open": base[i],
                    "selected_leg": target,
                    "action": "|".join(actions),
                    "strategy_return": day_return,
                    "strategy_equity": equity,
                }
            )
        previous_state = target

    metrics = compute_metrics(returns)
    metrics.update(counts)
    metrics.update({name: float(value) for name, value in zip(PARAM_NAMES, p)})
    metrics["bb_window_days"] = int(metrics["bb_window_days"])
    metrics["start"] = BACKTEST_START
    metrics["end"] = inputs.dates[-1]
    metrics["base_reentry_rule"] = "tqqq_open_drawdown_from_immediate_prior_peak"
    metrics["transition_policy"] = "one_open_transition_per_day"
    metrics["objective"] = "maximize_cagr"
    return metrics, path


def lhs_samples(n: int, rng: random.Random) -> list[np.ndarray]:
    dims = len(PARAM_NAMES)
    samples = np.zeros((n, dims), dtype=float)
    for j in range(dims):
        perm = list(range(n))
        rng.shuffle(perm)
        for i, bucket in enumerate(perm):
            frac = (bucket + rng.random()) / n
            samples[i, j] = BOUNDS[j, 0] + frac * (BOUNDS[j, 1] - BOUNDS[j, 0])
    return [normalize_params(row) for row in samples]


def differential_evolution(
    inputs: Inputs,
    seed: int,
    generations: int = 90,
    pop_size: int = 96,
    f: float = 0.72,
    cr: float = 0.72,
) -> list[dict[str, float]]:
    rng = random.Random(seed)
    population = lhs_samples(pop_size, rng)
    population[0] = normalize_params(CANONICAL)
    scores = [simulate(inputs, p)[0]["cagr"] for p in population]
    trace: list[dict[str, float]] = []
    for gen in range(generations):
        for i in range(pop_size):
            choices = [idx for idx in range(pop_size) if idx != i]
            a_idx, b_idx, c_idx = rng.sample(choices, 3)
            mutant = population[a_idx] + f * (population[b_idx] - population[c_idx])
            trial = population[i].copy()
            forced = rng.randrange(len(PARAM_NAMES))
            for j in range(len(PARAM_NAMES)):
                if rng.random() < cr or j == forced:
                    trial[j] = mutant[j]
            trial = normalize_params(trial)
            score = simulate(inputs, trial)[0]["cagr"]
            if score > scores[i]:
                population[i] = trial
                scores[i] = score
        best_idx = int(np.argmax(scores))
        trace.append({"seed": seed, "generation": gen + 1, "best_cagr": scores[best_idx], **params_dict(population[best_idx])})
    rows = []
    for p, score in zip(population, scores):
        rows.append({"seed": seed, "cagr": score, **params_dict(p)})
    return rows + trace


def params_dict(p: Iterable[float]) -> dict[str, float]:
    p = normalize_params(p)
    return {name: float(value) for name, value in zip(PARAM_NAMES, p)}


def local_refine(inputs: Inputs, initial: np.ndarray) -> list[dict[str, float]]:
    current = normalize_params(initial)
    current_score = simulate(inputs, current)[0]["cagr"]
    step_sets = [
        np.array([5.0, 0.5, 1.0, 1.0, 5.0, 0.25, 1.0, 1.0]),
        np.array([2.0, 0.2, 0.5, 0.5, 2.0, 0.10, 0.5, 0.5]),
        np.array([0.5, 0.1, 0.5, 0.5, 1.0, 0.05, 0.5, 0.5]),
    ]
    rows = []
    improved = True
    while improved:
        improved = False
        for steps in step_sets:
            for j in range(len(PARAM_NAMES)):
                for sign in [-1.0, 1.0]:
                    trial = normalize_params(current + sign * steps * np.eye(len(PARAM_NAMES))[j])
                    score = simulate(inputs, trial)[0]["cagr"]
                    rows.append({"stage": "local", "cagr": score, **params_dict(trial)})
                    if score > current_score:
                        current = trial
                        current_score = score
                        improved = True
    rows.append({"stage": "local_best", "cagr": current_score, **params_dict(current)})
    return rows


def dedupe(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    seen = {}
    for row in rows:
        key = tuple(row.get(name) for name in PARAM_NAMES)
        if key not in seen or row["cagr"] > seen[key]["cagr"]:
            seen[key] = row
    return list(seen.values())


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    inputs = load_inputs()
    canonical_metrics, _ = simulate(inputs, CANONICAL)
    print(
        "Canonical check:",
        f"CAGR={canonical_metrics['cagr'] * 100:.3f}%",
        f"MDD={canonical_metrics['max_drawdown'] * 100:.2f}%",
        f"UVIX entries={int(canonical_metrics['uvix_entries'])}",
    )

    all_rows: list[dict[str, float]] = [{"seed": -1, "cagr": canonical_metrics["cagr"], **params_dict(CANONICAL)}]
    for seed in [11, 29, 47, 71, 97, 131]:
        rows = differential_evolution(inputs, seed=seed)
        final_rows = [r for r in rows if "generation" not in r]
        best = max(final_rows, key=lambda r: r["cagr"])
        print("DE seed", seed, f"best CAGR={best['cagr'] * 100:.3f}%", params_dict([best[n] for n in PARAM_NAMES]))
        all_rows.extend(final_rows)

    candidates = sorted(dedupe(all_rows), key=lambda r: r["cagr"], reverse=True)[:20]
    refined_rows: list[dict[str, float]] = []
    for row in candidates[:8]:
        refined_rows.extend(local_refine(inputs, np.array([row[n] for n in PARAM_NAMES], dtype=float)))
    all_rows.extend(refined_rows)

    ranked = sorted(dedupe(all_rows), key=lambda r: r["cagr"], reverse=True)
    top_metrics = []
    for row in ranked[:50]:
        metrics, _ = simulate(inputs, [row[n] for n in PARAM_NAMES])
        top_metrics.append(metrics)
    best = top_metrics[0]
    _, best_path = simulate(inputs, [best[n] for n in PARAM_NAMES], keep_path=True)

    stem = "canonical_8param_global_de_round2_from_20100212"
    write_csv(OUTPUT_DIR / f"{stem}_candidates.csv", ranked[:500])
    write_csv(OUTPUT_DIR / f"{stem}_top50_metrics.csv", top_metrics)
    write_csv(OUTPUT_DIR / f"{stem}_best_daily_path.csv", best_path)
    write_csv(OUTPUT_DIR / f"{stem}_canonical_check.csv", [canonical_metrics])

    print("Best:")
    print(
        f"CAGR={best['cagr'] * 100:.3f}%",
        f"MDD={best['max_drawdown'] * 100:.2f}%",
        f"UVIX entries={int(best['uvix_entries'])}",
        f"low RSI entries={int(best['low_rsi_entries'])}",
    )
    for name in PARAM_NAMES:
        print(f"  {name}={best[name]}")


if __name__ == "__main__":
    main()
