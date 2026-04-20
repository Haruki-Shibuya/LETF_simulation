from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
UVIX_DIR = REPO_DIR / "uvix_backtest"

sys.path.insert(0, str(UVIX_DIR))

import rsi_entry_exit_optimize as opt


DEFAULT_DATASET_NAME = "stitched_uvix_longvol_2x"
DEFAULT_BACKTEST_START = "2005-12-20"
DEFAULT_VALIDATION_START = "2006-01-01"
DEFAULT_HOLDOUT_START = "2023-01-01"
DEFAULT_ENTRY_STEP = 0.1
DEFAULT_EXIT_STEP = 0.1
DEFAULT_ENTRY_MIN = 55.0
DEFAULT_ENTRY_MAX = 95.0
DEFAULT_EXIT_MIN = 45.0
DEFAULT_EXIT_MAX = 90.0
DEFAULT_PLATEAU_RADIUS = 0.3
BASELINE_ENTRY = 71.0
BASELINE_EXIT = 68.0


@dataclass(frozen=True)
class FoldSpec:
    fold_id: int
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    days: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--backtest-start", default=DEFAULT_BACKTEST_START)
    parser.add_argument("--backtest-end", default=None)
    parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START)
    parser.add_argument("--holdout-start", default=DEFAULT_HOLDOUT_START)
    parser.add_argument("--entry-min", type=float, default=DEFAULT_ENTRY_MIN)
    parser.add_argument("--entry-max", type=float, default=DEFAULT_ENTRY_MAX)
    parser.add_argument("--exit-min", type=float, default=DEFAULT_EXIT_MIN)
    parser.add_argument("--exit-max", type=float, default=DEFAULT_EXIT_MAX)
    parser.add_argument("--entry-step", type=float, default=DEFAULT_ENTRY_STEP)
    parser.add_argument("--exit-step", type=float, default=DEFAULT_EXIT_STEP)
    parser.add_argument("--plateau-radius", type=float, default=DEFAULT_PLATEAU_RADIUS)
    return parser.parse_args()


def get_dataset_config(name: str) -> opt.DatasetConfig:
    for config in opt.BASE_DATASETS + [opt.UVXY_DATASET]:
        if config.name == name:
            return config
    raise ValueError(f"Unknown dataset: {name}")


def build_prices_frame(
    config: opt.DatasetConfig,
    backtest_start: str,
    backtest_end: str | None,
) -> pd.DataFrame:
    tickers = sorted({opt.SIGNAL_TICKER, "SOXL", "TQQQ", "UGL", "TMF", "UVIX", "UVXY"})
    prices = opt.download_adj_close(tickers, start=opt.DEFAULT_FETCH_START, end=backtest_end)
    prices, _ = opt.enrich_with_volatility_series(prices)
    overrides = opt.load_extended_price_overrides()
    prices = opt.apply_extended_price_overrides(prices, overrides)
    frame = opt.build_frame(config, prices)
    frame = opt.filter_frame(frame, backtest_start, backtest_end)
    return frame


def first_index_on_or_after(index: pd.DatetimeIndex, date_text: str) -> pd.Timestamp:
    target = pd.Timestamp(date_text)
    mask = index >= target
    if not mask.any():
        raise ValueError(f"No data on or after {date_text}")
    return index[mask][0]


def build_fold_specs(
    index: pd.DatetimeIndex,
    validation_start: str,
    holdout_start: str,
) -> tuple[list[FoldSpec], pd.Timestamp, pd.Timestamp]:
    validation_start_actual = first_index_on_or_after(index, validation_start)
    holdout_start_actual = first_index_on_or_after(index, holdout_start)

    validation_index = index[(index >= validation_start_actual) & (index < holdout_start_actual)]
    if len(validation_index) == 0:
        raise ValueError("Validation window is empty.")

    folds: list[FoldSpec] = []
    for year in sorted(pd.Index(validation_index.year).unique()):
        year_index = validation_index[validation_index.year == year]
        if len(year_index) == 0:
            continue
        folds.append(
            FoldSpec(
                fold_id=len(folds),
                name=str(year),
                start=year_index[0],
                end=year_index[-1],
                days=len(year_index),
            )
        )

    if not folds:
        raise ValueError("No annual validation folds were created.")

    return folds, validation_start_actual, holdout_start_actual


def simulate_fold_metrics(
    frame: pd.DataFrame,
    config: opt.DatasetConfig,
    entries: np.ndarray,
    exits: np.ndarray,
    folds: list[FoldSpec],
    holdout_start: pd.Timestamp,
) -> dict[str, np.ndarray]:
    market = frame[opt.SIGNAL_TICKER].to_numpy(dtype=float)
    rsi = frame[opt.SIGNAL_RSI_COL].to_numpy(dtype=float)
    sma = frame[opt.SIGNAL_SMA_COL].to_numpy(dtype=float)

    returns = frame[["SOXL", "TQQQ", "UGL", "TMF"]].pct_change().fillna(0.0)
    ret_vol = frame[config.vol_return_col].to_numpy(dtype=float)
    ret_soxl = returns["SOXL"].to_numpy(dtype=float)
    ret_tqqq = returns["TQQQ"].to_numpy(dtype=float)
    ret_def = (0.5 * returns["UGL"] + 0.5 * returns["TMF"]).to_numpy(dtype=float)

    low_state = opt.hysteresis_lt(rsi, opt.LOW_RSI_ENTRY, opt.LOW_RSI_EXIT)
    trend_state = opt.hysteresis_sma(market, sma)
    fallback_codes = np.where(low_state, 1, np.where(trend_state, 2, 3)).astype(np.int8)

    count = len(entries)
    fold_count = len(folds)
    fold_id_by_day = np.full(len(frame), -1, dtype=np.int16)
    for fold in folds:
        mask = (frame.index >= fold.start) & (frame.index <= fold.end)
        fold_id_by_day[mask] = fold.fold_id
    holdout_mask = frame.index >= holdout_start

    high_state = np.zeros(count, dtype=bool)
    held_code = np.full(count, -1, dtype=np.int8)

    fold_log_sums = np.zeros((fold_count, count), dtype=np.float64)
    fold_equity = np.ones((fold_count, count), dtype=np.float64)
    fold_peak = np.ones((fold_count, count), dtype=np.float64)
    fold_max_drawdown = np.zeros((fold_count, count), dtype=np.float64)

    holdout_log_sum = np.zeros(count, dtype=np.float64)
    holdout_equity = np.ones(count, dtype=np.float64)
    holdout_peak = np.ones(count, dtype=np.float64)
    holdout_max_drawdown = np.zeros(count, dtype=np.float64)

    for i, value in enumerate(rsi):
        if i > 0:
            day_ret = np.zeros(count, dtype=np.float64)
            vol_mask = held_code == 0
            soxl_mask = held_code == 1
            tqqq_mask = held_code == 2
            def_mask = held_code == 3

            day_ret[vol_mask] = ret_vol[i]
            day_ret[soxl_mask] = ret_soxl[i]
            day_ret[tqqq_mask] = ret_tqqq[i]
            day_ret[def_mask] = ret_def[i]
            day_ret = np.clip(day_ret, -0.999999, None)
            day_log = np.log1p(day_ret)

            fold_id = int(fold_id_by_day[i])
            if fold_id >= 0:
                fold_log_sums[fold_id] += day_log
                fold_equity[fold_id] *= 1.0 + day_ret
                fold_peak[fold_id] = np.maximum(fold_peak[fold_id], fold_equity[fold_id])
                fold_max_drawdown[fold_id] = np.minimum(
                    fold_max_drawdown[fold_id],
                    fold_equity[fold_id] / fold_peak[fold_id] - 1.0,
                )
            elif holdout_mask[i]:
                holdout_log_sum += day_log
                holdout_equity *= 1.0 + day_ret
                holdout_peak = np.maximum(holdout_peak, holdout_equity)
                holdout_max_drawdown = np.minimum(
                    holdout_max_drawdown,
                    holdout_equity / holdout_peak - 1.0,
                )

        if not np.isnan(value):
            enter_mask = (~high_state) & (value > entries)
            exit_mask = high_state & (value < exits)
            high_state[enter_mask] = True
            high_state[exit_mask] = False

        next_code = np.full(count, fallback_codes[i], dtype=np.int8)
        next_code[high_state] = 0
        held_code = next_code

    return {
        "fold_log_sums": fold_log_sums,
        "fold_max_drawdown": fold_max_drawdown,
        "holdout_log_sum": holdout_log_sum,
        "holdout_max_drawdown": holdout_max_drawdown,
        "holdout_equity": holdout_equity,
    }


def build_metric_matrix(
    values: np.ndarray,
    entries: np.ndarray,
    exits: np.ndarray,
    entry_values: np.ndarray,
    exit_values: np.ndarray,
) -> np.ndarray:
    matrix = np.full((len(entry_values), len(exit_values)), np.nan, dtype=np.float64)
    entry_map = {float(value): idx for idx, value in enumerate(entry_values)}
    exit_map = {float(value): idx for idx, value in enumerate(exit_values)}
    for entry, exit_, value in zip(entries, exits, values):
        matrix[entry_map[float(entry)], exit_map[float(exit_)]] = float(value)
    return matrix


def rolling_nanmean_square(matrix: np.ndarray, radius_steps: int) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(matrix)
    values = np.where(valid, matrix, 0.0)

    prefix_values = np.pad(values, ((1, 0), (1, 0)), constant_values=0.0).cumsum(axis=0).cumsum(axis=1)
    prefix_counts = np.pad(valid.astype(np.int32), ((1, 0), (1, 0)), constant_values=0).cumsum(axis=0).cumsum(axis=1)

    def rect_sum(prefix: np.ndarray, i0: int, i1: int, j0: int, j1: int) -> float:
        return (
            prefix[i1 + 1, j1 + 1]
            - prefix[i0, j1 + 1]
            - prefix[i1 + 1, j0]
            + prefix[i0, j0]
        )

    out = np.full_like(matrix, np.nan, dtype=np.float64)
    counts = np.zeros_like(matrix, dtype=np.int32)
    rows, cols = matrix.shape
    for i in range(rows):
        i0 = max(0, i - radius_steps)
        i1 = min(rows - 1, i + radius_steps)
        for j in range(cols):
            j0 = max(0, j - radius_steps)
            j1 = min(cols - 1, j + radius_steps)
            count = int(rect_sum(prefix_counts, i0, i1, j0, j1))
            counts[i, j] = count
            if count > 0:
                out[i, j] = rect_sum(prefix_values, i0, i1, j0, j1) / count
    return out, counts


def simulate_single_strategy(
    frame: pd.DataFrame,
    config: opt.DatasetConfig,
    entry_level: float,
    exit_level: float,
) -> pd.DataFrame:
    market = frame[opt.SIGNAL_TICKER].to_numpy(dtype=float)
    rsi = frame[opt.SIGNAL_RSI_COL].to_numpy(dtype=float)
    sma = frame[opt.SIGNAL_SMA_COL].to_numpy(dtype=float)

    returns = frame[["SOXL", "TQQQ", "UGL", "TMF"]].pct_change().fillna(0.0)
    ret_vol = frame[config.vol_return_col].to_numpy(dtype=float)
    ret_soxl = returns["SOXL"].to_numpy(dtype=float)
    ret_tqqq = returns["TQQQ"].to_numpy(dtype=float)
    ret_def = (0.5 * returns["UGL"] + 0.5 * returns["TMF"]).to_numpy(dtype=float)

    low_state = opt.hysteresis_lt(rsi, opt.LOW_RSI_ENTRY, opt.LOW_RSI_EXIT)
    trend_state = opt.hysteresis_sma(market, sma)

    high_state = False
    held_code = -1
    daily_returns = np.zeros(len(frame), dtype=np.float64)
    held_codes = np.full(len(frame), -1, dtype=np.int8)

    for i, value in enumerate(rsi):
        if i > 0 and held_code >= 0:
            if held_code == 0:
                daily_returns[i] = ret_vol[i]
            elif held_code == 1:
                daily_returns[i] = ret_soxl[i]
            elif held_code == 2:
                daily_returns[i] = ret_tqqq[i]
            else:
                daily_returns[i] = ret_def[i]

        if not np.isnan(value):
            if not high_state and value > entry_level:
                high_state = True
            elif high_state and value < exit_level:
                high_state = False

        if high_state:
            held_code = 0
        elif low_state[i]:
            held_code = 1
        elif trend_state[i]:
            held_code = 2
        else:
            held_code = 3
        held_codes[i] = held_code

    equity = pd.Series((1.0 + daily_returns).cumprod(), index=frame.index, name="equity")
    return pd.DataFrame(
        {
            "daily_return": daily_returns,
            "equity": equity,
            "held_code": held_codes,
        },
        index=frame.index,
    )


def summarize_return_slice(returns: pd.Series) -> tuple[float, float, float]:
    returns = returns.astype(float)
    if len(returns) == 0:
        return np.nan, np.nan, np.nan
    clipped = returns.clip(lower=-0.999999)
    log_sum = float(np.log1p(clipped).sum())
    years = len(clipped) / opt.TRADING_DAYS_PER_YEAR
    cagr = float(np.exp(log_sum / years) - 1.0) if years > 0 else np.nan
    equity = (1.0 + clipped).cumprod()
    peak = equity.cummax()
    max_drawdown = float((equity / peak - 1.0).min())
    final_multiple = float(equity.iloc[-1])
    return cagr, max_drawdown, final_multiple


def build_candidate_summary(
    label: str,
    entry_level: float,
    exit_level: float,
    metrics_row: pd.Series,
    frame: pd.DataFrame,
    config: opt.DatasetConfig,
    holdout_start: pd.Timestamp,
) -> dict[str, object]:
    sim = simulate_single_strategy(frame, config, entry_level, exit_level)
    full_cagr, full_mdd, full_multiple = summarize_return_slice(sim["daily_return"].iloc[1:])
    holdout_returns = sim.loc[holdout_start:, "daily_return"]
    holdout_cagr, holdout_mdd, holdout_multiple = summarize_return_slice(holdout_returns)
    return {
        "selection_rule": label,
        "entry": entry_level,
        "exit": exit_level,
        "validation_total_cagr_pct": float(metrics_row["validation_total_cagr"] * 100.0),
        "validation_median_fold_cagr_pct": float(metrics_row["validation_median_fold_cagr"] * 100.0),
        "validation_p10_fold_cagr_pct": float(metrics_row["validation_p10_fold_cagr"] * 100.0),
        "validation_worst_fold_cagr_pct": float(metrics_row["validation_worst_fold_cagr"] * 100.0),
        "validation_positive_fold_share_pct": float(metrics_row["validation_positive_fold_share"] * 100.0),
        "plateau_median_cagr_pct": float(metrics_row["plateau_median_cagr"] * 100.0),
        "plateau_p10_cagr_pct": float(metrics_row["plateau_p10_cagr"] * 100.0),
        "plateau_neighbor_count": int(metrics_row["plateau_neighbor_count"]),
        "robust_score_pct": float(metrics_row["robust_score"] * 100.0),
        "holdout_cagr_pct": holdout_cagr * 100.0,
        "holdout_mdd_pct": holdout_mdd * 100.0,
        "holdout_final_multiple": holdout_multiple,
        "full_sample_cagr_pct": full_cagr * 100.0,
        "full_sample_mdd_pct": full_mdd * 100.0,
        "full_sample_final_multiple": full_multiple,
    }


def save_heatmap(
    matrix: np.ndarray,
    entry_values: np.ndarray,
    exit_values: np.ndarray,
    title: str,
    colorbar_label: str,
    output_path: Path,
    selected_point: tuple[float, float],
    compare_points: list[tuple[str, float, float]],
) -> None:
    data = matrix * 100.0
    masked = np.ma.masked_invalid(data)

    fig, ax = plt.subplots(figsize=(11, 8), constrained_layout=True)
    mesh = ax.pcolormesh(exit_values, entry_values, masked, cmap="viridis", shading="nearest")

    valid_values = data[np.isfinite(data)]
    if len(valid_values) > 0:
        levels = np.linspace(np.nanpercentile(valid_values, 70), np.nanmax(valid_values), 5)
        if np.nanmax(levels) > np.nanmin(levels):
            contours = ax.contour(exit_values, entry_values, masked, levels=levels, colors="red", linewidths=0.7)
            ax.clabel(contours, inline=True, fontsize=8, fmt=lambda x: f"{x:.1f}%")

    ax.scatter(
        selected_point[1],
        selected_point[0],
        color="red",
        marker="x",
        s=140,
        linewidths=2.4,
        label="Robust optimum",
        zorder=5,
    )
    for label, entry_level, exit_level in compare_points:
        ax.scatter(
            exit_level,
            entry_level,
            marker="o",
            s=55,
            facecolors="none",
            edgecolors="white",
            linewidths=1.5,
            zorder=4,
            label=label,
        )

    ax.set_xlabel("RSI Exit")
    ax.set_ylabel("RSI Entry")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=9)
    colorbar = fig.colorbar(mesh, ax=ax)
    colorbar.set_label(colorbar_label)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_fold_comparison_plot(
    folds: list[FoldSpec],
    metrics: pd.DataFrame,
    candidates: list[tuple[str, float, float]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    x = np.arange(len(folds))
    for label, entry_level, exit_level in candidates:
        row = metrics[(np.isclose(metrics["entry"], entry_level)) & (np.isclose(metrics["exit"], exit_level))].iloc[0]
        values = [float(row[f"fold_{fold.name}_cagr"]) * 100.0 for fold in folds]
        ax.plot(x, values, marker="o", linewidth=2.0, label=label)
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    ax.set_xticks(x, [fold.name for fold in folds], rotation=45)
    ax.set_ylabel("Fold CAGR (%)")
    ax.set_title("Annual OOS Fold CAGR By Candidate")
    ax.legend()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_equity_plot(
    frame: pd.DataFrame,
    config: opt.DatasetConfig,
    candidates: list[tuple[str, float, float]],
    holdout_start: pd.Timestamp,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    for label, entry_level, exit_level in candidates:
        sim = simulate_single_strategy(frame, config, entry_level, exit_level)
        ax.plot(sim.index, sim["equity"], linewidth=2.0, label=label)
    ax.axvline(holdout_start, color="black", linestyle="--", linewidth=1.0, label="Holdout start")
    ax.set_yscale("log")
    ax.set_ylabel("Equity (log scale)")
    ax.set_title("Full-Path Equity Comparison")
    ax.legend()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config = get_dataset_config(args.dataset)
    frame = build_prices_frame(config, args.backtest_start, args.backtest_end)
    folds, validation_start_actual, holdout_start_actual = build_fold_specs(
        frame.index,
        args.validation_start,
        args.holdout_start,
    )

    entries, exits = opt.build_threshold_grid(
        entry_min=args.entry_min,
        entry_max=args.entry_max,
        exit_min=args.exit_min,
        exit_max=args.exit_max,
        entry_step=args.entry_step,
        exit_step=args.exit_step,
    )

    sim = simulate_fold_metrics(
        frame=frame,
        config=config,
        entries=entries,
        exits=exits,
        folds=folds,
        holdout_start=holdout_start_actual,
    )

    fold_years = np.array([fold.days / opt.TRADING_DAYS_PER_YEAR for fold in folds], dtype=np.float64)
    validation_total_years = float(sum(fold.days for fold in folds) / opt.TRADING_DAYS_PER_YEAR)
    holdout_days = int((frame.index >= holdout_start_actual).sum())
    holdout_years = holdout_days / opt.TRADING_DAYS_PER_YEAR

    fold_cagrs = np.exp(sim["fold_log_sums"] / fold_years[:, None]) - 1.0
    validation_total_cagr = np.exp(sim["fold_log_sums"].sum(axis=0) / validation_total_years) - 1.0
    holdout_cagr = np.exp(sim["holdout_log_sum"] / holdout_years) - 1.0

    metrics = pd.DataFrame(
        {
            "entry": entries,
            "exit": exits,
            "validation_total_cagr": validation_total_cagr,
            "validation_median_fold_cagr": np.median(fold_cagrs, axis=0),
            "validation_p10_fold_cagr": np.quantile(fold_cagrs, 0.10, axis=0),
            "validation_worst_fold_cagr": np.min(fold_cagrs, axis=0),
            "validation_mean_fold_cagr": np.mean(fold_cagrs, axis=0),
            "validation_positive_fold_share": np.mean(fold_cagrs > 0.0, axis=0),
            "validation_worst_fold_mdd": np.min(sim["fold_max_drawdown"], axis=0),
            "validation_median_fold_mdd": np.median(sim["fold_max_drawdown"], axis=0),
            "holdout_cagr": holdout_cagr,
            "holdout_mdd": sim["holdout_max_drawdown"],
            "holdout_final_multiple": sim["holdout_equity"],
        }
    )
    for fold, values in zip(folds, fold_cagrs):
        metrics[f"fold_{fold.name}_cagr"] = values

    entry_values = np.round(np.arange(args.entry_min, args.entry_max + (args.entry_step / 2.0), args.entry_step), 10)
    exit_values = np.round(np.arange(args.exit_min, args.exit_max + (args.exit_step / 2.0), args.exit_step), 10)
    radius_steps = int(round(args.plateau_radius / args.entry_step))

    median_matrix = build_metric_matrix(
        metrics["validation_median_fold_cagr"].to_numpy(),
        entries,
        exits,
        entry_values,
        exit_values,
    )
    p10_matrix = build_metric_matrix(
        metrics["validation_p10_fold_cagr"].to_numpy(),
        entries,
        exits,
        entry_values,
        exit_values,
    )
    holdout_matrix = build_metric_matrix(
        metrics["holdout_cagr"].to_numpy(),
        entries,
        exits,
        entry_values,
        exit_values,
    )
    plateau_median_matrix, neighbor_counts = rolling_nanmean_square(median_matrix, radius_steps)
    plateau_p10_matrix, _ = rolling_nanmean_square(p10_matrix, radius_steps)
    robust_score_matrix = 0.5 * (plateau_median_matrix + plateau_p10_matrix)

    flat_plateau_median = []
    flat_plateau_p10 = []
    flat_robust_score = []
    flat_neighbor_count = []
    entry_map = {float(value): idx for idx, value in enumerate(entry_values)}
    exit_map = {float(value): idx for idx, value in enumerate(exit_values)}
    for entry_level, exit_level in zip(entries, exits):
        i = entry_map[float(entry_level)]
        j = exit_map[float(exit_level)]
        flat_plateau_median.append(plateau_median_matrix[i, j])
        flat_plateau_p10.append(plateau_p10_matrix[i, j])
        flat_robust_score.append(robust_score_matrix[i, j])
        flat_neighbor_count.append(neighbor_counts[i, j])

    metrics["plateau_median_cagr"] = flat_plateau_median
    metrics["plateau_p10_cagr"] = flat_plateau_p10
    metrics["robust_score"] = flat_robust_score
    metrics["plateau_neighbor_count"] = flat_neighbor_count
    metrics = metrics.sort_values(
        ["robust_score", "plateau_p10_cagr", "plateau_median_cagr", "validation_total_cagr"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    robust_row = metrics.iloc[0]
    naive_row = metrics.sort_values(["validation_total_cagr", "holdout_cagr"], ascending=[False, False]).iloc[0]
    baseline_row = metrics[(np.isclose(metrics["entry"], BASELINE_ENTRY)) & (np.isclose(metrics["exit"], BASELINE_EXIT))].iloc[0]

    robust_point = (float(robust_row["entry"]), float(robust_row["exit"]))
    compare_points = [
        ("Validation max", float(naive_row["entry"]), float(naive_row["exit"])),
        ("71/68 baseline", BASELINE_ENTRY, BASELINE_EXIT),
    ]

    metrics_path = OUTPUT_DIR / "parameter_metrics.csv"
    folds_path = OUTPUT_DIR / "validation_folds.csv"
    summary_path = OUTPUT_DIR / "selection_summary.csv"
    top20_path = OUTPUT_DIR / "top20_by_robust_score.csv"

    fold_frame = pd.DataFrame(
        [
            {
                "fold_id": fold.fold_id,
                "fold_name": fold.name,
                "start": fold.start.strftime("%Y-%m-%d"),
                "end": fold.end.strftime("%Y-%m-%d"),
                "days": fold.days,
            }
            for fold in folds
        ]
    )
    fold_frame.to_csv(folds_path, index=False)

    summary_rows = [
        build_candidate_summary(
            label="robust_optimum",
            entry_level=float(robust_row["entry"]),
            exit_level=float(robust_row["exit"]),
            metrics_row=robust_row,
            frame=frame,
            config=config,
            holdout_start=holdout_start_actual,
        ),
        build_candidate_summary(
            label="validation_total_max",
            entry_level=float(naive_row["entry"]),
            exit_level=float(naive_row["exit"]),
            metrics_row=naive_row,
            frame=frame,
            config=config,
            holdout_start=holdout_start_actual,
        ),
        build_candidate_summary(
            label="baseline_71_68",
            entry_level=BASELINE_ENTRY,
            exit_level=BASELINE_EXIT,
            metrics_row=baseline_row,
            frame=frame,
            config=config,
            holdout_start=holdout_start_actual,
        ),
    ]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(summary_path, index=False)

    metrics.to_csv(metrics_path, index=False)
    metrics.head(20).to_csv(top20_path, index=False)

    save_heatmap(
        matrix=median_matrix,
        entry_values=entry_values,
        exit_values=exit_values,
        title="Validation Median Annual OOS CAGR",
        colorbar_label="Median annual OOS CAGR (%)",
        output_path=OUTPUT_DIR / "validation_median_fold_cagr_heatmap.png",
        selected_point=robust_point,
        compare_points=compare_points,
    )
    save_heatmap(
        matrix=p10_matrix,
        entry_values=entry_values,
        exit_values=exit_values,
        title="Validation P10 Annual OOS CAGR",
        colorbar_label="P10 annual OOS CAGR (%)",
        output_path=OUTPUT_DIR / "validation_p10_fold_cagr_heatmap.png",
        selected_point=robust_point,
        compare_points=compare_points,
    )
    save_heatmap(
        matrix=robust_score_matrix,
        entry_values=entry_values,
        exit_values=exit_values,
        title="Plateau-Smoothed Robust Score",
        colorbar_label="Robust score (%)",
        output_path=OUTPUT_DIR / "plateau_robust_score_heatmap.png",
        selected_point=robust_point,
        compare_points=compare_points,
    )
    save_heatmap(
        matrix=holdout_matrix,
        entry_values=entry_values,
        exit_values=exit_values,
        title="Final Holdout CAGR",
        colorbar_label="Holdout CAGR (%)",
        output_path=OUTPUT_DIR / "holdout_cagr_heatmap.png",
        selected_point=robust_point,
        compare_points=compare_points,
    )
    save_fold_comparison_plot(
        folds=folds,
        metrics=metrics,
        candidates=[
            ("Robust optimum", float(robust_row["entry"]), float(robust_row["exit"])),
            ("Validation max", float(naive_row["entry"]), float(naive_row["exit"])),
            ("71/68 baseline", BASELINE_ENTRY, BASELINE_EXIT),
        ],
        output_path=OUTPUT_DIR / "annual_fold_cagr_comparison.png",
    )
    save_equity_plot(
        frame=frame,
        config=config,
        candidates=[
            ("Robust optimum", float(robust_row["entry"]), float(robust_row["exit"])),
            ("Validation max", float(naive_row["entry"]), float(naive_row["exit"])),
            ("71/68 baseline", BASELINE_ENTRY, BASELINE_EXIT),
        ],
        holdout_start=holdout_start_actual,
        output_path=OUTPUT_DIR / "equity_curve_comparison.png",
    )

    print("Validation window:", validation_start_actual.strftime("%Y-%m-%d"), "->", folds[-1].end.strftime("%Y-%m-%d"))
    print("Holdout start:", holdout_start_actual.strftime("%Y-%m-%d"))
    print("Robust optimum:", f"entry={robust_point[0]:.1f}", f"exit={robust_point[1]:.1f}")
    print(summary.to_string(index=False))
    print("\nSaved files")
    for path in [
        folds_path,
        metrics_path,
        top20_path,
        summary_path,
        OUTPUT_DIR / "validation_median_fold_cagr_heatmap.png",
        OUTPUT_DIR / "validation_p10_fold_cagr_heatmap.png",
        OUTPUT_DIR / "plateau_robust_score_heatmap.png",
        OUTPUT_DIR / "holdout_cagr_heatmap.png",
        OUTPUT_DIR / "annual_fold_cagr_comparison.png",
        OUTPUT_DIR / "equity_curve_comparison.png",
    ]:
        print(path)


if __name__ == "__main__":
    main()
