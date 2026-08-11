from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT = ROOT / "output"
DATA = OUTPUT / "data"
sys.path.insert(0, str(ROOT))

from validate_parameters import (  # noqa: E402
    DELAYS,
    INITIAL_CAPITAL,
    TRADING_COST,
    backtest,
    hysteresis_trend,
    load_inputs,
)


TECL_PRIMARY_PATH = (
    REPO
    / "tecl_sma160_rotation"
    / "output"
    / "_delete_candidates"
    / "tecl_sma160_gspc_above_tecl100_tqqq0_below_soxl0_tecl0_tqqq100_"
    "crossunder_price_drawdown_enterdown_23p0_from_19920101_daily_path.csv"
)
TECL_SECONDARY_PATH = (
    REPO
    / "tecl_sma160_rotation"
    / "output"
    / "_delete_candidates"
    / "tecl_sma160_gspc_above_tecl100_tqqq0_wait_tmf50_gld50_below_soxl0_"
    "tecl0_tqqq100_crossunder_price_drawdown_ref_tecl_enterdown_41p5_"
    "from_20020101_daily_path.csv"
)
TECL_DIAGNOSTICS_PATH = TECL_PRIMARY_PATH.with_name(
    TECL_PRIMARY_PATH.name.replace("_daily_path.csv", "_proxy_diagnostics.csv")
)
TECL_CACHE_PATH = DATA / "tecl_stitched_return_1992_2026.csv"
DOTCOM_SURVIVAL_FLOOR = -0.60
RECENT_DAYS = 252


METHOD_ORDER = [
    "A_profit_target",
    "B_fixed_duration",
    "C_confirmed_profit_target",
    "D_long_riskoff_profit_target",
    "E_relative_strength",
]
METHOD_LABELS = {
    "Baseline": "Baseline TQQQ",
    "All_TECL": "TECL throughout risk-on",
    "A_profit_target": "A: Profit target",
    "B_fixed_duration": "B: Fixed duration",
    "C_confirmed_profit_target": "C: Confirm then target",
    "D_long_riskoff_profit_target": "D: Long-off target",
    "E_relative_strength": "E: Relative strength",
}


def load_tecl_return() -> tuple[pd.Series, pd.DataFrame]:
    """Extract and reconcile the existing stitched TECL total-return series."""
    primary = pd.read_csv(
        TECL_PRIMARY_PATH,
        usecols=["Date", "tecl_buy_hold_return"],
        parse_dates=["Date"],
    ).set_index("Date")["tecl_buy_hold_return"]
    secondary = pd.read_csv(
        TECL_SECONDARY_PATH,
        usecols=["Date", "tecl_buy_hold_return"],
        parse_dates=["Date"],
    ).set_index("Date")["tecl_buy_hold_return"]
    overlap = pd.concat(
        [primary.rename("primary"), secondary.rename("secondary")], axis=1
    ).dropna()
    maximum_difference = float((overlap["primary"] - overlap["secondary"]).abs().max())
    # Independent saved runs recalibrated the synthetic financing multiplier
    # separately. Accept only sub-0.1bp daily differences and preserve the
    # observed discrepancy in the exported quality report.
    if maximum_difference > 1e-5:
        raise AssertionError(
            f"Saved TECL sources disagree by as much as {maximum_difference}"
        )
    if primary.index.has_duplicates or not primary.index.is_monotonic_increasing:
        raise AssertionError("TECL source dates must be unique and ordered")
    if primary.isna().any() or (primary <= -1.0).any():
        raise AssertionError("TECL return series contains invalid values")

    cache = primary.rename("tecl_stitched_return").to_frame()
    cache.index.name = "Date"
    cache.to_csv(TECL_CACHE_PATH)

    diagnostics = pd.read_csv(TECL_DIAGNOSTICS_PATH)
    tecl_row = diagnostics[diagnostics["proxy"] == "TECL"].copy()
    if tecl_row.empty:
        raise AssertionError("TECL proxy diagnostics are missing")
    quality = pd.DataFrame(
        [
            {
                "series": "TECL stitched return",
                "rows": int(primary.shape[0]),
                "start": primary.index.min(),
                "end": primary.index.max(),
                "nulls": int(primary.isna().sum()),
                "duplicate_dates": int(primary.index.duplicated().sum()),
                "cross_source_overlap_rows": int(overlap.shape[0]),
                "cross_source_max_abs_difference": maximum_difference,
                "actual_overlap_start": tecl_row.iloc[0]["overlap_start"],
                "actual_overlap_end": tecl_row.iloc[0]["overlap_end"],
                "model_actual_daily_corr": float(tecl_row.iloc[0]["daily_return_corr"]),
                "model_actual_mae_bps": float(tecl_row.iloc[0]["daily_return_mae_bps"]),
                "legacy_proxy": tecl_row.iloc[0]["legacy_proxy"],
                "modern_proxy": tecl_row.iloc[0]["modern_proxy"],
                "legacy_beta": float(tecl_row.iloc[0]["legacy_beta"]),
                "financing_multiplier": float(tecl_row.iloc[0]["financing_multiplier"]),
                "annual_fee": float(tecl_row.iloc[0]["annual_fee"]),
            }
        ]
    )
    return primary, quality


def annualized_cagr(returns: pd.Series) -> float:
    growth = float((1.0 + returns).prod())
    years = (returns.index[-1] - returns.index[0]).days / 365.2425
    return growth ** (1.0 / years) - 1.0


def continued_subperiod_cagr(returns: pd.Series, anchor: pd.Timestamp) -> float:
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


def build_asset_diagnostics(
    frame: pd.DataFrame, base_signal: pd.Series
) -> pd.DataFrame:
    rows = []
    periods = {
        "full_1996_2026": pd.Timestamp("1996-01-02"),
        "actual_overlap_2010_2026": pd.Timestamp("2010-02-11"),
    }
    spy_return = frame["spy"].pct_change(fill_method=None)
    for period, start in periods.items():
        subset = frame.loc[frame.index >= start].copy()
        subset_spy = spy_return.reindex(subset.index)
        valid = subset_spy.notna()
        subset = subset.loc[valid]
        subset_spy = subset_spy.loc[valid]
        tqqq_up = subset["tqqq_return"] > 0.0
        risk_on = base_signal.reindex(subset.index).fillna(False)
        for label, column in [
            ("TECL", "tecl_return"),
            ("TQQQ", "tqqq_return"),
        ]:
            returns = subset[column]
            rows.append(
                {
                    "period": period,
                    "asset": label,
                    "start": subset.index[0],
                    "end": subset.index[-1],
                    "trading_days": int(subset.shape[0]),
                    "cagr": annualized_cagr(returns),
                    "annualized_volatility": float(
                        returns.std(ddof=1) * np.sqrt(252.0)
                    ),
                    "beta_to_spy": float(
                        np.cov(returns, subset_spy, ddof=1)[0, 1]
                        / np.var(subset_spy, ddof=1)
                    ),
                    "correlation_to_spy": float(returns.corr(subset_spy)),
                    "mean_return_on_tqqq_up_days": float(returns.loc[tqqq_up].mean()),
                    "mean_return_on_tqqq_down_days": float(
                        returns.loc[~tqqq_up].mean()
                    ),
                    "mean_return_during_base_risk_on": float(
                        returns.loc[risk_on].mean()
                    ),
                }
            )
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(OUTPUT / "tecl_tqqq_asset_diagnostics.csv", index=False)
    return diagnostics


def baseline_codes(base_signal: pd.Series, risk_on_asset: str) -> pd.Series:
    return pd.Series(
        np.where(base_signal, risk_on_asset, "DEF"),
        index=base_signal.index,
        dtype="object",
    )


def profit_target_codes(
    base_signal: pd.Series,
    tecl_level: pd.Series,
    profit_target: float,
) -> pd.Series:
    output = []
    previous_on = False
    sprinting = False
    reference = np.nan
    for date, is_on in base_signal.items():
        if not is_on:
            output.append("DEF")
            sprinting = False
            reference = np.nan
        elif not previous_on:
            sprinting = True
            reference = float(tecl_level.loc[date])
            output.append("TECL")
        elif sprinting and float(tecl_level.loc[date]) / reference - 1.0 >= profit_target:
            sprinting = False
            output.append("TQQQ")
        else:
            output.append("TECL" if sprinting else "TQQQ")
        previous_on = bool(is_on)
    return pd.Series(output, index=base_signal.index, dtype="object")


def fixed_duration_codes(base_signal: pd.Series, holding_days: int) -> pd.Series:
    output = []
    on_days = 0
    for is_on in base_signal:
        if not is_on:
            on_days = 0
            output.append("DEF")
        else:
            on_days += 1
            output.append("TECL" if on_days <= holding_days else "TQQQ")
    return pd.Series(output, index=base_signal.index, dtype="object")


def confirmed_profit_target_codes(
    base_signal: pd.Series,
    tecl_level: pd.Series,
    confirmation_days: int,
    profit_target: float,
) -> pd.Series:
    output = []
    on_days = 0
    sprinting = False
    reference = np.nan
    for date, is_on in base_signal.items():
        if not is_on:
            on_days = 0
            sprinting = False
            reference = np.nan
            output.append("DEF")
            continue
        on_days += 1
        if on_days < confirmation_days:
            output.append("TQQQ")
            continue
        if on_days == confirmation_days:
            sprinting = True
            reference = float(tecl_level.loc[date])
            output.append("TECL")
            continue
        if sprinting and float(tecl_level.loc[date]) / reference - 1.0 >= profit_target:
            sprinting = False
        output.append("TECL" if sprinting else "TQQQ")
    return pd.Series(output, index=base_signal.index, dtype="object")


def long_riskoff_profit_target_codes(
    base_signal: pd.Series,
    tecl_level: pd.Series,
    minimum_off_days: int,
    profit_target: float,
) -> pd.Series:
    output = []
    off_days = 0
    previous_on = False
    sprinting = False
    reference = np.nan
    for date, is_on in base_signal.items():
        if not is_on:
            off_days += 1
            sprinting = False
            reference = np.nan
            output.append("DEF")
        elif not previous_on:
            sprinting = off_days >= minimum_off_days
            reference = float(tecl_level.loc[date]) if sprinting else np.nan
            off_days = 0
            output.append("TECL" if sprinting else "TQQQ")
        elif sprinting and float(tecl_level.loc[date]) / reference - 1.0 >= profit_target:
            sprinting = False
            output.append("TQQQ")
        else:
            output.append("TECL" if sprinting else "TQQQ")
        previous_on = bool(is_on)
    return pd.Series(output, index=base_signal.index, dtype="object")


def relative_strength_codes(
    frame: pd.DataFrame,
    base_signal: pd.Series,
    lookback: int,
    threshold: float,
) -> pd.Series:
    relative_log_return = (
        np.log1p(frame["tecl_return"]).rolling(lookback, min_periods=lookback).sum()
        - np.log1p(frame["tqqq_return"])
        .rolling(lookback, min_periods=lookback)
        .sum()
    )
    relative_return = np.expm1(relative_log_return)
    return pd.Series(
        np.where(
            ~base_signal,
            "DEF",
            np.where(relative_return > threshold, "TECL", "TQQQ"),
        ),
        index=frame.index,
        dtype="object",
    )


def backtest_codes(
    frame: pd.DataFrame,
    observed_codes: pd.Series,
    delay: int,
) -> tuple[dict[str, float], pd.DataFrame]:
    codes = observed_codes.shift(delay + 1, fill_value="DEF")
    gross = pd.Series(
        np.select(
            [codes.eq("TECL"), codes.eq("TQQQ")],
            [frame["tecl_return"], frame["tqqq_return"]],
            default=frame["defensive_return"],
        ),
        index=frame.index,
        dtype=float,
    )
    allocation_turnover = codes.ne(codes.shift()).astype(float)
    allocation_turnover.iloc[0] = 1.0
    internal_turnover = frame["defensive_rebalance_turnover"].where(
        codes.eq("DEF"), 0.0
    )
    costs = TRADING_COST * (allocation_turnover + internal_turnover)
    net = gross - costs
    recent = net.iloc[-RECENT_DAYS:]
    ytd_2026 = net.loc[net.index >= pd.Timestamp("2026-01-01")]
    dotcom = net.loc["2000-01-01":"2003-12-31"]
    metrics = {
        "cagr": annualized_cagr(net),
        "post_2008_cagr": continued_subperiod_cagr(
            net, pd.Timestamp("2007-12-31")
        ),
        "post_2010_cagr": continued_subperiod_cagr(
            net, pd.Timestamp("2010-02-10")
        ),
        "volatility": float(net.std(ddof=1) * np.sqrt(252.0)),
        "max_drawdown": drawdown_min(net),
        "dotcom_max_drawdown": drawdown_min(dotcom),
        "trailing_252_return": float((1.0 + recent).prod() - 1.0),
        "return_2026_ytd": float((1.0 + ytd_2026).prod() - 1.0),
        "ending_value_1000": float(INITIAL_CAPITAL * (1.0 + net).prod()),
        "tecl_share": float(codes.eq("TECL").mean()),
        "tqqq_share": float(codes.eq("TQQQ").mean()),
        "defensive_share": float(codes.eq("DEF").mean()),
        "asset_switches": int(codes.ne(codes.shift()).sum()),
        "tecl_entries": int((codes.eq("TECL") & ~codes.shift().eq("TECL")).sum()),
        "total_turnover": float((allocation_turnover + internal_turnover).sum()),
    }
    path = pd.DataFrame(
        {
            "asset": codes,
            "gross_return": gross,
            "trading_cost": costs,
            "net_return": net,
            "nav_1000": INITIAL_CAPITAL * (1.0 + net).cumprod(),
        }
    )
    return metrics, path


def aggregate_results(results: pd.DataFrame) -> pd.DataFrame:
    aggregated = (
        results.groupby(
            ["method", "method_label", "candidate_id", "parameters"], as_index=False
        )
        .agg(
            min_delay_cagr=("cagr", "min"),
            mean_delay_cagr=("cagr", "mean"),
            min_post_2008_cagr=("post_2008_cagr", "min"),
            min_post_2010_cagr=("post_2010_cagr", "min"),
            min_trailing_252_return=("trailing_252_return", "min"),
            min_2026_ytd_return=("return_2026_ytd", "min"),
            worst_volatility=("volatility", "max"),
            worst_max_drawdown=("max_drawdown", "min"),
            worst_dotcom_drawdown=("dotcom_max_drawdown", "min"),
            min_tecl_share=("tecl_share", "min"),
            max_tecl_share=("tecl_share", "max"),
            max_asset_switches=("asset_switches", "max"),
            max_total_turnover=("total_turnover", "max"),
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


def select_winners(aggregated: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHOD_ORDER:
        group = aggregated[aggregated["method"] == method]
        feasible = group[group["passes_hard_requirements"]]
        pool = feasible if not feasible.empty else group
        rows.append(
            pool.sort_values(
                ["min_delay_cagr", "min_post_2010_cagr", "worst_max_drawdown"],
                ascending=False,
            ).iloc[0]
        )
    return pd.DataFrame(rows).reset_index(drop=True)


def save_metric_plot(selected: pd.DataFrame) -> None:
    ordered = selected.reset_index(drop=True)
    labels = ordered["method_label"].tolist()
    colors = ["#444444", "#4C78A8", "#E0A458", "#D98C4B", "#7A9E52", "#B279A2"]
    hatches = ["", "//", "\\\\", "..", "xx", "++"]
    panels = [
        ("min_delay_cagr", "Full-period CAGR", 0.30),
        ("min_post_2010_cagr", "CAGR from actual overlap (2010)", 0.30),
        ("worst_max_drawdown", "Maximum drawdown", None),
        ("worst_dotcom_drawdown", "Dot-com maximum drawdown", DOTCOM_SURVIVAL_FLOOR),
    ]
    plt.style.use("seaborn-v0_8-whitegrid")
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
            offset = 0.008 if value >= 0.0 else -0.008
            ax.text(
                value + offset,
                bar.get_y() + bar.get_height() / 2.0,
                f"{value:.1%}",
                va="center",
                ha="left" if value >= 0.0 else "right",
                fontsize=9,
                color="#222222",
            )
        ax.axvline(0.0, color="#222222", linewidth=0.9)
        if threshold is not None:
            ax.axvline(threshold, color="#222222", linestyle="--", linewidth=1.1)
        ax.set_title(title, loc="left")
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        ax.set_yticks(np.arange(len(labels)), labels)
        ax.invert_yaxis()
        minimum = min(values.min(), threshold if threshold is not None else 0.0, 0.0)
        maximum = max(values.max(), threshold if threshold is not None else 0.0, 0.0)
        padding = max(0.05, (maximum - minimum) * 0.18)
        ax.set_xlim(minimum - padding, maximum + padding)
    fig.suptitle(
        "Five TECL-to-TQQQ rotation methods versus the TQQQ baseline\n"
        "Each bar is the worse result across normal and one-day-additional delays",
        x=0.05,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUTPUT / "tecl_rotation_metric_comparison.png", bbox_inches="tight")
    plt.close(fig)


def save_full_path_plot(
    selected: pd.DataFrame,
    paths: dict[tuple[str, int], pd.DataFrame],
) -> None:
    colors = ["#444444", "#4C78A8", "#E0A458", "#D98C4B", "#7A9E52", "#B279A2"]
    line_styles = ["-", "--", "-.", ":", (0, (5, 2)), (0, (1, 1))]
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(14, 7), dpi=170)
    for position, row in enumerate(selected.itertuples(index=False)):
        path = paths[(row.candidate_id, 1)]
        ax.plot(
            path.index,
            path["nav_1000"],
            label=row.method_label,
            color=colors[position],
            linestyle=line_styles[position],
            linewidth=1.45,
        )
    ax.set_yscale("log")
    ax.set_title(
        "Selected TECL-to-TQQQ methods: full portfolio paths\n"
        "One-day additional delay; $1,000 initial value; 1996–2026",
        loc="left",
    )
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUTPUT / "tecl_rotation_full_paths.png", bbox_inches="tight")
    plt.close(fig)


def save_tradeoff_plot(aggregated: pd.DataFrame) -> None:
    method_colors = {
        "A_profit_target": "#4C78A8",
        "B_fixed_duration": "#E0A458",
        "C_confirmed_profit_target": "#D98C4B",
        "D_long_riskoff_profit_target": "#7A9E52",
        "E_relative_strength": "#B279A2",
    }
    markers = {
        "A_profit_target": "o",
        "B_fixed_duration": "s",
        "C_confirmed_profit_target": "^",
        "D_long_riskoff_profit_target": "D",
        "E_relative_strength": "P",
    }
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=170)
    for method in METHOD_ORDER:
        group = aggregated[aggregated["method"] == method]
        ax.scatter(
            group["worst_max_drawdown"],
            group["min_delay_cagr"],
            s=40 + 300 * group["max_tecl_share"],
            c=method_colors[method],
            marker=markers[method],
            edgecolors="#333333",
            linewidths=0.5,
            alpha=0.75,
            label=METHOD_LABELS[method],
        )
    baseline = aggregated[aggregated["method"] == "Baseline"].iloc[0]
    ax.scatter(
        baseline["worst_max_drawdown"],
        baseline["min_delay_cagr"],
        s=180,
        c="#222222",
        marker="*",
        label="Baseline TQQQ",
        zorder=5,
    )
    ax.axhline(0.30, color="#222222", linestyle="--", linewidth=1.0)
    ax.set_title(
        "Candidate trade-off: worst-delay CAGR versus maximum drawdown\n"
        "Marker size represents TECL allocation share; 46 method candidates",
        loc="left",
    )
    ax.set_xlabel("Worst maximum drawdown across delays")
    ax.set_ylabel("Worst CAGR across delays")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(OUTPUT / "tecl_rotation_candidate_tradeoff.png", bbox_inches="tight")
    plt.close(fig)


def save_balanced_recommendation_plot(
    baseline_paths: dict[int, pd.DataFrame],
    recommendation_paths: dict[int, pd.DataFrame],
) -> None:
    """Show the recommended confirmation-plus-target rule against the baseline."""
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), dpi=170)

    for label, path, color, linestyle in [
        ("Baseline: TQQQ", baseline_paths[1], "#333333", "-"),
        (
            "Recommended: confirm 5 days, TECL to +20%, then TQQQ",
            recommendation_paths[1],
            "#D98C4B",
            "--",
        ),
    ]:
        axes[0].plot(
            path.index,
            path["nav_1000"],
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=1.5,
        )
    axes[0].set_yscale("log")
    axes[0].set_title("Full period: one-day additional delay", loc="left")
    axes[0].set_ylabel("Portfolio value from $1,000 (log scale)")
    axes[0].set_xlabel("Date")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")

    recent_start = pd.Timestamp("2008-01-02")
    for label, path, color, linestyle in [
        ("Baseline: TQQQ", baseline_paths[1], "#333333", "-"),
        (
            "Recommended: confirm 5 days, TECL to +20%, then TQQQ",
            recommendation_paths[1],
            "#D98C4B",
            "--",
        ),
    ]:
        recent = path.loc[recent_start:, "nav_1000"]
        normalized = 1000.0 * recent / recent.iloc[0]
        axes[1].plot(
            normalized.index,
            normalized,
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=1.5,
        )
    axes[1].set_yscale("log")
    axes[1].set_title("Since 2008: rebased to $1,000", loc="left")
    axes[1].set_ylabel("Portfolio value (log scale)")
    axes[1].set_xlabel("Date")
    axes[1].legend(frameon=False, fontsize=8.5, loc="upper left")

    fig.suptitle(
        "Balanced TECL-to-TQQQ recommendation versus the current baseline",
        x=0.055,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(
        OUTPUT / "tecl_rotation_balanced_vs_baseline.png", bbox_inches="tight"
    )
    plt.close(fig)


def save_allocation_heatmaps(
    selected: pd.DataFrame,
    paths: dict[tuple[str, int], pd.DataFrame],
) -> None:
    windows = [
        (pd.Timestamp("1999-01-01"), pd.Timestamp("2003-12-31"), "Dot-com window"),
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-04-17"), "Recent window"),
    ]
    mapping = {"DEF": 0, "TQQQ": 1, "TECL": 2}
    cmap = ListedColormap(["#F3E2CF", "#777777", "#4C78A8"])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)
    labels = selected["method_label"].tolist()
    fig, axes = plt.subplots(2, 1, figsize=(15, 8.5), dpi=170)
    for ax, (start, end, title) in zip(axes, windows):
        first_path = paths[(selected.iloc[0]["candidate_id"], 1)].loc[start:end]
        dates = first_path.index
        rows = []
        for row in selected.itertuples(index=False):
            asset = paths[(row.candidate_id, 1)].loc[start:end, "asset"]
            rows.append(asset.map(mapping).to_numpy())
        matrix = np.vstack(rows)
        ax.imshow(
            matrix,
            aspect="auto",
            interpolation="nearest",
            cmap=cmap,
            norm=norm,
        )
        tick_dates = pd.date_range(dates[0], dates[-1], freq="6MS")
        tick_positions = [int(dates.searchsorted(date)) for date in tick_dates]
        valid = [
            (position, date)
            for position, date in zip(tick_positions, tick_dates)
            if position < len(dates)
        ]
        ax.set_xticks([position for position, _ in valid])
        ax.set_xticklabels(
            [date.strftime("%Y-%m") for _, date in valid], rotation=45, ha="right"
        )
        ax.set_yticks(np.arange(len(labels)), labels)
        ax.set_title(title, loc="left")
    axes[0].legend(
        handles=[
            Patch(facecolor="#F3E2CF", label="Defensive"),
            Patch(facecolor="#777777", label="TQQQ"),
            Patch(facecolor="#4C78A8", label="TECL"),
        ],
        frameon=False,
        ncol=3,
        loc="upper left",
        bbox_to_anchor=(0, 1.28),
    )
    fig.suptitle(
        "Realized daily asset selection with one-day additional delay",
        x=0.08,
        ha="left",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUTPUT / "tecl_rotation_allocation_heatmaps.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    frame, _ = load_inputs()
    tecl_return, tecl_quality = load_tecl_return()
    frame = frame.join(tecl_return.rename("tecl_return"), how="left")
    if frame["tecl_return"].isna().any():
        missing = int(frame["tecl_return"].isna().sum())
        raise AssertionError(f"TECL join left {missing} missing analysis rows")
    if not frame.index.is_unique or frame.index.has_duplicates:
        raise AssertionError("Analysis frame dates must be unique")

    sma150 = frame["spy"].rolling(150, min_periods=150).mean()
    trend = hysteresis_trend(frame["spy"], sma150, 0.03)
    vol40 = (
        frame["ndx_return"].rolling(40, min_periods=40).std(ddof=1)
        * np.sqrt(252.0)
    )
    base_signal = trend & (vol40 < 0.32)
    tecl_level = (1.0 + frame["tecl_return"]).cumprod()

    asset_diagnostics = build_asset_diagnostics(frame, base_signal)
    tecl_quality.to_csv(OUTPUT / "tecl_rotation_data_quality.csv", index=False)

    candidates: list[tuple[str, str, str, dict, pd.Series]] = [
        (
            "Baseline",
            METHOD_LABELS["Baseline"],
            "baseline_tqqq",
            {"risk_on_asset": "TQQQ"},
            baseline_codes(base_signal, "TQQQ"),
        ),
        (
            "All_TECL",
            METHOD_LABELS["All_TECL"],
            "all_tecl",
            {"risk_on_asset": "TECL"},
            baseline_codes(base_signal, "TECL"),
        ),
    ]

    for profit_target in [0.10, 0.15, 0.20, 0.25, 0.30]:
        parameters = {
            "profit_target_from_breakout_close": profit_target,
        }
        candidates.append(
            (
                "A_profit_target",
                METHOD_LABELS["A_profit_target"],
                f"profit_target_{profit_target:.2f}",
                parameters,
                profit_target_codes(base_signal, tecl_level, profit_target),
            )
        )

    for holding_days in [10, 20, 40, 60, 80]:
        parameters = {"tecl_holding_days_after_risk_on": holding_days}
        candidates.append(
            (
                "B_fixed_duration",
                METHOD_LABELS["B_fixed_duration"],
                f"fixed_duration_{holding_days}",
                parameters,
                fixed_duration_codes(base_signal, holding_days),
            )
        )

    for confirmation_days in [2, 3, 5, 10]:
        for profit_target in [0.10, 0.20, 0.30]:
            parameters = {
                "confirmation_days": confirmation_days,
                "profit_target_from_confirmation_close": profit_target,
            }
            candidates.append(
                (
                    "C_confirmed_profit_target",
                    METHOD_LABELS["C_confirmed_profit_target"],
                    f"confirm_{confirmation_days}_target_{profit_target:.2f}",
                    parameters,
                    confirmed_profit_target_codes(
                        base_signal,
                        tecl_level,
                        confirmation_days,
                        profit_target,
                    ),
                )
            )

    for minimum_off_days in [5, 10, 20, 40]:
        for profit_target in [0.10, 0.20, 0.30]:
            parameters = {
                "minimum_preceding_riskoff_days": minimum_off_days,
                "profit_target_from_breakout_close": profit_target,
            }
            candidates.append(
                (
                    "D_long_riskoff_profit_target",
                    METHOD_LABELS["D_long_riskoff_profit_target"],
                    f"off_{minimum_off_days}_target_{profit_target:.2f}",
                    parameters,
                    long_riskoff_profit_target_codes(
                        base_signal,
                        tecl_level,
                        minimum_off_days,
                        profit_target,
                    ),
                )
            )

    for lookback in [10, 20, 40, 60]:
        for threshold in [0.00, 0.02, 0.05]:
            parameters = {
                "tecl_minus_tqqq_lookback_days": lookback,
                "relative_return_threshold": threshold,
            }
            candidates.append(
                (
                    "E_relative_strength",
                    METHOD_LABELS["E_relative_strength"],
                    f"relative_{lookback}_{threshold:.2f}",
                    parameters,
                    relative_strength_codes(
                        frame, base_signal, lookback, threshold
                    ),
                )
            )

    rows = []
    paths: dict[tuple[str, int], pd.DataFrame] = {}
    for method, label, candidate_id, parameters, codes in candidates:
        for delay in DELAYS:
            metrics, path = backtest_codes(frame, codes, delay)
            rows.append(
                {
                    "method": method,
                    "method_label": label,
                    "candidate_id": candidate_id,
                    "parameters": json.dumps(
                        parameters, sort_keys=True, ensure_ascii=False
                    ),
                    "delay": delay,
                    **metrics,
                }
            )
            paths[(candidate_id, delay)] = path

    results = pd.DataFrame(rows)
    aggregated = aggregate_results(results)
    winners = select_winners(aggregated)
    baseline = aggregated[aggregated["method"] == "Baseline"]
    selected = pd.concat([baseline, winners], ignore_index=True)
    balanced_candidate_id = "confirm_5_target_0.20"
    balanced_aggregate = aggregated[
        aggregated["candidate_id"] == balanced_candidate_id
    ].copy()
    balanced_results = results[
        results["candidate_id"] == balanced_candidate_id
    ].copy()
    if len(balanced_aggregate) != 1 or set(balanced_results["delay"]) != set(DELAYS):
        raise AssertionError("Balanced recommendation is missing from candidate results")

    # Generalized baseline must reproduce the existing binary TQQQ/defensive model.
    for delay in DELAYS:
        _, original = backtest(frame, base_signal, delay)
        generalized = paths[("baseline_tqqq", delay)]
        difference = float(
            (original["net_return"] - generalized["net_return"]).abs().max()
        )
        if difference > 1e-12:
            raise AssertionError(
                f"Generalized baseline differs from original by {difference}"
            )

    results.to_csv(OUTPUT / "tecl_rotation_candidate_results.csv", index=False)
    aggregated.to_csv(OUTPUT / "tecl_rotation_candidate_robust_summary.csv", index=False)
    selected.to_csv(OUTPUT / "tecl_rotation_selected_summary.csv", index=False)
    balanced_aggregate.to_csv(
        OUTPUT / "tecl_rotation_balanced_recommendation_summary.csv", index=False
    )
    balanced_results.to_csv(
        OUTPUT / "tecl_rotation_balanced_recommendation_delay_results.csv",
        index=False,
    )

    selected_ids = set(selected["candidate_id"])
    selected_paths = {
        key: value for key, value in paths.items() if key[0] in selected_ids
    }
    lookup = selected.set_index("candidate_id")
    exports = []
    for (candidate_id, delay), path in selected_paths.items():
        export = path.copy()
        export.insert(0, "date", export.index)
        export.insert(1, "candidate_id", candidate_id)
        export.insert(2, "method_label", lookup.loc[candidate_id, "method_label"])
        export.insert(3, "delay", delay)
        exports.append(export.reset_index(drop=True))
    pd.concat(exports, ignore_index=True).to_csv(
        OUTPUT / "tecl_rotation_selected_paths.csv", index=False
    )

    balanced_path_exports = []
    for delay in DELAYS:
        export = paths[(balanced_candidate_id, delay)].copy()
        export.insert(0, "date", export.index)
        export.insert(1, "candidate_id", balanced_candidate_id)
        export.insert(2, "delay", delay)
        balanced_path_exports.append(export.reset_index(drop=True))
    pd.concat(balanced_path_exports, ignore_index=True).to_csv(
        OUTPUT / "tecl_rotation_balanced_recommendation_paths.csv", index=False
    )

    save_metric_plot(selected)
    save_full_path_plot(selected, selected_paths)
    save_tradeoff_plot(aggregated)
    save_allocation_heatmaps(selected, selected_paths)
    save_balanced_recommendation_plot(
        {delay: paths[("baseline_tqqq", delay)] for delay in DELAYS},
        {delay: paths[(balanced_candidate_id, delay)] for delay in DELAYS},
    )

    display_columns = [
        "method_label",
        "parameters",
        "passes_hard_requirements",
        "min_delay_cagr",
        "min_post_2008_cagr",
        "min_post_2010_cagr",
        "worst_volatility",
        "worst_max_drawdown",
        "worst_dotcom_drawdown",
        "max_tecl_share",
        "delay_cagr_gap",
    ]
    print(selected[display_columns].to_string(index=False))
    print("\nBalanced recommendation:")
    print(balanced_aggregate[display_columns].to_string(index=False))
    print(f"Candidates: {len(aggregated):,}; delay cases: {len(results):,}")
    print(asset_diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
