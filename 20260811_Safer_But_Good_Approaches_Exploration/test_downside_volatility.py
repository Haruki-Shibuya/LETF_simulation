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

from explore_recent_performance_methods import aggregate_candidates, backtest_weights  # noqa: E402
from test_2026_reentry_5_methods import consecutive_true  # noqa: E402
from validate_parameters import DELAYS, hysteresis_trend, load_inputs  # noqa: E402


TOTAL_VOL_WINDOW = 40
TOTAL_VOL_THRESHOLD = 0.32
SHORT_SMA_WINDOW = 3
CONFIRMATION_DAYS = 5
SPY_FLOOR = -0.08

DOWNSIDE_WINDOWS = list(range(20, 81, 5))
DOWNSIDE_THRESHOLDS = [value / 100.0 for value in range(10, 31)]


def downside_deviation(returns: pd.Series, window: int) -> pd.Series:
    """Annualized lower partial deviation versus a 0% daily target."""
    lower_partial_squared = returns.clip(upper=0.0).pow(2)
    return (
        lower_partial_squared.rolling(window, min_periods=window).mean().pow(0.5)
        * np.sqrt(252.0)
    )


def build_weight(
    frame: pd.DataFrame,
    risk_measure: pd.Series,
    threshold: float,
) -> pd.Series:
    sma150 = frame["spy"].rolling(150, min_periods=150).mean()
    trend = hysteresis_trend(frame["spy"], sma150, 0.03)
    risk_ok = risk_measure < threshold
    base_risk_on = trend & risk_ok

    ndx_sma3 = frame["ndx"].rolling(
        SHORT_SMA_WINDOW, min_periods=SHORT_SMA_WINDOW
    ).mean()
    early_raw = (
        (frame["ndx"] > ndx_sma3)
        & (frame["spy"] > sma150 * (1.0 + SPY_FLOOR))
        & risk_ok
    )
    early_reentry = consecutive_true(early_raw, CONFIRMATION_DAYS)
    return (base_risk_on | early_reentry).astype(float)


def add_acceptance_columns(robust: pd.DataFrame, tqqq_2026_ytd: float) -> pd.DataFrame:
    output = robust.copy()
    output["passes_original_requirements"] = (
        (output["min_delay_cagr"] >= 0.30)
        & (output["min_post_2008_cagr"] > 0.30)
        & (output["worst_dotcom_drawdown"] >= -0.60)
        & (output["delay_cagr_gap"] <= 0.05)
    )
    output["positive_2026_both_delays"] = output["min_2026_ytd_return"] > 0.0
    output["tqqq_2026_capture_ratio"] = (
        output["min_2026_ytd_return"] / tqqq_2026_ytd
    )
    output["strong_solution"] = (
        output["passes_original_requirements"]
        & output["positive_2026_both_delays"]
        & (output["worst_max_drawdown"] >= -0.60)
        & (output["tqqq_2026_capture_ratio"] >= 0.50)
    )
    return output


def parameter_columns(robust: pd.DataFrame) -> pd.DataFrame:
    output = robust.copy()
    parameters = output["parameters"].map(json.loads).apply(pd.Series)
    return pd.concat([output, parameters], axis=1)


def select_plateau_candidate(downside: pd.DataFrame) -> pd.Series:
    """Select the strongest result, then prefer a broad local neighborhood."""
    strong = downside[downside["strong_solution"]].copy()
    if strong.empty:
        raise RuntimeError("No downside-volatility candidate passed the strong criteria")

    lookup = strong.set_index(["downside_window", "downside_threshold"])
    neighborhood_scores = []
    for row in strong.itertuples(index=False):
        neighbor_keys = [
            (row.downside_window + window_offset, round(row.downside_threshold + threshold_offset, 2))
            for window_offset in (-5, 0, 5)
            for threshold_offset in (-0.01, 0.0, 0.01)
        ]
        neighbors = [lookup.loc[key] for key in neighbor_keys if key in lookup.index]
        neighborhood_scores.append(
            {
                "candidate_id": row.candidate_id,
                "strong_neighbor_count": len(neighbors),
                "neighbor_min_cagr": min(float(item["min_delay_cagr"]) for item in neighbors),
                "neighbor_worst_drawdown": min(
                    float(item["worst_max_drawdown"]) for item in neighbors
                ),
            }
        )
    scores = pd.DataFrame(neighborhood_scores)
    strong = strong.merge(scores, on="candidate_id", how="left")
    winner = strong.sort_values(
        [
            "strong_neighbor_count",
            "neighbor_min_cagr",
            "min_delay_cagr",
            "worst_max_drawdown",
            "delay_cagr_gap",
        ],
        ascending=[False, False, False, False, True],
    ).iloc[0]
    return winner


def save_heatmaps(downside: pd.DataFrame, winner: pd.Series) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    panels = [
        ("min_delay_cagr", "Full-period CAGR: worse of 0/1-day delays", "viridis"),
        ("worst_max_drawdown", "Maximum drawdown: worse of 0/1-day delays", "cividis"),
        ("min_2026_ytd_return", "2026 YTD: worse of 0/1-day delays", "viridis"),
        ("strong_solution", "Passes all strong criteria", "Greens"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=170)
    windows = sorted(downside["downside_window"].unique())
    thresholds = sorted(downside["downside_threshold"].unique())
    for ax, (column, title, cmap) in zip(axes.flat, panels):
        matrix = (
            downside.pivot(
                index="downside_window", columns="downside_threshold", values=column
            )
            .reindex(index=windows, columns=thresholds)
            .to_numpy(dtype=float)
        )
        image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap=cmap)
        winner_row = windows.index(int(winner["downside_window"]))
        winner_col = thresholds.index(float(winner["downside_threshold"]))
        ax.scatter(
            winner_col,
            winner_row,
            marker="s",
            facecolors="none",
            edgecolors="#E45756",
            s=120,
            linewidths=2.0,
        )
        ax.set_xticks(
            np.arange(0, len(thresholds), 2),
            [f"{thresholds[i]:.0%}" for i in range(0, len(thresholds), 2)],
            rotation=45,
            ha="right",
        )
        ax.set_yticks(np.arange(len(windows)), windows)
        ax.set_xlabel("Downside-deviation threshold")
        ax.set_ylabel("Lookback (trading days)")
        ax.set_title(title, loc="left")
        colorbar = fig.colorbar(image, ax=ax, pad=0.01)
        if column != "strong_solution":
            colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.suptitle(
        "Downside-deviation parameter neighborhood\n"
        "Red outline is the highest worst-delay CAGR candidate; 1996-01-02 to 2026-04-17",
        x=0.05,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUTPUT / "downside_volatility_parameter_heatmaps.png", bbox_inches="tight")
    plt.close(fig)


def save_comparison_chart(
    results: pd.DataFrame,
    paths: dict[tuple[str, int], pd.DataFrame],
    best_id: str,
    plateau_id: str,
) -> None:
    labels = {
        "total_vol_40_32": "Current: total volatility 40d < 32%",
        best_id: "Downside: highest worst-delay CAGR",
        plateau_id: "Downside: broad-neighborhood representative",
    }
    colors = {
        "total_vol_40_32": "#4C78A8",
        best_id: "#E45756",
        plateau_id: "#F2A541",
    }
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), dpi=170)
    for candidate_id, label in labels.items():
        path = paths[(candidate_id, 1)]
        axes[0].plot(
            path.index,
            path["nav_1000"],
            label=label,
            color=colors[candidate_id],
            linewidth=1.7,
        )
        recent = path.loc["2025-01-01":]
        normalized = 100.0 * recent["nav_1000"] / recent["nav_1000"].iloc[0]
        axes[1].plot(
            normalized.index,
            normalized,
            label=label,
            color=colors[candidate_id],
            linewidth=1.9,
        )
    axes[0].set_yscale("log")
    axes[0].set_title("Full-period portfolio growth (1-day additional delay)", loc="left")
    axes[0].set_ylabel("Value from $1,000 (log scale)")
    axes[0].legend(frameon=False)
    axes[1].axhline(100.0, color="#777777", linewidth=0.8)
    axes[1].set_title("Recent portfolio path (1-day additional delay)", loc="left")
    axes[1].set_ylabel("Value (first 2025 trading day = 100)")
    axes[1].set_xlabel("Date")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "downside_volatility_strategy_comparison.png", bbox_inches="tight")
    plt.close(fig)

    selected = results[results["candidate_id"].isin(labels)].copy()
    selected.to_csv(OUTPUT / "downside_volatility_selected_delay_results.csv", index=False)

    annual_rows = []
    for candidate_id, label in labels.items():
        for delay in DELAYS:
            path = paths[(candidate_id, delay)]
            annual = (1.0 + path["net_return"]).groupby(path.index.year).prod() - 1.0
            for year, value in annual.items():
                annual_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "label": label,
                        "delay": delay,
                        "year": int(year),
                        "annual_return": float(value),
                    }
                )
    annual = pd.DataFrame(annual_rows)
    annual.to_csv(OUTPUT / "downside_volatility_annual_returns.csv", index=False)

    comparison = annual.pivot(
        index=["delay", "year"], columns="candidate_id", values="annual_return"
    ).reset_index()
    for candidate_id in [best_id, plateau_id]:
        comparison[f"{candidate_id}_minus_current"] = (
            comparison[candidate_id] - comparison["total_vol_40_32"]
        )
    comparison.to_csv(
        OUTPUT / "downside_volatility_annual_return_differences.csv", index=False
    )

    delay_one = comparison[comparison["delay"] == 1]
    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=170)
    ax.bar(
        delay_one["year"] - 0.18,
        delay_one[f"{best_id}_minus_current"],
        width=0.36,
        label=labels[best_id],
        color=colors[best_id],
    )
    ax.bar(
        delay_one["year"] + 0.18,
        delay_one[f"{plateau_id}_minus_current"],
        width=0.36,
        label=labels[plateau_id],
        color=colors[plateau_id],
    )
    ax.axhline(0.0, color="#333333", linewidth=0.9)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title(
        "Annual return difference versus the current total-volatility strategy",
        loc="left",
    )
    ax.set_ylabel("Downside strategy minus current strategy")
    ax.set_xlabel("Year")
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "downside_volatility_annual_differences.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    frame, _ = load_inputs()
    total_volatility = (
        frame["ndx_return"]
        .rolling(TOTAL_VOL_WINDOW, min_periods=TOTAL_VOL_WINDOW)
        .std(ddof=1)
        * np.sqrt(252.0)
    )
    tqqq_2026_ytd = float((1.0 + frame.loc["2026":, "tqqq_return"]).prod() - 1.0)
    downside_40 = downside_deviation(frame["ndx_return"], 40)
    diagnostic_rows = []
    for threshold in [value / 100.0 for value in range(14, 29, 2)]:
        diagnostic_rows.append(
            {
                "downside_window": 40,
                "downside_threshold": threshold,
                "total_vol_threshold": TOTAL_VOL_THRESHOLD,
                "total_vol_below_threshold_share": float(
                    (total_volatility < TOTAL_VOL_THRESHOLD).mean()
                ),
                "downside_below_threshold_share": float(
                    (downside_40 < threshold).mean()
                ),
                "same_daily_classification_share": float(
                    ((downside_40 < threshold) == (total_volatility < TOTAL_VOL_THRESHOLD)).mean()
                ),
                "full_period_measure_correlation": float(
                    total_volatility.corr(downside_40)
                ),
                "total_vol_2026_min": float(total_volatility.loc["2026":].min()),
                "total_vol_2026_max": float(total_volatility.loc["2026":].max()),
                "downside_2026_min": float(downside_40.loc["2026":].min()),
                "downside_2026_max": float(downside_40.loc["2026":].max()),
            }
        )
    pd.DataFrame(diagnostic_rows).to_csv(
        OUTPUT / "downside_volatility_measure_diagnostics.csv", index=False
    )

    candidate_specs: list[tuple[str, str, str, dict, pd.Series]] = []
    total_weight = build_weight(frame, total_volatility, TOTAL_VOL_THRESHOLD)
    candidate_specs.append(
        (
            "total_volatility",
            "Current total-volatility strategy",
            "total_vol_40_32",
            {"volatility_type": "total", "window": 40, "threshold": 0.32},
            total_weight,
        )
    )

    downside_cache = {
        window: downside_deviation(frame["ndx_return"], window)
        for window in DOWNSIDE_WINDOWS
    }
    for window in DOWNSIDE_WINDOWS:
        for threshold in DOWNSIDE_THRESHOLDS:
            candidate_specs.append(
                (
                    "downside_deviation",
                    "Downside-deviation strategy",
                    f"downside_{window}_{threshold:.2f}",
                    {
                        "volatility_type": "downside_deviation_zero_target",
                        "downside_window": window,
                        "downside_threshold": threshold,
                    },
                    build_weight(frame, downside_cache[window], threshold),
                )
            )

    rows = []
    paths: dict[tuple[str, int], pd.DataFrame] = {}
    for method, label, candidate_id, parameters, weight in candidate_specs:
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
    robust = add_acceptance_columns(aggregate_candidates(results), tqqq_2026_ytd)
    downside = parameter_columns(
        robust[robust["method"] == "downside_deviation"].copy()
    )
    best = downside[downside["strong_solution"]].sort_values(
        ["min_delay_cagr", "worst_max_drawdown", "delay_cagr_gap"],
        ascending=[False, False, True],
    ).iloc[0]
    plateau = select_plateau_candidate(downside)
    best_id = str(best["candidate_id"])
    plateau_id = str(plateau["candidate_id"])

    results.to_csv(OUTPUT / "downside_volatility_candidate_results.csv", index=False)
    robust.to_csv(OUTPUT / "downside_volatility_robust_summary.csv", index=False)
    downside.to_csv(OUTPUT / "downside_volatility_parameter_grid.csv", index=False)
    recommendations = pd.DataFrame(
        [
            {**best.to_dict(), "selection_role": "highest_worst_delay_cagr"},
            {**plateau.to_dict(), "selection_role": "broad_neighborhood"},
        ]
    )
    recommendations.to_csv(
        OUTPUT / "downside_volatility_recommendation.csv", index=False
    )

    path_exports = []
    for candidate_id in ["total_vol_40_32", best_id, plateau_id]:
        for delay in DELAYS:
            export = paths[(candidate_id, delay)].copy()
            export.insert(0, "date", export.index)
            export.insert(1, "candidate_id", candidate_id)
            export.insert(2, "delay", delay)
            path_exports.append(export.reset_index(drop=True))
    pd.concat(path_exports, ignore_index=True).to_csv(
        OUTPUT / "downside_volatility_selected_paths.csv", index=False
    )

    save_heatmaps(downside, best)
    save_comparison_chart(results, paths, best_id, plateau_id)

    current = robust[robust["candidate_id"] == "total_vol_40_32"].iloc[0]
    print("Current total volatility")
    print(current.to_string())
    print("\nHighest-CAGR downside deviation")
    print(best.to_string())
    print("\nBroad-neighborhood downside deviation")
    print(plateau.to_string())
    print(f"\nDownside candidates: {len(downside)}")
    print(f"Strong downside candidates: {int(downside['strong_solution'].sum())}")


if __name__ == "__main__":
    main()
