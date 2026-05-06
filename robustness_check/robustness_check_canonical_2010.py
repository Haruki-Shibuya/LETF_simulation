#!/usr/bin/env python3
from __future__ import annotations

import csv
import itertools
import math
import random
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from statistics import mean, median, pstdev

import numpy as np

import optimize_canonical_8params_from_2010 as opt


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
STEM = "canonical_robustness_2010_open_signal"
CANONICAL = opt.CANONICAL
TRADING_DAYS = 252


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def params_dict(params: np.ndarray) -> dict[str, object]:
    normalized = opt.normalize_params(params)
    out = {name: float(value) for name, value in zip(opt.PARAM_NAMES, normalized)}
    out["bb_window_days"] = int(out["bb_window_days"])
    return out


def candidate_key(params: np.ndarray) -> tuple[float, ...]:
    p = opt.normalize_params(params)
    return tuple(float(x) for x in p)


def subset_inputs(inputs: opt.Inputs, start: str | None = None, end: str | None = None) -> opt.Inputs:
    mask = np.array(
        [(start is None or d >= start) and (end is None or d <= end) for d in inputs.dates],
        dtype=bool,
    )
    dates = [d for d, keep in zip(inputs.dates, mask) if keep]
    bb = {window: values[mask] for window, values in inputs.bb_z_by_window.items()}
    return replace(
        inputs,
        dates=dates,
        gspc_open=inputs.gspc_open[mask],
        gspc_sma160_prev=inputs.gspc_sma160_prev[mask],
        rsi=inputs.rsi[mask],
        bb_z_by_window=bb,
        tqqq_open=inputs.tqqq_open[mask],
        tqqq_cto=inputs.tqqq_cto[mask],
        tqqq_otc=inputs.tqqq_otc[mask],
        tmf_cto=inputs.tmf_cto[mask],
        tmf_otc=inputs.tmf_otc[mask],
        gld_cto=inputs.gld_cto[mask],
        gld_otc=inputs.gld_otc[mask],
        uvix_cto=inputs.uvix_cto[mask],
        uvix_otc=inputs.uvix_otc[mask],
    )


def annualized_return_from_returns(returns: list[float]) -> float:
    if not returns:
        return math.nan
    equity = 1.0
    for r in returns:
        equity *= 1.0 + max(float(r), -0.999999)
    years = len(returns) / TRADING_DAYS
    return equity ** (1.0 / years) - 1.0


def max_drawdown_from_returns(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        equity *= 1.0 + max(float(r), -0.999999)
        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1.0)
    return mdd


def canonical_neighbor_candidates() -> list[np.ndarray]:
    grids = {
        "alpha_drawdown_pct": [37.5, 40.5, 43.0],
        "gspc_exit_gamma_pct": [0.0, 0.1, 0.3],
        "uvix_entry_rsi": [67.0, 67.5, 68.0],
        "uvix_exit_rsi": [65.0, 66.0],
        "bb_window_days": [15.0, 20.0],
        "bb_z_threshold": [1.4, 1.6],
        "low_rsi_entry": [30.0],
        "low_rsi_exit": [32.5],
    }
    ordered = [grids[name] for name in opt.PARAM_NAMES]
    out: dict[tuple[float, ...], np.ndarray] = {}
    for values in itertools.product(*ordered):
        p = opt.normalize_params(values)
        if p[3] < p[2] and p[7] > p[6]:
            out[candidate_key(p)] = p
    out[candidate_key(CANONICAL)] = opt.normalize_params(CANONICAL)
    return list(out.values())


def returns_by_year(path: list[dict[str, object]]) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in path:
        grouped[str(row["Date"])[:4]].append(float(row["strategy_return"]))
    return dict(grouped)


def evaluate_candidates(inputs: opt.Inputs, candidates: list[np.ndarray]) -> tuple[list[dict[str, object]], dict[tuple[float, ...], dict[str, list[float]]]]:
    rows: list[dict[str, object]] = []
    annual_returns: dict[tuple[float, ...], dict[str, list[float]]] = {}
    for idx, params in enumerate(candidates):
        metrics, path = opt.simulate(inputs, params, keep_path=True)
        key = candidate_key(params)
        annual_returns[key] = returns_by_year(path)
        row: dict[str, object] = {"candidate_id": idx, **params_dict(params)}
        row.update({k: metrics[k] for k in ["cagr", "annualized_vol", "max_drawdown", "final_multiple", "uvix_entries", "low_rsi_entries"]})
        rows.append(row)
    rows.sort(key=lambda r: float(r["cagr"]), reverse=True)
    return rows, annual_returns


def score_years(year_returns: dict[str, list[float]], years: list[str]) -> float:
    returns = [r for y in years for r in year_returns.get(y, [])]
    return annualized_return_from_returns(returns)


def mdd_years(year_returns: dict[str, list[float]], years: list[str]) -> float:
    returns = [r for y in years for r in year_returns.get(y, [])]
    return max_drawdown_from_returns(returns)


def walk_forward(annual_returns: dict[tuple[float, ...], dict[str, list[float]]], candidates: list[np.ndarray]) -> list[dict[str, object]]:
    years = sorted({y for yr in annual_returns.values() for y in yr})
    test_years = [y for y in years if "2015" <= y <= "2026"]
    rows: list[dict[str, object]] = []
    for test_year in test_years:
        train_years = [y for y in years if y < test_year]
        if len(train_years) < 4:
            continue
        best_key = max(annual_returns, key=lambda k: score_years(annual_returns[k], train_years))
        test_returns = annual_returns[best_key].get(test_year, [])
        train_cagr = score_years(annual_returns[best_key], train_years)
        test_cagr = annualized_return_from_returns(test_returns)
        canonical_test = annualized_return_from_returns(annual_returns[candidate_key(CANONICAL)].get(test_year, []))
        row = {
            "mode": "anchored_walk_forward",
            "train_start": train_years[0],
            "train_end": train_years[-1],
            "test_year": test_year,
            "train_cagr": train_cagr,
            "test_cagr": test_cagr,
            "test_mdd": max_drawdown_from_returns(test_returns),
            "canonical_same_year_cagr": canonical_test,
        }
        row.update(params_dict(np.array(best_key)))
        rows.append(row)
    for test_year in test_years:
        train_years = [str(y) for y in range(int(test_year) - 5, int(test_year))]
        if not all(y in years for y in train_years):
            continue
        best_key = max(annual_returns, key=lambda k: score_years(annual_returns[k], train_years))
        test_returns = annual_returns[best_key].get(test_year, [])
        row = {
            "mode": "rolling_5y_walk_forward",
            "train_start": train_years[0],
            "train_end": train_years[-1],
            "test_year": test_year,
            "train_cagr": score_years(annual_returns[best_key], train_years),
            "test_cagr": annualized_return_from_returns(test_returns),
            "test_mdd": max_drawdown_from_returns(test_returns),
            "canonical_same_year_cagr": annualized_return_from_returns(annual_returns[candidate_key(CANONICAL)].get(test_year, [])),
        }
        row.update(params_dict(np.array(best_key)))
        rows.append(row)
    return rows


def pbo_cscv_approx(annual_returns: dict[tuple[float, ...], dict[str, list[float]]]) -> list[dict[str, object]]:
    years = sorted(y for y in {y for yr in annual_returns.values() for y in yr} if y <= "2025")
    rng = random.Random(20260504)
    combos = list(itertools.combinations(years, len(years) // 2))
    rng.shuffle(combos)
    combos = combos[:2000]
    rows: list[dict[str, object]] = []
    n_candidates = len(annual_returns)
    for idx, train_tuple in enumerate(combos):
        train_years = list(train_tuple)
        test_years = [y for y in years if y not in train_years]
        best_key = max(annual_returns, key=lambda k: score_years(annual_returns[k], train_years))
        test_scores = [(k, score_years(v, test_years)) for k, v in annual_returns.items()]
        test_scores.sort(key=lambda item: item[1], reverse=True)
        ranks = {k: rank + 1 for rank, (k, _) in enumerate(test_scores)}
        best_test_score = dict(test_scores)[best_key]
        rank = ranks[best_key]
        rows.append(
            {
                "split_id": idx,
                "train_years": ",".join(train_years),
                "test_years": ",".join(test_years),
                "selected_train_cagr": score_years(annual_returns[best_key], train_years),
                "selected_test_cagr": best_test_score,
                "selected_test_rank": rank,
                "selected_test_rank_pct": rank / n_candidates,
                "is_oos_below_median": rank > n_candidates / 2,
                "is_oos_loss": best_test_score < 0,
            }
        )
    return rows


def episode_rows(path: list[dict[str, object]]) -> list[dict[str, object]]:
    episodes: list[dict[str, object]] = []
    active: list[dict[str, object]] = []
    for row in path:
        if row["selected_leg"] == "UVIX":
            active.append(row)
        elif active:
            episodes.append(summarize_episode(active))
            active = []
    if active:
        episodes.append(summarize_episode(active))
    for idx, row in enumerate(episodes, start=1):
        row["episode"] = idx
    return episodes


def summarize_episode(rows: list[dict[str, object]]) -> dict[str, object]:
    uvix_return = 1.0
    strategy_return = 1.0
    for row in rows:
        # During an active UVIX episode, selected_leg is UVIX, so strategy_return is the practical episode return.
        strategy_return *= 1.0 + float(row["strategy_return"])
    return {
        "entry_date": rows[0]["Date"],
        "exit_date": rows[-1]["Date"],
        "days": len(rows),
        "episode_strategy_return": strategy_return - 1.0,
        "entry_rsi": rows[0]["gspc_open_implied_rsi14"],
        "exit_rsi": rows[-1]["gspc_open_implied_rsi14"],
    }


def leave_top_episodes(path: list[dict[str, object]]) -> list[dict[str, object]]:
    episodes = episode_rows(path)
    ranked = sorted(episodes, key=lambda r: float(r["episode_strategy_return"]), reverse=True)
    rows: list[dict[str, object]] = []
    returns_all = [float(row["strategy_return"]) for row in path]
    baseline_cagr = annualized_return_from_returns(returns_all)
    baseline_mdd = max_drawdown_from_returns(returns_all)
    rows.append({"removed_top_episodes": 0, "cagr": baseline_cagr, "max_drawdown": baseline_mdd, "removed_return_sum": 0.0})
    for n in [1, 3, 5, 10]:
        remove_dates = set()
        removed_sum = 0.0
        for ep in ranked[:n]:
            removed_sum += float(ep["episode_strategy_return"])
            start = str(ep["entry_date"])
            end = str(ep["exit_date"])
            remove_dates.update(str(row["Date"]) for row in path if start <= str(row["Date"]) <= end and row["selected_leg"] == "UVIX")
        stressed = [0.0 if str(row["Date"]) in remove_dates else float(row["strategy_return"]) for row in path]
        rows.append(
            {
                "removed_top_episodes": n,
                "cagr": annualized_return_from_returns(stressed),
                "max_drawdown": max_drawdown_from_returns(stressed),
                "removed_return_sum": removed_sum,
            }
        )
    return rows


def execution_slippage(path: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for bps in [0, 5, 10, 25, 50, 100]:
        cost = bps / 10000.0
        stressed_returns = []
        for row in path:
            r = float(row["strategy_return"])
            action = str(row.get("action", ""))
            transitions = 1 if action else 0
            stressed_returns.append(r - transitions * cost)
        rows.append(
            {
                "cost_bps_per_transition": bps,
                "cagr": annualized_return_from_returns(stressed_returns),
                "max_drawdown": max_drawdown_from_returns(stressed_returns),
            }
        )
    return rows


def start_date_sensitivity(inputs: opt.Inputs) -> list[dict[str, object]]:
    rows = []
    for start in ["2010-02-12", "2011-01-03", "2012-01-03", "2013-01-02", "2014-01-02", "2015-01-02"]:
        sub = subset_inputs(inputs, start=start)
        metrics, _ = opt.simulate(sub, CANONICAL)
        rows.append({"start": start, **{k: metrics[k] for k in ["cagr", "annualized_vol", "max_drawdown", "final_multiple", "uvix_entries", "low_rsi_entries"]}})
    return rows


def summarize_rows(rows: list[dict[str, object]], key: str) -> dict[str, float]:
    values = [float(r[key]) for r in rows if math.isfinite(float(r[key]))]
    if not values:
        return {"mean": math.nan, "median": math.nan, "min": math.nan, "max": math.nan, "std": math.nan}
    return {"mean": mean(values), "median": median(values), "min": min(values), "max": max(values), "std": pstdev(values)}


def main() -> None:
    inputs = opt.load_inputs()
    candidates = canonical_neighbor_candidates()
    print(f"candidate_count={len(candidates)}", flush=True)
    candidate_rows, annual_returns = evaluate_candidates(inputs, candidates)
    canonical_metrics, canonical_path = opt.simulate(inputs, CANONICAL, keep_path=True)
    walk_rows = walk_forward(annual_returns, candidates)
    pbo_rows = pbo_cscv_approx(annual_returns)
    episode_out = episode_rows(canonical_path)
    leave_top_rows = leave_top_episodes(canonical_path)
    slippage_rows = execution_slippage(canonical_path)
    start_rows = start_date_sensitivity(inputs)

    wf_anchor = [r for r in walk_rows if r["mode"] == "anchored_walk_forward"]
    wf_roll = [r for r in walk_rows if r["mode"] == "rolling_5y_walk_forward"]
    summary = [
        {"check": "canonical_full_period", **{k: canonical_metrics[k] for k in ["cagr", "annualized_vol", "max_drawdown", "final_multiple", "uvix_entries", "low_rsi_entries"]}},
        {"check": "candidate_grid_best", **{k: candidate_rows[0][k] for k in ["cagr", "annualized_vol", "max_drawdown", "final_multiple", "uvix_entries", "low_rsi_entries"]}},
        {"check": "anchored_walk_forward_oos", **summarize_rows(wf_anchor, "test_cagr"), "positive_year_share": sum(float(r["test_cagr"]) > 0 for r in wf_anchor) / len(wf_anchor)},
        {"check": "rolling_5y_walk_forward_oos", **summarize_rows(wf_roll, "test_cagr"), "positive_year_share": sum(float(r["test_cagr"]) > 0 for r in wf_roll) / len(wf_roll)},
        {
            "check": "cscv_pbo_approx",
            "pbo": sum(bool(r["is_oos_below_median"]) for r in pbo_rows) / len(pbo_rows),
            "prob_oos_loss": sum(bool(r["is_oos_loss"]) for r in pbo_rows) / len(pbo_rows),
            "median_selected_oos_cagr": median(float(r["selected_test_cagr"]) for r in pbo_rows),
            "mean_selected_oos_rank_pct": mean(float(r["selected_test_rank_pct"]) for r in pbo_rows),
        },
        {
            "check": "canonical_uvix_episode_distribution",
            "episodes": len(episode_out),
            "mean": mean(float(r["episode_strategy_return"]) for r in episode_out),
            "median": median(float(r["episode_strategy_return"]) for r in episode_out),
            "std": pstdev(float(r["episode_strategy_return"]) for r in episode_out),
            "win_rate": sum(float(r["episode_strategy_return"]) > 0 for r in episode_out) / len(episode_out),
            "best": max(float(r["episode_strategy_return"]) for r in episode_out),
            "worst": min(float(r["episode_strategy_return"]) for r in episode_out),
        },
    ]

    write_csv(OUTPUT_DIR / f"{STEM}_candidate_grid.csv", candidate_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_walk_forward.csv", walk_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_cscv_pbo_approx.csv", pbo_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_uvix_episodes.csv", episode_out)
    write_csv(OUTPUT_DIR / f"{STEM}_leave_top_episodes.csv", leave_top_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_slippage_stress.csv", slippage_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_start_date_sensitivity.csv", start_rows)
    write_csv(OUTPUT_DIR / f"{STEM}_summary.csv", summary)

    for row in summary:
        print(row, flush=True)
    print("saved", OUTPUT_DIR / f"{STEM}_summary.csv", flush=True)


if __name__ == "__main__":
    main()
