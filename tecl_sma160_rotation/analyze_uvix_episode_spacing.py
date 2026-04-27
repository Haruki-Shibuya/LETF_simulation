from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DAILY_PATH = (
    OUTPUT_DIR
    / "canonical_prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212_daily_path.csv"
)


def extract_episodes(path: pd.DataFrame) -> pd.DataFrame:
    rows = []
    active = False
    start_idx = None
    start_date = None
    previous_exit_idx = None
    previous_exit_date = None

    for idx, (date, row) in enumerate(path.iterrows()):
        is_uvix = row["selected_leg"] == "UVIX"
        if is_uvix and not active:
            active = True
            start_idx = idx
            start_date = date
        next_is_uvix = idx + 1 < len(path) and path.iloc[idx + 1]["selected_leg"] == "UVIX"
        if active and is_uvix and not next_is_uvix:
            end_idx = idx
            end_date = date
            segment = path.iloc[start_idx : end_idx + 1]
            episode_return = float((1.0 + segment["strategy_return"].clip(lower=-0.999999)).prod() - 1.0)
            holding_days = int(len(segment))
            days_since_previous_exit = None if previous_exit_idx is None else int(start_idx - previous_exit_idx)
            calendar_days_since_previous_exit = (
                None if previous_exit_date is None else int((start_date - previous_exit_date).days)
            )
            rows.append(
                {
                    "episode_id": len(rows) + 1,
                    "entry_date": start_date.date().isoformat(),
                    "exit_date": end_date.date().isoformat(),
                    "entry_index": int(start_idx),
                    "exit_index": int(end_idx),
                    "holding_days": holding_days,
                    "days_since_previous_exit": days_since_previous_exit,
                    "calendar_days_since_previous_exit": calendar_days_since_previous_exit,
                    "episode_return": episode_return,
                    "episode_return_pct": episode_return * 100.0,
                    "entry_rsi": float(segment["gspc_open_implied_rsi14"].iloc[0]),
                    "exit_rsi": float(segment["gspc_open_implied_rsi14"].iloc[-1]),
                    "entry_tqqq_open": float(segment["TQQQ_OPEN"].iloc[0]),
                    "exit_tqqq_open": float(segment["TQQQ_OPEN"].iloc[-1]),
                    "tqqq_open_return_during_episode": float(segment["TQQQ_OPEN"].iloc[-1] / segment["TQQQ_OPEN"].iloc[0] - 1.0),
                }
            )
            previous_exit_idx = end_idx
            previous_exit_date = end_date
            active = False
            start_idx = None
            start_date = None

    return pd.DataFrame(rows)


def save_plot(episodes: pd.DataFrame, output_path: Path) -> None:
    data = episodes.dropna(subset=["days_since_previous_exit", "episode_return_pct"]).copy()
    x = data["days_since_previous_exit"].astype(float)
    y = data["episode_return_pct"].astype(float)
    corr = x.corr(y)
    win_rate = float((episodes["episode_return"] > 0).mean())

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    colors = np.where(y >= 0, "#2ca25f", "#de2d26")
    ax.scatter(x, y, c=colors, alpha=0.82, s=58, edgecolor="white", linewidth=0.7)

    if len(data) >= 2:
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 100)
        ax.plot(xs, slope * xs + intercept, color="#225ea8", linewidth=2, label="linear fit")
        ax.legend(loc="best")

    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_title(
        "UVIX Episode Return vs Days Since Previous UVIX Exit\n"
        f"episodes={len(episodes)}, win rate={win_rate:.1%}, corr={corr:.3f}"
    )
    ax.set_xlabel("Trading days since previous UVIX episode exit")
    ax.set_ylabel("UVIX episode return (%)")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_distribution_plot(episodes: pd.DataFrame, output_path: Path) -> None:
    returns_pct = episodes["episode_return_pct"].dropna().to_numpy(dtype=float)
    mean_value = float(np.mean(returns_pct))
    median_value = float(np.median(returns_pct))
    win_rate = float(np.mean(returns_pct > 0))
    p05, p25, p75, p95 = np.percentile(returns_pct, [5, 25, 75, 95])

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    counts, bins, patches = ax.hist(
        returns_pct,
        bins=30,
        color="#9ecae1",
        edgecolor="#ffffff",
        alpha=0.88,
        label="episode count",
    )
    ax.axvline(0, color="#333333", linewidth=1.2, label="0%")
    ax.axvline(mean_value, color="#de2d26", linewidth=2, linestyle="--", label=f"mean {mean_value:.2f}%")
    ax.axvline(median_value, color="#2ca25f", linewidth=2, linestyle="--", label=f"median {median_value:.2f}%")
    ax.axvspan(p25, p75, color="#74c476", alpha=0.12, label=f"IQR {p25:.2f}% .. {p75:.2f}%")
    for count, left, right in zip(counts, bins[:-1], bins[1:]):
        if count > 0:
            ax.text((left + right) / 2, count + 0.25, f"{int(count)}", ha="center", va="bottom", fontsize=8)
    x_left = np.floor(returns_pct.min() / 5.0) * 5.0
    x_right = np.ceil(returns_pct.max() / 5.0) * 5.0
    xticks = np.arange(x_left, x_right + 0.1, 5.0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{tick:.0f}%" for tick in xticks], rotation=45, ha="right")
    ax.set_xlim(x_left, x_right)
    ax.grid(axis="x", which="major", alpha=0.28)
    ax.set_title(
        "Histogram of UVIX Episode Returns\n"
        f"episodes={len(returns_pct)}, win rate={win_rate:.1%}, p05={p05:.2f}%, p95={p95:.2f}%"
    )
    ax.set_xlabel("UVIX episode return (%)")
    ax.set_ylabel("Episode count")
    ax.legend(loc="best")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    path = pd.read_csv(DAILY_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    episodes = extract_episodes(path)
    episodes.to_csv(OUTPUT_DIR / "uvix_episode_spacing_analysis.csv", index=False)
    save_plot(episodes, OUTPUT_DIR / "uvix_episode_spacing_vs_return.png")
    save_distribution_plot(episodes, OUTPUT_DIR / "uvix_episode_return_distribution.png")

    quantiles = episodes["episode_return"].quantile([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    quantile_frame = quantiles.rename("episode_return").reset_index().rename(columns={"index": "quantile"})
    quantile_frame["episode_return_pct"] = quantile_frame["episode_return"] * 100.0
    quantile_frame.to_csv(OUTPUT_DIR / "uvix_episode_return_quantiles.csv", index=False)

    data = episodes.dropna(subset=["days_since_previous_exit", "episode_return"])
    summary = {
        "episodes": int(len(episodes)),
        "episodes_with_spacing": int(len(data)),
        "win_rate": float((episodes["episode_return"] > 0).mean()),
        "average_return": float(episodes["episode_return"].mean()),
        "median_return": float(episodes["episode_return"].median()),
        "average_holding_days": float(episodes["holding_days"].mean()),
        "median_holding_days": float(episodes["holding_days"].median()),
        "correlation_spacing_vs_return": float(data["days_since_previous_exit"].corr(data["episode_return"])),
        "correlation_calendar_spacing_vs_return": float(
            data["calendar_days_since_previous_exit"].corr(data["episode_return"])
        ),
    }
    pd.DataFrame([summary]).to_csv(OUTPUT_DIR / "uvix_episode_spacing_summary.csv", index=False)
    print(pd.Series(summary).to_string())
    print("\nTop positive episodes")
    print(episodes.sort_values("episode_return", ascending=False).head(10).to_string(index=False))
    print("\nWorst episodes")
    print(episodes.sort_values("episode_return", ascending=True).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
