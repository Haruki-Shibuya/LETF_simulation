from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT = ROOT / "output"
TQQQ_PATH = REPO / "tqqq_backtest" / "output" / "tqqq_extension_1991.csv"
END_DATE = pd.Timestamp("2026-04-17")
START_YEARS = range(1995, 2027)
TRADING_COST = 0.0005


def load_returns() -> pd.DataFrame:
    delay_0 = pd.read_csv(
        OUTPUT / "recommended_delay_0_path.csv", index_col="Date", parse_dates=True
    )["net_return"].rename("strategy_delay_0_return")
    delay_1 = pd.read_csv(
        OUTPUT / "recommended_delay_1_path.csv", index_col="Date", parse_dates=True
    )["net_return"].rename("strategy_delay_1_return")
    canonical = pd.read_csv(TQQQ_PATH, parse_dates=["Date"]).set_index("Date")
    buy_hold = canonical["TQQQ_3X_CALIBRATED_STITCHED_RETURN"].reindex(delay_0.index)
    buy_hold = buy_hold.rename("buy_hold_return")
    # Match the benchmark convention used by validate_parameters.py.
    buy_hold.iloc[0] -= TRADING_COST

    returns = pd.concat([buy_hold, delay_0, delay_1], axis=1).loc[:END_DATE]
    if returns.isna().any().any():
        raise ValueError("Return series do not share a complete common date range")
    return returns


def calculate_start_year_table(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    first_available_year = int(returns.index[0].year)
    for year in START_YEARS:
        if year < first_available_year:
            rows.append(
                {
                    "start_year": year,
                    "available": False,
                    "start_date": pd.NaT,
                    "end_date": returns.index[-1],
                    "trading_days": 0,
                    "calendar_years": np.nan,
                    "note": "N/A: current simulation starts in 1996",
                }
            )
            continue

        period = returns.loc[returns.index >= pd.Timestamp(year=year, month=1, day=1)]
        elapsed_years = (period.index[-1] - period.index[0]).days / 365.2425
        if elapsed_years <= 0:
            raise ValueError(f"Insufficient elapsed time for {year}")

        row: dict[str, object] = {
            "start_year": year,
            "available": True,
            "start_date": period.index[0],
            "end_date": period.index[-1],
            "trading_days": len(period),
            "calendar_years": elapsed_years,
            "note": "Partial-year annualization" if year == 2026 else "",
        }
        for column, label in {
            "buy_hold_return": "buy_hold",
            "strategy_delay_0_return": "strategy_delay_0",
            "strategy_delay_1_return": "strategy_delay_1",
        }.items():
            series = period[column]
            total_return = float((1.0 + series).prod() - 1.0)
            row[f"{label}_total_return"] = total_return
            row[f"{label}_cagr"] = float(
                (1.0 + total_return) ** (1.0 / elapsed_years) - 1.0
            )
            row[f"{label}_volatility"] = float(
                series.std(ddof=1) * np.sqrt(252.0)
            )
        rows.append(row)
    return pd.DataFrame(rows)


def plot_comparison(table: pd.DataFrame) -> None:
    available = table.loc[table["available"]].copy()
    colors = {
        "buy_hold": "#4B5563",
        "strategy_delay_0": "#8BA9C4",
        "strategy_delay_1": "#24557A",
    }
    labels = {
        "buy_hold": "Buy & hold TQQQ",
        "strategy_delay_0": "Strategy, normal execution",
        "strategy_delay_1": "Strategy, +1 trading-day delay",
    }
    styles = {
        "buy_hold": ("--", "s", False),
        "strategy_delay_0": ("-.", "o", False),
        "strategy_delay_1": ("-", "o", True),
    }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.labelsize": 12,
            "axes.edgecolor": "#6B7280",
            "axes.linewidth": 0.8,
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "text.color": "#1F2937",
        }
    )
    fig, axes = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    fig.patch.set_facecolor("#FAFAF9")

    for axis in axes:
        axis.set_facecolor("#FAFAF9")
        axis.grid(axis="y", color="#D1D5DB", linewidth=0.8, alpha=0.75)
        axis.spines[["top", "right"]].set_visible(False)
        axis.axvspan(2025.5, 2026.5, color="#E5E7EB", alpha=0.45, zorder=0)

    for key in ("buy_hold", "strategy_delay_0", "strategy_delay_1"):
        linestyle, marker, filled = styles[key]
        markerfacecolor = colors[key] if filled else "#FAFAF9"
        axes[0].plot(
            available["start_year"],
            available[f"{key}_cagr"],
            label=labels[key],
            color=colors[key],
            linewidth=2.2,
            linestyle=linestyle,
            marker=marker,
            markersize=5,
            markerfacecolor=markerfacecolor,
            markeredgecolor=colors[key],
            markeredgewidth=1.1,
        )
        axes[1].plot(
            available["start_year"],
            available[f"{key}_volatility"],
            color=colors[key],
            linewidth=2.2,
            linestyle=linestyle,
            marker=marker,
            markersize=5,
            markerfacecolor=markerfacecolor,
            markeredgecolor=colors[key],
            markeredgewidth=1.1,
        )

    axes[0].axhline(0.30, color="#9CA3AF", linewidth=1.2, linestyle=":")
    axes[0].text(
        1996.1,
        0.305,
        "30% CAGR threshold",
        color="#6B7280",
        fontsize=10,
        va="bottom",
    )
    axes[0].axhline(0.0, color="#6B7280", linewidth=0.9)
    axes[0].set_title("Pretax CAGR by starting year", loc="left", fontweight="bold")
    axes[0].set_ylabel("Annualized CAGR")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axes[0].legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.18),
        ncol=3,
        frameon=False,
        fontsize=10.5,
    )

    axes[1].set_title("Annualized volatility by starting year", loc="left", fontweight="bold")
    axes[1].set_ylabel("Annualized volatility")
    axes[1].set_xlabel("Starting year x")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axes[1].set_xlim(1994.5, 2026.5)
    axes[1].set_xticks([1995] + list(range(1996, 2027, 2)))
    axes[1].tick_params(axis="x", rotation=45)

    axes[0].annotate(
        "2026: 73 trading days\n(partial-year annualization)",
        xy=(2026, available.loc[available["start_year"] == 2026, "strategy_delay_1_cagr"].iloc[0]),
        xytext=(2021.8, -0.24),
        arrowprops={"arrowstyle": "->", "color": "#6B7280", "linewidth": 1.0},
        fontsize=9.5,
        color="#4B5563",
        ha="left",
    )
    axes[1].text(
        1995,
        axes[1].get_ylim()[0],
        "1995\nN/A",
        color="#6B7280",
        fontsize=9,
        ha="center",
        va="bottom",
    )

    fig.suptitle(
        "TQQQ buy-and-hold versus the 150/40/32/3 regime strategy",
        x=0.07,
        y=0.995,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.956,
        "Each point uses daily returns from the first available trading day of year x through 2026-04-17. "
        "The strategy state is carried forward from the original 1996 simulation; expenses and modeled trading costs are included.",
        fontsize=10.5,
        color="#4B5563",
        ha="left",
    )
    fig.text(
        0.07,
        0.014,
        "1995 is unavailable because the validated strategy path begins on 1996-01-02. "
        "Short recent windows, especially 2026, produce unstable annualized estimates.",
        fontsize=9.5,
        color="#6B7280",
        ha="left",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.88, bottom=0.10, hspace=0.30)
    fig.savefig(
        OUTPUT / "start_year_cagr_volatility_comparison.png",
        dpi=180,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)


def main() -> None:
    returns = load_returns()
    table = calculate_start_year_table(returns)
    table.to_csv(OUTPUT / "start_year_cagr_volatility_comparison.csv", index=False)
    plot_comparison(table)
    print(
        table.loc[
            table["start_year"].isin([1995, 1996, 2000, 2008, 2010, 2020, 2024, 2025, 2026]),
            [
                "start_year",
                "trading_days",
                "buy_hold_cagr",
                "strategy_delay_0_cagr",
                "strategy_delay_1_cagr",
                "buy_hold_volatility",
                "strategy_delay_0_volatility",
                "strategy_delay_1_volatility",
            ],
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
