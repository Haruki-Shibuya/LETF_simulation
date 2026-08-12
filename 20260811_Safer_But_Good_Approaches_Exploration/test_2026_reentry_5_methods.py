from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
sys.path.insert(0, str(ROOT))

from explore_recent_performance_methods import (  # noqa: E402
    aggregate_candidates,
    backtest_weights,
)
from validate_parameters import (  # noqa: E402
    DELAYS,
    hysteresis_trend,
    load_inputs,
)


METHOD_LABELS = {
    "A_relaxed_reentry": "A: Relaxed SPY re-entry",
    "B_drawdown_rebound": "B: Rebound from recent low",
    "C_ndx_short_trend": "C: Nasdaq short trend",
    "D_staged_reentry": "D: Staged re-entry",
    "E_timed_rebound": "E: Timed rebound window",
}

FULL_CAGR_FLOOR = 0.30
POST_2008_CAGR_FLOOR = 0.30
DOTCOM_DRAWDOWN_FLOOR = -0.60


def consecutive_true(values: pd.Series, days: int) -> pd.Series:
    return values.rolling(days, min_periods=days).sum().eq(days)


def timed_rebound_weight(
    base_signal: pd.Series,
    trigger: pd.Series,
    holding_days: int,
    weight: float,
) -> pd.Series:
    output = []
    remaining = 0
    for base_on, fired in zip(base_signal, trigger):
        if base_on:
            remaining = 0
            output.append(1.0)
        elif fired:
            remaining = holding_days
            output.append(weight)
            remaining -= 1
        elif remaining > 0:
            output.append(weight)
            remaining -= 1
        else:
            output.append(0.0)
    return pd.Series(output, index=base_signal.index, dtype=float)


def save_outputs(
    results: pd.DataFrame,
    robust: pd.DataFrame,
    selected: pd.DataFrame,
    paths: dict[tuple[str, int], pd.DataFrame],
) -> None:
    results.to_csv(OUTPUT / "reentry_2026_candidate_results.csv", index=False)
    robust.to_csv(OUTPUT / "reentry_2026_candidate_robust_summary.csv", index=False)
    selected.to_csv(OUTPUT / "reentry_2026_selected_summary.csv", index=False)

    selected_ids = set(selected["candidate_id"])
    exports = []
    for candidate_id in selected_ids:
        for delay in DELAYS:
            path = paths[(candidate_id, delay)].copy()
            path.insert(0, "date", path.index)
            path.insert(1, "candidate_id", candidate_id)
            path.insert(2, "delay", delay)
            exports.append(path.reset_index(drop=True))
    pd.concat(exports, ignore_index=True).to_csv(
        OUTPUT / "reentry_2026_selected_paths.csv", index=False
    )

    ordered = selected.reset_index(drop=True)
    colors = ["#444444", "#4C78A8", "#E0A458", "#D98C4B", "#7A9E52", "#B279A2"]
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), dpi=170)
    panels = [
        ("min_2026_ytd_return", "2026 YTD return", 0.0),
        ("min_delay_cagr", "Full-period CAGR", 0.30),
        ("worst_dotcom_drawdown", "Dot-com maximum drawdown", -0.60),
        ("worst_max_drawdown", "Full-period maximum drawdown", -0.60),
    ]
    labels = ordered["method_label"].tolist()
    for ax, (column, title, threshold) in zip(axes.flat, panels):
        values = ordered[column].to_numpy()
        bars = ax.barh(np.arange(len(labels)), values, color=colors, edgecolor="#333333")
        for bar, value in zip(bars, values):
            offset = 0.008 if value >= 0 else -0.008
            ax.text(
                value + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1%}",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=9,
            )
        ax.axvline(threshold, color="#222222", linestyle="--", linewidth=1.0)
        ax.set_title(title, loc="left")
        ax.set_yticks(np.arange(len(labels)), labels)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        minimum = min(values.min(), threshold, 0.0)
        maximum = max(values.max(), threshold, 0.0)
        padding = max(0.05, 0.15 * (maximum - minimum))
        ax.set_xlim(minimum - padding, maximum + padding)
    fig.suptitle(
        "Five dynamic re-entry methods versus the baseline\n"
        "Each metric is the worse result across normal and one-day-additional delays",
        x=0.05,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUTPUT / "reentry_2026_metric_comparison.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 7), dpi=170)
    for position, row in enumerate(ordered.itertuples(index=False)):
        path = paths[(row.candidate_id, 1)].loc["2026-01-01":]
        normalized = 100.0 * path["nav_1000"] / path["nav_1000"].iloc[0]
        ax.plot(
            normalized.index,
            normalized,
            label=row.method_label,
            color=colors[position],
            linewidth=1.8,
        )
    ax.axhline(100.0, color="#777777", linewidth=0.9)
    ax.set_title("2026 portfolio paths with one-day additional delay", loc="left")
    ax.set_ylabel("Portfolio value (first 2026 trading day = 100)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "reentry_2026_paths.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 5.8), dpi=170)
    matrices = []
    index = None
    for row in ordered.itertuples(index=False):
        path = paths[(row.candidate_id, 1)].loc["2026-01-01":]
        matrices.append(path["tqqq_weight"].to_numpy())
        index = path.index
    image = ax.imshow(
        np.vstack(matrices),
        aspect="auto",
        interpolation="nearest",
        cmap="Blues",
        vmin=0.0,
        vmax=1.0,
    )
    tick_dates = pd.date_range(index[0], index[-1], freq="MS")
    positions = [int(index.searchsorted(date)) for date in tick_dates]
    valid = [(position, date) for position, date in zip(positions, tick_dates) if position < len(index)]
    ax.set_xticks([position for position, _ in valid])
    ax.set_xticklabels([date.strftime("%Y-%m") for _, date in valid])
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_title("2026 daily TQQQ target weight with one-day additional delay", loc="left")
    colorbar = fig.colorbar(image, ax=ax, pad=0.01)
    colorbar.set_label("TQQQ target weight")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(OUTPUT / "reentry_2026_allocations.png", bbox_inches="tight")
    plt.close(fig)


def save_short_trend_neighborhood(robust: pd.DataFrame) -> None:
    family = robust[robust["method"] == "C_ndx_short_trend"].copy()
    parameters = family["parameters"].map(json.loads).apply(pd.Series)
    family = pd.concat([family, parameters], axis=1)
    neighborhood = (
        family.groupby(["ndx_sma", "confirmation_days"], as_index=False)
        .agg(
            worst_floor_2026_ytd=("min_2026_ytd_return", "min"),
            worst_floor_full_cagr=("min_delay_cagr", "min"),
            worst_floor_max_drawdown=("worst_max_drawdown", "min"),
            strong_solution_rate=("strong_2026_solution", "mean"),
        )
    )
    neighborhood.to_csv(
        OUTPUT / "reentry_2026_short_trend_neighborhood.csv", index=False
    )

    panels = [
        ("worst_floor_2026_ytd", "2026 YTD: worst of three SPY floors"),
        ("worst_floor_full_cagr", "Full CAGR: worst of three SPY floors"),
        ("worst_floor_max_drawdown", "Maximum drawdown: worst of three SPY floors"),
        ("strong_solution_rate", "Strong-solution rate across SPY floors"),
    ]
    windows = sorted(neighborhood["ndx_sma"].unique())
    confirmations = sorted(neighborhood["confirmation_days"].unique())
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=170)
    for ax, (column, title) in zip(axes.flat, panels):
        matrix = (
            neighborhood.pivot(
                index="ndx_sma", columns="confirmation_days", values=column
            )
            .reindex(index=windows, columns=confirmations)
            .to_numpy()
        )
        image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="cividis")
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                ax.text(
                    col,
                    row,
                    f"{matrix[row, col]:.0%}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if matrix[row, col] < np.nanmedian(matrix) else "black",
                )
        ax.set_xticks(np.arange(len(confirmations)), [int(value) for value in confirmations])
        ax.set_yticks(np.arange(len(windows)), [int(value) for value in windows])
        ax.set_xlabel("Confirmation days")
        ax.set_ylabel("Nasdaq short SMA (days)")
        ax.set_title(title, loc="left")
        colorbar = fig.colorbar(image, ax=ax, pad=0.01)
        colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.suptitle(
        "Nasdaq short-trend parameter neighborhood\n"
        "Each cell aggregates SPY floors of -5%, -8%, and -10% versus SMA150",
        x=0.05,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(
        OUTPUT / "reentry_2026_short_trend_neighborhood.png", bbox_inches="tight"
    )
    plt.close(fig)


def save_finalist_comparison(
    frame: pd.DataFrame,
    results: pd.DataFrame,
    paths: dict[tuple[str, int], pd.DataFrame],
) -> None:
    finalists = {
        "Baseline": "baseline",
        "Balanced: NDX SMA3, 5-day confirmation": "short_3_confirm_5_floor_0.08",
        "Capture-focused: NDX SMA3, 4-day confirmation": "short_3_confirm_4_floor_0.05",
    }
    ids = list(finalists.values())
    results[results["candidate_id"].isin(ids)].to_csv(
        OUTPUT / "reentry_2026_finalist_delay_results.csv", index=False
    )

    exports = []
    series = {}
    for label, candidate_id in finalists.items():
        path = paths[(candidate_id, 1)].loc["2026-01-01":].copy()
        normalized = 100.0 * path["nav_1000"] / path["nav_1000"].iloc[0]
        series[label] = normalized
        export = path.copy()
        export.insert(0, "date", export.index)
        export.insert(1, "series", label)
        exports.append(export.reset_index(drop=True))
    tqqq_return = frame.loc["2026-01-01":, "tqqq_return"]
    tqqq_path = 100.0 * (1.0 + tqqq_return).cumprod()
    tqqq_path = 100.0 * tqqq_path / tqqq_path.iloc[0]
    series["TQQQ buy-and-hold"] = tqqq_path
    tqqq_export = pd.DataFrame(
        {
            "date": tqqq_path.index,
            "series": "TQQQ buy-and-hold",
            "tqqq_weight": 1.0,
            "gross_return": tqqq_return,
            "trading_cost": 0.0,
            "net_return": tqqq_return,
            "nav_1000": 10.0 * tqqq_path,
        }
    )
    exports.append(tqqq_export.reset_index(drop=True))
    pd.concat(exports, ignore_index=True).to_csv(
        OUTPUT / "reentry_2026_finalist_paths.csv", index=False
    )

    colors = ["#444444", "#4C78A8", "#D98C4B", "#7A9E52"]
    styles = ["-", "--", "-.", ":"]
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(14, 7), dpi=170)
    for (label, values), color, style in zip(series.items(), colors, styles):
        ax.plot(
            values.index,
            values,
            label=label,
            color=color,
            linestyle=style,
            linewidth=2.0,
        )
    ax.axhline(100.0, color="#777777", linewidth=0.8)
    ax.set_title(
        "2026 finalists versus TQQQ buy-and-hold\n"
        "Strategy paths use one-day additional execution delay",
        loc="left",
    )
    ax.set_ylabel("Portfolio value (first 2026 trading day = 100)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "reentry_2026_finalist_comparison.png", bbox_inches="tight")
    plt.close(fig)

def main() -> None:
    frame, _ = load_inputs()
    sma150 = frame["spy"].rolling(150, min_periods=150).mean()
    trend = hysteresis_trend(frame["spy"], sma150, 0.03)
    vol40 = frame["ndx_return"].rolling(40, min_periods=40).std(ddof=1) * np.sqrt(252.0)
    base_signal = trend & (vol40 < 0.32)
    ndx_return = frame["ndx"].pct_change(fill_method=None)

    candidates: list[tuple[str, str, str, dict, pd.Series]] = [
        (
            "Baseline",
            "Baseline",
            "baseline",
            {"ma_window": 150, "vol_window": 40, "vol_threshold": 0.32, "tolerance": 0.03},
            base_signal.astype(float),
        )
    ]

    # A: Keep the original -3% exit, but allow earlier re-entry below the upper +3% band.
    for entry_band in [-0.03, -0.02, -0.01, 0.00, 0.01, 0.02]:
        override = (frame["spy"] > sma150 * (1.0 + entry_band)) & (vol40 < 0.32)
        weight = (base_signal | override).astype(float)
        candidates.append(
            (
                "A_relaxed_reentry",
                METHOD_LABELS["A_relaxed_reentry"],
                f"relaxed_{entry_band:+.2f}",
                {"reentry_band_vs_spy_sma150": entry_band},
                weight,
            )
        )

    # B: Re-enter after an observable rebound from a rolling NDX low while not too far below trend.
    for lookback in [5, 10, 15, 20]:
        recent_low = frame["ndx"].rolling(lookback, min_periods=lookback).min()
        rebound = frame["ndx"] / recent_low - 1.0
        for rebound_threshold in [0.04, 0.06, 0.08, 0.10]:
            for trend_floor in [0.05, 0.08]:
                override = (
                    (rebound >= rebound_threshold)
                    & (frame["spy"] > sma150 * (1.0 - trend_floor))
                    & (vol40 < 0.32)
                )
                candidates.append(
                    (
                        "B_drawdown_rebound",
                        METHOD_LABELS["B_drawdown_rebound"],
                        f"rebound_{lookback}_{rebound_threshold:.2f}_{trend_floor:.2f}",
                        {
                            "ndx_low_lookback": lookback,
                            "rebound_threshold": rebound_threshold,
                            "spy_trend_floor": trend_floor,
                        },
                        (base_signal | override).astype(float),
                    )
                )

    # C: Re-enter when the Nasdaq is above a short SMA, with 1-5 day confirmation.
    for short_window in [3, 5, 7, 10, 12, 15, 18, 20, 25, 30]:
        short_sma = frame["ndx"].rolling(short_window, min_periods=short_window).mean()
        for trend_floor in [0.05, 0.08, 0.10]:
            raw = (
                (frame["ndx"] > short_sma)
                & (frame["spy"] > sma150 * (1.0 - trend_floor))
                & (vol40 < 0.32)
            )
            for confirmation_days in [1, 2, 3, 4, 5]:
                override = consecutive_true(raw, confirmation_days)
                candidates.append(
                    (
                        "C_ndx_short_trend",
                        METHOD_LABELS["C_ndx_short_trend"],
                        f"short_{short_window}_confirm_{confirmation_days}_floor_{trend_floor:.2f}",
                        {
                            "ndx_sma": short_window,
                            "confirmation_days": confirmation_days,
                            "spy_floor_vs_sma150": -trend_floor,
                        },
                        (base_signal | override).astype(float),
                    )
                )

    # D: Use partial weights when multiple independent rebound conditions agree.
    score = pd.DataFrame(
        {
            "ndx_above_sma5": frame["ndx"] > frame["ndx"].rolling(5).mean(),
            "ndx_5d_positive": frame["ndx"] > frame["ndx"].shift(5),
            "spy_daily_positive": frame["spy"].pct_change(fill_method=None) > 0.0,
            "ndx_3d_momentum": ndx_return.rolling(3).sum() > 0.0,
        }
    ).sum(axis=1)
    for score_threshold in [2, 3, 4]:
        for partial_weight in [0.50, 0.75, 1.00]:
            override = (
                (score >= score_threshold)
                & (frame["spy"] > sma150 * 0.92)
                & (vol40 < 0.32)
            )
            weight = pd.Series(
                np.where(base_signal, 1.0, np.where(override, partial_weight, 0.0)),
                index=frame.index,
            )
            candidates.append(
                (
                    "D_staged_reentry",
                    METHOD_LABELS["D_staged_reentry"],
                    f"score_{score_threshold}_weight_{partial_weight:.2f}",
                    {"score_threshold": score_threshold, "reentry_weight": partial_weight},
                    weight,
                )
            )

    # E: A short-SMA cross starts a finite rebound window rather than a permanent override.
    for short_window in [3, 5, 10]:
        short_sma = frame["ndx"].rolling(short_window, min_periods=short_window).mean()
        raw = (
            (frame["ndx"] > short_sma)
            & (frame["ndx"].shift(1) <= short_sma.shift(1))
            & (frame["spy"] > sma150 * 0.92)
            & (vol40 < 0.32)
        )
        for holding_days in [5, 10, 15, 20]:
            for weight_value in [0.50, 1.00]:
                weight = timed_rebound_weight(base_signal, raw, holding_days, weight_value)
                candidates.append(
                    (
                        "E_timed_rebound",
                        METHOD_LABELS["E_timed_rebound"],
                        f"timed_{short_window}_{holding_days}_{weight_value:.2f}",
                        {
                            "ndx_sma_cross": short_window,
                            "holding_days": holding_days,
                            "reentry_weight": weight_value,
                        },
                        weight,
                    )
                )

    rows = []
    paths: dict[tuple[str, int], pd.DataFrame] = {}
    for method, label, candidate_id, parameters, weight in candidates:
        for delay in DELAYS:
            metrics, path = backtest_weights(frame, weight, delay)
            rows.append(
                {
                    "method": method,
                    "method_label": label,
                    "candidate_id": candidate_id,
                    "parameters": json.dumps(parameters, sort_keys=True),
                    "delay": delay,
                    **metrics,
                }
            )
            paths[(candidate_id, delay)] = path

    results = pd.DataFrame(rows)
    robust = aggregate_candidates(results)
    robust["passes_original_hard_requirements"] = (
        (robust["min_delay_cagr"] >= FULL_CAGR_FLOOR)
        & (robust["min_post_2008_cagr"] > POST_2008_CAGR_FLOOR)
        & (robust["worst_dotcom_drawdown"] >= DOTCOM_DRAWDOWN_FLOOR)
        & (robust["delay_cagr_gap"] <= 0.05)
    )
    robust["solves_2026"] = robust["min_2026_ytd_return"] > 0.0
    robust["passes_all_requirements"] = (
        robust["passes_original_hard_requirements"] & robust["solves_2026"]
    )
    tqqq_2026_ytd = float(
        (1.0 + frame.loc["2026-01-01":, "tqqq_return"]).prod() - 1.0
    )
    robust["tqqq_2026_capture_ratio"] = (
        robust["min_2026_ytd_return"] / tqqq_2026_ytd
    )
    robust["keeps_full_max_drawdown_near_60pct"] = (
        robust["worst_max_drawdown"] >= -0.60
    )
    robust["strong_2026_solution"] = (
        robust["passes_all_requirements"]
        & robust["keeps_full_max_drawdown_near_60pct"]
        & (robust["tqqq_2026_capture_ratio"] >= 0.50)
    )

    selected_rows = [robust[robust["method"] == "Baseline"].iloc[0]]
    for method in METHOD_LABELS:
        group = robust[robust["method"] == method]
        passing = group[group["passes_all_requirements"]]
        strong = passing[passing["strong_2026_solution"]]
        safe_passing = passing[passing["keeps_full_max_drawdown_near_60pct"]]
        if not strong.empty:
            winner = strong.sort_values(
                ["min_delay_cagr", "worst_max_drawdown", "delay_cagr_gap"],
                ascending=[False, False, True],
            ).iloc[0]
        else:
            pool = safe_passing if not safe_passing.empty else passing
            if pool.empty:
                pool = group
            winner = pool.sort_values(
                [
                    "passes_all_requirements",
                    "min_2026_ytd_return",
                    "worst_max_drawdown",
                    "min_delay_cagr",
                ],
                ascending=False,
            ).iloc[0]
        selected_rows.append(winner)
    selected = pd.DataFrame(selected_rows).reset_index(drop=True)

    # Baseline implementation must reproduce the previously saved baseline.
    saved = pd.read_csv(
        OUTPUT / "recent_improvement_candidate_results.csv"
    )
    for delay in DELAYS:
        expected = saved[(saved["candidate_id"] == "baseline") & (saved["delay"] == delay)].iloc[0]
        actual = results[(results["candidate_id"] == "baseline") & (results["delay"] == delay)].iloc[0]
        for metric in ["cagr", "post_2008_cagr", "return_2026_ytd", "max_drawdown"]:
            if abs(float(expected[metric]) - float(actual[metric])) > 1e-12:
                raise AssertionError(f"Baseline mismatch: delay={delay}, metric={metric}")

    save_outputs(results, robust, selected, paths)
    save_short_trend_neighborhood(robust)
    save_finalist_comparison(frame, results, paths)
    print(selected[
        [
            "method_label",
            "parameters",
            "passes_all_requirements",
            "strong_2026_solution",
            "min_2026_ytd_return",
            "tqqq_2026_capture_ratio",
            "min_delay_cagr",
            "min_post_2008_cagr",
            "worst_max_drawdown",
            "worst_dotcom_drawdown",
            "delay_cagr_gap",
        ]
    ].to_string(index=False))
    print(f"Candidates: {len(robust)}; delay cases: {len(results)}")
    print(f"All-requirement passers: {int(robust['passes_all_requirements'].sum())}")
    print(f"Strong 2026 solutions: {int(robust['strong_2026_solution'].sum())}")


if __name__ == "__main__":
    main()
