from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import rsi_entry_exit_optimize as opt


DEFAULT_DATASET_NAME = "stitched_uvix_longvol_2x"
DEFAULT_BACKTEST_START = "2011-01-01"
DEFAULT_ENTRY_STEP = 0.1
DEFAULT_EXIT_STEP = 0.1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET_NAME)
    parser.add_argument("--backtest-start", default=DEFAULT_BACKTEST_START)
    parser.add_argument("--backtest-end", default=None)
    parser.add_argument("--entry-step", type=float, default=DEFAULT_ENTRY_STEP)
    parser.add_argument("--exit-step", type=float, default=DEFAULT_EXIT_STEP)
    return parser.parse_args()


def get_dataset_config(name: str) -> opt.DatasetConfig:
    for config in opt.BASE_DATASETS + [opt.UVXY_DATASET]:
        if config.name == name:
            return config
    raise ValueError(f"Unknown dataset: {name}")


def output_suffix(backtest_start: str | None, backtest_end: str | None, entry_step: float, exit_step: float) -> str:
    return opt.build_output_suffix(
        backtest_start=backtest_start,
        backtest_end=backtest_end,
        entry_step=entry_step,
        exit_step=exit_step,
    )


def load_full_grid(config: opt.DatasetConfig, suffix: str) -> pd.DataFrame:
    path = opt.OUTPUT_DIR / f"{config.name}_full_grid{suffix}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing full grid CSV: {path}")
    return pd.read_csv(path)


def build_prices() -> pd.DataFrame:
    tickers = sorted({opt.SIGNAL_TICKER, "SOXL", "TQQQ", "UGL", "TMF", "UVIX", "UVXY"})
    prices = opt.download_adj_close(tickers, start=opt.DEFAULT_FETCH_START, end=None)
    prices, _ = opt.enrich_with_volatility_series(prices)
    overrides = opt.load_extended_price_overrides()
    prices = opt.apply_extended_price_overrides(prices, overrides)
    return prices


def hysteresis_gt(values: np.ndarray, entry_level: float, exit_level: float) -> np.ndarray:
    state = False
    out = np.zeros(len(values), dtype=bool)
    for i, value in enumerate(values):
        if not np.isnan(value):
            if not state and value > entry_level:
                state = True
            elif state and value < exit_level:
                state = False
        out[i] = state
    return out


def identify_episodes(frame: pd.DataFrame, entry_level: float, exit_level: float) -> tuple[pd.DataFrame, np.ndarray]:
    high_state = hysteresis_gt(frame[opt.SIGNAL_RSI_COL].to_numpy(dtype=float), entry_level, exit_level)
    episode_ids = np.full(len(frame), -1, dtype=np.int32)
    rows: list[dict[str, object]] = []

    current_start = None
    episode_number = 0
    for i, is_on in enumerate(high_state):
        if is_on and current_start is None:
            current_start = i
        is_last = i == len(high_state) - 1
        if current_start is not None and ((not is_on) or is_last):
            end_idx = i if is_on and is_last else i - 1
            episode_number += 1
            episode_ids[current_start : end_idx + 1] = episode_number - 1
            carry_idx = end_idx + 1 if end_idx + 1 < len(frame) else -1
            if carry_idx >= 0:
                episode_ids[carry_idx] = episode_number - 1
            rows.append(
                {
                    "episode_id": episode_number - 1,
                    "episode_number": episode_number,
                    "episode_start": frame.index[current_start].strftime("%Y-%m-%d"),
                    "episode_end": frame.index[end_idx].strftime("%Y-%m-%d"),
                    "episode_days": end_idx - current_start + 1,
                    "carry_day": frame.index[carry_idx].strftime("%Y-%m-%d") if carry_idx >= 0 else "",
                    "omit_block_days": end_idx - current_start + 1 + (1 if carry_idx >= 0 else 0),
                }
            )
            current_start = None
    episodes = pd.DataFrame(rows)
    return episodes, episode_ids


def analyze_leave_one_episode_out(
    frame: pd.DataFrame,
    config: opt.DatasetConfig,
    entries: np.ndarray,
    exits: np.ndarray,
    episode_ids: np.ndarray,
    full_best_entry: float,
    full_best_exit: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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

    strategy_count = len(entries)
    episode_count = int(episode_ids.max()) + 1

    full_idx_arr = np.where(np.isclose(entries, full_best_entry) & np.isclose(exits, full_best_exit))[0]
    if len(full_idx_arr) != 1:
        raise ValueError("Could not uniquely identify full-sample optimum in threshold grid.")
    full_idx = int(full_idx_arr[0])

    high_state = np.zeros(strategy_count, dtype=bool)
    held_code = np.full(strategy_count, -1, dtype=np.int8)
    full_log_equity = np.zeros(strategy_count, dtype=np.float64)
    episode_log_sums = np.zeros((episode_count, strategy_count), dtype=np.float64)
    full_opt_episode_log_sums = np.zeros(episode_count, dtype=np.float64)

    for i, value in enumerate(rsi):
        if i > 0:
            day_ret = np.empty(strategy_count, dtype=np.float64)
            day_ret.fill(0.0)

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
            full_log_equity += day_log

            episode_id = int(episode_ids[i])
            if episode_id >= 0:
                episode_log_sums[episode_id] += day_log
                full_opt_episode_log_sums[episode_id] += day_log[full_idx]

        if not np.isnan(value):
            enter_mask = (~high_state) & (value > entries)
            exit_mask = high_state & (value < exits)
            high_state[enter_mask] = True
            high_state[exit_mask] = False

        next_code = np.full(strategy_count, fallback_codes[i], dtype=np.int8)
        next_code[high_state] = 0
        held_code = next_code

    omit_block_days = np.bincount(episode_ids[episode_ids >= 0], minlength=episode_count)
    total_return_days = len(frame) - 1
    base_included_days = total_return_days - omit_block_days
    base_years = base_included_days / opt.TRADING_DAYS_PER_YEAR

    rows: list[dict[str, object]] = []
    for episode_id in range(episode_count):
        loo_log_equity = full_log_equity - episode_log_sums[episode_id]
        years = base_years[episode_id]
        loo_cagr = np.exp(loo_log_equity / years) - 1.0
        best_idx = int(np.argmax(loo_cagr))
        rows.append(
            {
                "episode_id": episode_id,
                "best_entry": entries[best_idx],
                "best_exit": exits[best_idx],
                "best_cagr": loo_cagr[best_idx],
                "full_opt_cagr_without_episode": loo_cagr[full_idx],
                "full_opt_episode_block_return": np.exp(full_opt_episode_log_sums[episode_id]) - 1.0,
                "included_return_days": int(base_included_days[episode_id]),
            }
        )

    episode_results = pd.DataFrame(rows)
    distribution = (
        episode_results.groupby(["best_entry", "best_exit"], as_index=False)
        .size()
        .sort_values(["size", "best_entry", "best_exit"], ascending=[False, True, True])
        .rename(columns={"size": "count"})
        .reset_index(drop=True)
    )
    episode_results["same_as_full_optimum"] = (
        np.isclose(episode_results["best_entry"], full_best_entry)
        & np.isclose(episode_results["best_exit"], full_best_exit)
    )
    return episode_results, distribution


def save_distribution_plot(distribution: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    sizes = 80 + distribution["count"].to_numpy(dtype=float) * 45.0
    scatter = ax.scatter(
        distribution["best_entry"],
        distribution["best_exit"],
        s=sizes,
        c=distribution["count"],
        cmap="viridis",
        edgecolors="black",
        linewidths=0.8,
        alpha=0.9,
    )
    for _, row in distribution.iterrows():
        ax.text(
            row["best_entry"] + 0.03,
            row["best_exit"] + 0.03,
            str(int(row["count"])),
            fontsize=9,
            color="black",
        )
    ax.set_xlabel("Optimal RSI Entry")
    ax.set_ylabel("Optimal RSI Exit")
    ax.set_title("Leave-One-Episode-Out Optimal Threshold Distribution")
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("Episode count")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def sunflower_offsets(count: int, radius: float) -> tuple[np.ndarray, np.ndarray]:
    if count <= 1:
        return np.zeros(count), np.zeros(count)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    idx = np.arange(count, dtype=float)
    r = radius * np.sqrt((idx + 0.5) / count)
    theta = idx * golden_angle
    return r * np.cos(theta), r * np.sin(theta)


def save_optima_x_plot(
    episode_results: pd.DataFrame,
    distribution: pd.DataFrame,
    full_best_entry: float,
    full_best_exit: float,
    entry_step: float,
    exit_step: float,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    jitter_radius_x = entry_step * 0.85
    jitter_radius_y = exit_step * 0.85

    plotted_x: list[float] = []
    plotted_y: list[float] = []
    plotted_alpha: list[float] = []

    for _, row in distribution.iterrows():
        entry = float(row["best_entry"])
        exit_ = float(row["best_exit"])
        count = int(row["count"])
        dx, dy = sunflower_offsets(count, radius=1.0)
        plotted_x.extend(entry + dx * jitter_radius_x)
        plotted_y.extend(exit_ + dy * jitter_radius_y)
        plotted_alpha.extend([0.55] * count)

        ax.scatter(
            [entry],
            [exit_],
            marker="o",
            s=26,
            color="#d92d20",
            edgecolors="white",
            linewidths=0.8,
            zorder=4,
        )
        ax.annotate(
            f"{count}x @ ({entry:.1f}, {exit_:.1f})",
            xy=(entry, exit_),
            xytext=(entry + 0.16, exit_ + 0.05),
            fontsize=9,
            color="#d92d20",
            arrowprops={"arrowstyle": "-", "lw": 1.0, "color": "#d92d20"},
            bbox={"boxstyle": "round,pad=0.22", "fc": "white", "ec": "#d92d20", "alpha": 0.92},
            zorder=5,
        )

    ax.scatter(
        plotted_x,
        plotted_y,
        marker="x",
        s=68,
        c="#1f4e79",
        linewidths=1.6,
        alpha=0.72,
        zorder=3,
    )
    ax.scatter(
        [full_best_entry],
        [full_best_exit],
        marker="o",
        s=160,
        facecolors="none",
        edgecolors="#ff8c00",
        linewidths=2.2,
        zorder=6,
    )
    ax.annotate(
        "Full-sample optimum",
        xy=(full_best_entry, full_best_exit),
        xytext=(full_best_entry + 0.22, full_best_exit + 0.16),
        fontsize=10,
        color="#ff8c00",
        arrowprops={"arrowstyle": "->", "lw": 1.2, "color": "#ff8c00"},
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#ff8c00", "alpha": 0.94},
        zorder=7,
    )
    ax.set_xlabel("Optimal RSI Entry")
    ax.set_ylabel("Optimal RSI Exit")
    ax.set_title("Leave-One-Episode-Out Optima as X Marks\nJittered slightly for visibility")
    ax.grid(alpha=0.22)

    x_min = min(min(plotted_x), distribution["best_entry"].min(), full_best_entry) - entry_step * 2.0
    x_max = max(max(plotted_x), distribution["best_entry"].max(), full_best_entry) + entry_step * 2.0
    y_min = min(min(plotted_y), distribution["best_exit"].min(), full_best_exit) - exit_step * 2.0
    y_max = max(max(plotted_y), distribution["best_exit"].max(), full_best_exit) + exit_step * 2.0
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    config = get_dataset_config(args.dataset)
    suffix = output_suffix(args.backtest_start, args.backtest_end, args.entry_step, args.exit_step)
    full_grid = load_full_grid(config, suffix)
    full_best = full_grid.loc[full_grid["cagr"].idxmax()]
    full_best_entry = float(full_best["entry"])
    full_best_exit = float(full_best["exit"])

    prices = build_prices()
    frame = opt.build_frame(config, prices)
    frame = opt.filter_frame(frame, args.backtest_start, args.backtest_end)

    entries, exits = opt.build_threshold_grid(
        entry_min=opt.DEFAULT_ENTRY_MIN,
        entry_max=opt.DEFAULT_ENTRY_MAX,
        exit_min=opt.DEFAULT_EXIT_MIN,
        exit_max=opt.DEFAULT_EXIT_MAX,
        entry_step=args.entry_step,
        exit_step=args.exit_step,
    )

    episodes, episode_ids = identify_episodes(frame, full_best_entry, full_best_exit)
    episode_results, distribution = analyze_leave_one_episode_out(
        frame=frame,
        config=config,
        entries=entries,
        exits=exits,
        episode_ids=episode_ids,
        full_best_entry=full_best_entry,
        full_best_exit=full_best_exit,
    )

    merged = episodes.merge(episode_results, on="episode_id", how="left")
    merged["entry_shift"] = merged["best_entry"] - full_best_entry
    merged["exit_shift"] = merged["best_exit"] - full_best_exit
    merged["best_cagr_pct"] = merged["best_cagr"] * 100.0
    merged["full_opt_cagr_without_episode_pct"] = merged["full_opt_cagr_without_episode"] * 100.0
    merged["full_opt_episode_block_return_pct"] = merged["full_opt_episode_block_return"] * 100.0

    summary = pd.DataFrame(
        [
            {
                "dataset": config.name,
                "full_sample_best_entry": full_best_entry,
                "full_sample_best_exit": full_best_exit,
                "episode_count": len(episodes),
                "same_as_full_optimum_count": int(merged["same_as_full_optimum"].sum()),
                "same_as_full_optimum_share": float(merged["same_as_full_optimum"].mean()),
                "distinct_leave_one_out_optima": int(len(distribution)),
                "mode_best_entry": float(distribution.iloc[0]["best_entry"]),
                "mode_best_exit": float(distribution.iloc[0]["best_exit"]),
                "mode_count": int(distribution.iloc[0]["count"]),
            }
        ]
    )

    base_name = f"{config.name}_episode_leave_one_out{suffix}"
    episodes_path = opt.OUTPUT_DIR / f"{base_name}.csv"
    distribution_path = opt.OUTPUT_DIR / f"{base_name}_distribution.csv"
    summary_path = opt.OUTPUT_DIR / f"{base_name}_summary.csv"
    plot_path = opt.OUTPUT_DIR / f"{base_name}_distribution.png"
    x_plot_path = opt.OUTPUT_DIR / f"{base_name}_xmarks.png"

    merged.to_csv(episodes_path, index=False)
    distribution.to_csv(distribution_path, index=False)
    summary.to_csv(summary_path, index=False)
    save_distribution_plot(distribution, plot_path)
    save_optima_x_plot(
        episode_results=episode_results,
        distribution=distribution,
        full_best_entry=full_best_entry,
        full_best_exit=full_best_exit,
        entry_step=args.entry_step,
        exit_step=args.exit_step,
        output_path=x_plot_path,
    )

    print(summary.to_string(index=False))
    print("\nTop distribution rows")
    print(distribution.head(10).to_string(index=False))
    print("\nSaved files")
    print(episodes_path)
    print(distribution_path)
    print(summary_path)
    print(plot_path)
    print(x_plot_path)


if __name__ == "__main__":
    main()
