from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

from validate_parameters import (
    DELAYS,
    INITIAL_CAPITAL,
    OUTPUT,
    RECOMMENDED,
    TRADING_COST,
    backtest,
    hysteresis_trend,
    load_inputs,
)


FRED_BAA10Y_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv?"
    "id=BAA10Y&cosd=1995-01-01&coed=2026-04-17"
)
FRED_BAA10Y_PATH = OUTPUT / "data" / "fred_baa10y.csv"
RECENT_DAYS = 252
DOTCOM_SURVIVAL_FLOOR = -0.60


def load_credit_spread(index: pd.DatetimeIndex) -> pd.Series:
    """Load the daily Moody's Baa minus 10-year Treasury spread from FRED."""
    if not FRED_BAA10Y_PATH.exists():
        request = Request(FRED_BAA10Y_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            FRED_BAA10Y_PATH.write_bytes(response.read())

    raw = pd.read_csv(FRED_BAA10Y_PATH, parse_dates=["observation_date"])
    raw["BAA10Y"] = pd.to_numeric(raw["BAA10Y"], errors="coerce")
    spread = raw.set_index("observation_date")["BAA10Y"].sort_index()
    aligned = spread.reindex(index).ffill()
    if aligned.isna().any():
        raise ValueError("BAA10Y does not cover the full simulation index")
    return aligned


def asymmetric_hysteresis(
    price: pd.Series,
    sma: pd.Series,
    exit_tolerance: float,
    entry_tolerance: float,
) -> pd.Series:
    """Exit below a lower band and re-enter above a separately chosen band."""
    output = np.zeros(len(price), dtype=bool)
    state = False
    initialized = False

    for position, (current_price, current_sma) in enumerate(zip(price, sma)):
        if not np.isfinite(current_price) or not np.isfinite(current_sma):
            output[position] = False
            continue
        if not initialized:
            state = bool(current_price > current_sma)
            initialized = True
        elif state and current_price < current_sma * (1.0 - exit_tolerance):
            state = False
        elif not state and current_price > current_sma * (1.0 + entry_tolerance):
            state = True
        output[position] = state
    return pd.Series(output, index=price.index)


def delayed_exit(signal: pd.Series, confirmation_days: int) -> pd.Series:
    """Turn on immediately, but require N consecutive false closes to turn off."""
    state = False
    false_streak = 0
    output = np.zeros(len(signal), dtype=bool)
    for position, value in enumerate(signal.fillna(False).astype(bool)):
        if value:
            state = True
            false_streak = 0
        elif state:
            false_streak += 1
            if false_streak >= confirmation_days:
                state = False
        output[position] = state
    return pd.Series(output, index=signal.index)


def annualized_cagr(returns: pd.Series) -> float:
    if len(returns) < 2:
        return np.nan
    growth = float((1.0 + returns).prod())
    years = (returns.index[-1] - returns.index[0]).days / 365.2425
    return growth ** (1.0 / years) - 1.0


def continued_subperiod_cagr(returns: pd.Series, anchor: pd.Timestamp) -> float:
    """CAGR after an anchor close while retaining the pre-anchor strategy state."""
    anchor_dates = returns.index[returns.index <= anchor]
    if anchor_dates.empty:
        return np.nan
    actual_anchor = anchor_dates[-1]
    subperiod = returns.loc[returns.index > actual_anchor]
    growth = float((1.0 + subperiod).prod())
    years = (subperiod.index[-1] - actual_anchor).days / 365.2425
    return growth ** (1.0 / years) - 1.0


def drawdown_min(returns: pd.Series) -> float:
    nav = (1.0 + returns).cumprod()
    return float((nav / nav.cummax() - 1.0).min())


def backtest_weights(
    frame: pd.DataFrame,
    observed_tqqq_weight: pd.Series,
    delay: int,
) -> tuple[dict[str, float], pd.DataFrame]:
    """Backtest daily target weights with allocation and daily rebalance costs."""
    weight = (
        observed_tqqq_weight.shift(delay + 1, fill_value=0.0)
        .astype(float)
        .clip(0.0, 1.0)
    )
    defensive_weight = 1.0 - weight
    components = frame[["kmlmsim_return", "gold_return", "bond_return"]]
    gross = weight * frame["tqqq_return"] + defensive_weight * components.mean(axis=1)

    # One-way turnover for changes in the target TQQQ sleeve. The first day
    # allocates the whole portfolio from cash, matching the original model.
    allocation_turnover = weight.diff().abs()
    allocation_turnover.iloc[0] = 1.0

    # Daily close rebalance back to TQQQ=w and each defensive asset=(1-w)/3.
    target = pd.DataFrame(
        {
            "tqqq": weight,
            "kmlmsim": defensive_weight / 3.0,
            "gold": defensive_weight / 3.0,
            "bond": defensive_weight / 3.0,
        },
        index=frame.index,
    )
    asset_returns = pd.DataFrame(
        {
            "tqqq": frame["tqqq_return"],
            "kmlmsim": frame["kmlmsim_return"],
            "gold": frame["gold_return"],
            "bond": frame["bond_return"],
        },
        index=frame.index,
    )
    post_return_weights = target.mul(1.0 + asset_returns).div(1.0 + gross, axis=0)
    rebalance_turnover = 0.5 * post_return_weights.sub(target).abs().sum(axis=1)
    costs = TRADING_COST * (allocation_turnover + rebalance_turnover)
    net = gross - costs

    full = annualized_cagr(net)
    post_2008 = continued_subperiod_cagr(net, pd.Timestamp("2007-12-31"))
    recent = net.iloc[-RECENT_DAYS:]
    ytd_2026 = net.loc[net.index >= pd.Timestamp("2026-01-01")]
    dotcom = net.loc["2000-01-01":"2003-12-31"]
    metrics = {
        "cagr": full,
        "post_2008_cagr": post_2008,
        "volatility": float(net.std(ddof=1) * np.sqrt(252.0)),
        "max_drawdown": drawdown_min(net),
        "dotcom_max_drawdown": drawdown_min(dotcom),
        "trailing_252_return": float((1.0 + recent).prod() - 1.0),
        "return_2026_ytd": float((1.0 + ytd_2026).prod() - 1.0),
        "ending_value_1000": float(INITIAL_CAPITAL * (1.0 + net).prod()),
        "average_tqqq_weight": float(weight.mean()),
        "weight_changes": int(weight.ne(weight.shift()).sum()),
        "total_turnover": float((allocation_turnover + rebalance_turnover).sum()),
    }
    path = pd.DataFrame(
        {
            "tqqq_weight": weight,
            "gross_return": gross,
            "trading_cost": costs,
            "net_return": net,
            "nav_1000": INITIAL_CAPITAL * (1.0 + net).cumprod(),
        }
    )
    return metrics, path


def parameter_text(parameters: dict[str, float | int]) -> str:
    return json.dumps(parameters, ensure_ascii=False, sort_keys=True)


def aggregate_candidates(results: pd.DataFrame) -> pd.DataFrame:
    aggregated = (
        results.groupby(
            ["method", "method_label", "candidate_id", "parameters"], as_index=False
        )
        .agg(
            min_delay_cagr=("cagr", "min"),
            mean_delay_cagr=("cagr", "mean"),
            min_post_2008_cagr=("post_2008_cagr", "min"),
            min_trailing_252_return=("trailing_252_return", "min"),
            min_2026_ytd_return=("return_2026_ytd", "min"),
            worst_volatility=("volatility", "max"),
            worst_max_drawdown=("max_drawdown", "min"),
            worst_dotcom_drawdown=("dotcom_max_drawdown", "min"),
            min_average_tqqq_weight=("average_tqqq_weight", "min"),
            max_average_tqqq_weight=("average_tqqq_weight", "max"),
            min_turnover=("total_turnover", "min"),
            max_turnover=("total_turnover", "max"),
            min_delay_cagr_value=("cagr", "min"),
            max_delay_cagr_value=("cagr", "max"),
        )
    )
    aggregated["delay_cagr_gap"] = (
        aggregated["max_delay_cagr_value"] - aggregated["min_delay_cagr_value"]
    )
    aggregated["passes_hard_requirements"] = (
        (aggregated["min_delay_cagr"] >= 0.30)
        & (aggregated["min_post_2008_cagr"] > 0.30)
        & (aggregated["worst_dotcom_drawdown"] >= DOTCOM_SURVIVAL_FLOOR)
        & (aggregated["delay_cagr_gap"] <= 0.05)
    )
    return aggregated


def select_method_winners(aggregated: pd.DataFrame) -> pd.DataFrame:
    winners = []
    for method in [
        "A_asymmetric_reentry",
        "B_exit_confirmation",
        "C_partial_riskoff",
        "D_shallow_rebound",
        "E_credit_health",
    ]:
        group = aggregated[aggregated["method"] == method].copy()
        feasible = group[group["passes_hard_requirements"]]
        selection_pool = feasible if not feasible.empty else group
        winner = selection_pool.sort_values(
            [
                "min_trailing_252_return",
                "min_2026_ytd_return",
                "min_delay_cagr",
            ],
            ascending=False,
        ).iloc[0]
        winners.append(winner)
    return pd.DataFrame(winners).reset_index(drop=True)


def save_comparison_plots(
    selected: pd.DataFrame,
    selected_paths: dict[tuple[str, int], pd.DataFrame],
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    baseline = selected[selected["method"] == "Baseline"]
    methods = selected[selected["method"] != "Baseline"]
    ordered = pd.concat([baseline, methods], ignore_index=True)

    labels = ordered["method_label"].tolist()
    colors = ["#444444", "#4C78A8", "#E0A458", "#D98C4B", "#7A9E52", "#B279A2"]
    hatches = ["", "//", "\\\\", "..", "xx", "++"]

    panels = [
        ("min_delay_cagr", "Full-period CAGR", 0.30),
        ("min_post_2008_cagr", "CAGR from 2008", 0.30),
        ("min_trailing_252_return", "Trailing 252-day return", 0.0),
        ("worst_dotcom_drawdown", "Dot-com maximum drawdown", DOTCOM_SURVIVAL_FLOOR),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), dpi=170)
    for ax, (column, title, threshold) in zip(axes.flat, panels):
        values = ordered[column].to_numpy()
        bars = ax.barh(
            np.arange(len(labels)),
            values,
            color=colors,
            edgecolor="#333333",
            linewidth=0.7,
        )
        for bar, hatch, value in zip(bars, hatches, values):
            bar.set_hatch(hatch)
            offset = 0.008 if value >= 0 else -0.008
            ax.text(
                value + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1%}",
                va="center",
                ha="left" if value >= 0 else "right",
                fontsize=9,
                color="#222222",
            )
        ax.axvline(0.0, color="#222222", linewidth=0.9)
        if threshold != 0.0:
            ax.axvline(threshold, color="#222222", linestyle="--", linewidth=1.1)
        ax.set_title(title, loc="left")
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        ax.set_yticks(np.arange(len(labels)), labels)
        ax.invert_yaxis()
        minimum = min(values.min(), threshold, 0.0)
        maximum = max(values.max(), threshold, 0.0)
        padding = max(0.05, (maximum - minimum) * 0.18)
        ax.set_xlim(minimum - padding, maximum + padding)
    fig.suptitle(
        "Five recent-performance improvements versus the 150/40/32%/3% baseline\n"
        "Each bar is the worse result across normal and one-day-additional execution delays",
        x=0.05,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUTPUT / "five_method_metric_comparison.png", bbox_inches="tight")
    plt.close(fig)

    recent_start = next(iter(selected_paths.values())).index[-RECENT_DAYS]
    line_styles = ["-", "--", "-.", ":", (0, (5, 2)), (0, (1, 1))]

    fig, ax = plt.subplots(figsize=(14, 7), dpi=170)
    for position, row in enumerate(ordered.itertuples(index=False)):
        path = selected_paths[(row.candidate_id, 1)].loc[recent_start:]
        normalized = 100.0 * path["nav_1000"] / path["nav_1000"].iloc[0]
        ax.plot(
            normalized.index,
            normalized,
            label=row.method_label,
            color=colors[position],
            linestyle=line_styles[position],
            linewidth=1.8,
        )
    ax.axhline(100.0, color="#777777", linewidth=0.8)
    ax.set_title("Selected methods: trailing 252-trading-day portfolio paths", loc="left")
    ax.set_ylabel("Portfolio value (start = 100)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "five_method_recent_paths.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 7), dpi=170)
    for position, row in enumerate(ordered.itertuples(index=False)):
        path = selected_paths[(row.candidate_id, 1)]
        ax.plot(
            path.index,
            path["nav_1000"],
            label=row.method_label,
            color=colors[position],
            linestyle=line_styles[position],
            linewidth=1.45,
        )
    ax.set_yscale("log")
    ax.set_title("Selected methods: full portfolio paths with one-day additional delay", loc="left")
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "five_method_full_paths.png", bbox_inches="tight")
    plt.close(fig)

    heat_start = pd.Timestamp("2025-01-01")
    heat_rows = []
    for row in ordered.itertuples(index=False):
        weight = selected_paths[(row.candidate_id, 1)].loc[heat_start:, "tqqq_weight"]
        heat_rows.append(weight.to_numpy())
    heat = np.vstack(heat_rows)
    heat_index = selected_paths[(ordered.iloc[0]["candidate_id"], 1)].loc[heat_start:].index
    fig, ax = plt.subplots(figsize=(14, 5.8), dpi=170)
    image = ax.imshow(
        heat,
        aspect="auto",
        interpolation="nearest",
        cmap="Blues",
        vmin=0.0,
        vmax=1.0,
    )
    tick_dates = pd.date_range(heat_index[0], heat_index[-1], freq="2MS")
    tick_positions = [int(heat_index.searchsorted(date)) for date in tick_dates]
    valid = [(position, date) for position, date in zip(tick_positions, tick_dates) if position < len(heat_index)]
    ax.set_xticks([position for position, _ in valid])
    ax.set_xticklabels([date.strftime("%Y-%m") for _, date in valid], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(labels)), labels)
    ax.set_title("Daily TQQQ target weights in 2025–2026 (one-day additional delay)", loc="left")
    colorbar = fig.colorbar(image, ax=ax, pad=0.01)
    colorbar.set_label("TQQQ target weight")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(OUTPUT / "five_method_recent_allocations.png", bbox_inches="tight")
    plt.close(fig)


def save_annual_return_comparison(
    selected_paths: dict[tuple[str, int], pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare baseline and the 10% risk-off TQQQ sleeve by calendar year."""
    comparison_ids = {
        "Baseline": "baseline",
        "10% TQQQ sleeve": "partial_riskoff_0.10",
    }
    annual_series = {}
    for label, candidate_id in comparison_ids.items():
        path = selected_paths[(candidate_id, 1)]
        annual_series[label] = (
            (1.0 + path["net_return"])
            .groupby(path.index.year)
            .prod()
            .sub(1.0)
        )

    annual = pd.DataFrame(annual_series)
    annual.index.name = "year"
    final_year = int(annual.index.max())
    annual["difference_sleeve_minus_baseline"] = (
        annual["10% TQQQ sleeve"] - annual["Baseline"]
    )
    annual["complete_year"] = annual.index < final_year
    annual.to_csv(OUTPUT / "baseline_vs_partial10_delay1_annual_returns.csv")

    complete = annual.loc[annual["complete_year"], list(comparison_ids)]
    summary_rows = []
    for label in comparison_ids:
        values = complete[label]
        summary_rows.append(
            {
                "strategy": label,
                "complete_years": int(values.shape[0]),
                "mean_annual_return": float(values.mean()),
                "median_annual_return": float(values.median()),
                "annual_return_std": float(values.std(ddof=1)),
                "minimum_annual_return": float(values.min()),
                "minimum_year": int(values.idxmin()),
                "maximum_annual_return": float(values.max()),
                "maximum_year": int(values.idxmax()),
                "positive_years": int((values > 0.0).sum()),
                "negative_years": int((values < 0.0).sum()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(
        OUTPUT / "baseline_vs_partial10_delay1_annual_summary.csv", index=False
    )

    plt.style.use("seaborn-v0_8-whitegrid")
    baseline_color = "#555555"
    sleeve_color = "#4C78A8"
    ink = "#222222"
    years = annual.index.to_numpy()
    x = np.arange(len(years))
    width = 0.38

    fig, ax = plt.subplots(figsize=(15, 7.5), dpi=170)
    baseline_bars = ax.bar(
        x - width / 2.0,
        annual["Baseline"],
        width,
        label="Baseline",
        color=baseline_color,
        edgecolor=ink,
        linewidth=0.6,
    )
    sleeve_bars = ax.bar(
        x + width / 2.0,
        annual["10% TQQQ sleeve"],
        width,
        label="10% TQQQ sleeve in risk-off",
        color=sleeve_color,
        edgecolor=ink,
        linewidth=0.6,
        hatch="//",
    )
    baseline_bars[-1].set_hatch("...")
    sleeve_bars[-1].set_hatch("xx")
    for bars, values in [
        (baseline_bars, annual["Baseline"]),
        (sleeve_bars, annual["10% TQQQ sleeve"]),
    ]:
        for bar, value, year in zip(bars, values, years):
            if value < 0.0 or year == final_year:
                offset = 0.025 if value >= 0.0 else -0.025
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    value + offset,
                    f"{value:.0%}",
                    ha="center",
                    va="bottom" if value >= 0.0 else "top",
                    rotation=90,
                    fontsize=7,
                    color=ink,
                )
    ax.axhline(0.0, color=ink, linewidth=1.0)
    ax.set_title(
        "Calendar-year returns: baseline versus a 10% TQQQ sleeve in risk-off\n"
        "One-day additional execution delay; 1996–2026, with 2026 through April 17",
        loc="left",
    )
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Calendar-year return")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{year} YTD" if year == final_year else str(year) for year in years],
        rotation=45,
        ha="right",
    )
    ax.legend(frameon=False, ncol=2, loc="upper left")
    ax.margins(y=0.10)
    fig.tight_layout()
    fig.savefig(
        OUTPUT / "baseline_vs_partial10_delay1_annual_returns.png",
        bbox_inches="tight",
    )
    plt.close(fig)

    bin_width = 0.20
    all_values = complete.to_numpy().ravel()
    lower = np.floor(all_values.min() / bin_width) * bin_width
    upper = np.ceil(all_values.max() / bin_width) * bin_width + bin_width
    bins = np.arange(lower, upper + 1e-12, bin_width)
    baseline_counts, _ = np.histogram(complete["Baseline"], bins=bins)
    sleeve_counts, _ = np.histogram(complete["10% TQQQ sleeve"], bins=bins)
    centers = (bins[:-1] + bins[1:]) / 2.0
    histogram_width = bin_width * 0.38

    baseline_summary = summary.set_index("strategy").loc["Baseline"]
    sleeve_summary = summary.set_index("strategy").loc["10% TQQQ sleeve"]
    fig, ax = plt.subplots(figsize=(13, 7), dpi=170)
    baseline_hist = ax.bar(
        centers - histogram_width / 2.0,
        baseline_counts,
        width=histogram_width,
        color=baseline_color,
        edgecolor=ink,
        linewidth=0.7,
        label=(
            f"Baseline — mean {baseline_summary['mean_annual_return']:.1%}, "
            f"median {baseline_summary['median_annual_return']:.1%}"
        ),
    )
    sleeve_hist = ax.bar(
        centers + histogram_width / 2.0,
        sleeve_counts,
        width=histogram_width,
        color=sleeve_color,
        edgecolor=ink,
        linewidth=0.7,
        hatch="//",
        label=(
            f"10% sleeve — mean {sleeve_summary['mean_annual_return']:.1%}, "
            f"median {sleeve_summary['median_annual_return']:.1%}"
        ),
    )
    for bars in [baseline_hist, sleeve_hist]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 0.10,
                    f"{int(height)}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    color=ink,
                )
    ax.axvline(0.0, color=ink, linewidth=1.0)
    ax.set_title(
        "Distribution of complete calendar-year returns\n"
        "Baseline versus 10% TQQQ sleeve; one-day additional delay; "
        "1996–2025, n=30 years each; common 20pp bins",
        loc="left",
    )
    ax.set_xlabel("Calendar-year return")
    ax.set_ylabel("Number of years")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xticks(centers)
    ax.set_ylim(0.0, max(baseline_counts.max(), sleeve_counts.max()) + 1.5)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(
        OUTPUT / "baseline_vs_partial10_delay1_annual_distribution.png",
        bbox_inches="tight",
    )
    plt.close(fig)
    return annual, summary


def main() -> None:
    frame, _ = load_inputs()
    credit_spread = load_credit_spread(frame.index)
    sma150 = frame["spy"].rolling(150, min_periods=150).mean()
    vol40 = frame["ndx_return"].rolling(40, min_periods=40).std(ddof=1) * np.sqrt(252.0)
    base_trend = hysteresis_trend(frame["spy"], sma150, 0.03)
    base_signal = base_trend & (vol40 < 0.32)

    candidates: list[tuple[str, str, str, dict, pd.Series]] = []
    candidates.append(
        (
            "Baseline",
            "Baseline",
            "baseline",
            dict(RECOMMENDED),
            base_signal.astype(float),
        )
    )

    for entry_tolerance in [0.00, 0.01, 0.02]:
        parameters = {"exit_tolerance": 0.03, "entry_tolerance": entry_tolerance}
        trend = asymmetric_hysteresis(
            frame["spy"], sma150, 0.03, entry_tolerance
        )
        candidate_id = f"asym_entry_{entry_tolerance:.2f}"
        candidates.append(
            (
                "A_asymmetric_reentry",
                "A: Faster re-entry",
                candidate_id,
                parameters,
                (trend & (vol40 < 0.32)).astype(float),
            )
        )

    for confirmation_days in [2, 3, 5]:
        parameters = {"exit_confirmation_days": confirmation_days}
        candidate_id = f"confirm_exit_{confirmation_days}d"
        candidates.append(
            (
                "B_exit_confirmation",
                "B: Confirmed exit",
                candidate_id,
                parameters,
                delayed_exit(base_signal, confirmation_days).astype(float),
            )
        )

    for riskoff_weight in [0.10, 0.20, 0.30]:
        parameters = {"riskoff_tqqq_weight": riskoff_weight}
        candidate_id = f"partial_riskoff_{riskoff_weight:.2f}"
        weight = pd.Series(
            np.where(base_signal, 1.0, riskoff_weight), index=frame.index
        )
        candidates.append(
            (
                "C_partial_riskoff",
                "C: Partial TQQQ off",
                candidate_id,
                parameters,
                weight,
            )
        )

    for short_window in [10, 20, 30, 50]:
        short_sma = frame["ndx"].rolling(short_window, min_periods=short_window).mean()
        for trend_floor in [0.05, 0.08, 0.10]:
            for hard_vol_cap in [0.36, 0.40, 0.44]:
                parameters = {
                    "ndx_short_sma": short_window,
                    "trend_floor": trend_floor,
                    "hard_vol_cap": hard_vol_cap,
                }
                override = (
                    (frame["ndx"] > short_sma)
                    & (frame["spy"] > sma150 * (1.0 - trend_floor))
                    & (vol40 < hard_vol_cap)
                )
                candidate_id = (
                    f"rebound_{short_window}_{trend_floor:.2f}_{hard_vol_cap:.2f}"
                )
                candidates.append(
                    (
                        "D_shallow_rebound",
                        "D: Shallow rebound",
                        candidate_id,
                        parameters,
                        (base_signal | override).astype(float),
                    )
                )

    for baa_threshold in [1.75, 2.00, 2.25]:
        for trend_floor in [0.05, 0.08, 0.10]:
            for hard_vol_cap in [0.36, 0.40, 0.44]:
                parameters = {
                    "baa10y_threshold_pct_points": baa_threshold,
                    "trend_floor": trend_floor,
                    "hard_vol_cap": hard_vol_cap,
                }
                override = (
                    (credit_spread < baa_threshold)
                    & (frame["spy"] > sma150 * (1.0 - trend_floor))
                    & (vol40 < hard_vol_cap)
                )
                candidate_id = (
                    f"credit_{baa_threshold:.2f}_{trend_floor:.2f}_{hard_vol_cap:.2f}"
                )
                candidates.append(
                    (
                        "E_credit_health",
                        "E: Healthy credit",
                        candidate_id,
                        parameters,
                        (base_signal | override).astype(float),
                    )
                )

    rows = []
    paths: dict[tuple[str, int], pd.DataFrame] = {}
    raw_weights: dict[str, pd.Series] = {}
    for method, label, candidate_id, parameters, observed_weight in candidates:
        raw_weights[candidate_id] = observed_weight
        for delay in DELAYS:
            metrics, path = backtest_weights(frame, observed_weight, delay)
            rows.append(
                {
                    "method": method,
                    "method_label": label,
                    "candidate_id": candidate_id,
                    "parameters": parameter_text(parameters),
                    "delay": delay,
                    **metrics,
                }
            )
            paths[(candidate_id, delay)] = path

    results = pd.DataFrame(rows)
    aggregated = aggregate_candidates(results)
    winners = select_method_winners(aggregated)
    baseline = aggregated[aggregated["method"] == "Baseline"]
    selected = pd.concat([baseline, winners], ignore_index=True)

    # Confirm that the generalized binary-weight implementation reproduces the
    # original backtest before comparing the extensions.
    for delay in DELAYS:
        _, original_path = backtest(frame, base_signal, delay)
        generalized = paths[("baseline", delay)]
        max_difference = float(
            (original_path["net_return"] - generalized["net_return"]).abs().max()
        )
        if max_difference > 1e-12:
            raise AssertionError(
                f"Generalized backtest differs from baseline by {max_difference}"
            )

    results.to_csv(OUTPUT / "recent_improvement_candidate_results.csv", index=False)
    aggregated.to_csv(
        OUTPUT / "recent_improvement_candidate_robust_summary.csv", index=False
    )
    selected.to_csv(OUTPUT / "recent_improvement_selected_summary.csv", index=False)

    selected_paths = {
        key: value
        for key, value in paths.items()
        if key[0] in set(selected["candidate_id"])
    }
    long_paths = []
    selected_lookup = selected.set_index("candidate_id")
    for (candidate_id, delay), path in selected_paths.items():
        export = path.copy()
        export.insert(0, "date", export.index)
        export.insert(1, "candidate_id", candidate_id)
        export.insert(2, "method_label", selected_lookup.loc[candidate_id, "method_label"])
        export.insert(3, "delay", delay)
        long_paths.append(export.reset_index(drop=True))
    pd.concat(long_paths, ignore_index=True).to_csv(
        OUTPUT / "recent_improvement_selected_paths.csv", index=False
    )

    save_comparison_plots(selected, selected_paths)
    save_annual_return_comparison(selected_paths)

    display_columns = [
        "method_label",
        "parameters",
        "passes_hard_requirements",
        "min_delay_cagr",
        "min_post_2008_cagr",
        "min_trailing_252_return",
        "min_2026_ytd_return",
        "worst_max_drawdown",
        "worst_dotcom_drawdown",
        "delay_cagr_gap",
    ]
    print(selected[display_columns].to_string(index=False))
    print(f"Candidates evaluated: {len(aggregated):,} ({len(results):,} delay cases)")
    print(f"FRED source: {FRED_BAA10Y_URL}")


if __name__ == "__main__":
    main()
