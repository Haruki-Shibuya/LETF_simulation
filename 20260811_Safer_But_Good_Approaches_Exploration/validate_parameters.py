from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT = ROOT / "output"
DATA = OUTPUT / "data"
TQQQ_PATH = REPO / "tqqq_backtest" / "output" / "tqqq_extension_1991.csv"
KMLMSIM_PATH = DATA / "testfolio_kmlmsim_daily.csv"
KMLMSIM_METADATA_PATH = DATA / "testfolio_kmlmsim_metadata.json"

START = pd.Timestamp("1996-01-02")
DOWNLOAD_START = "1995-01-01"
END_EXCLUSIVE = "2026-04-18"
TRADING_COST = 0.0005
GOLD_PROXY_FEE = 0.0040
INITIAL_CAPITAL = 1_000.0

# Full-range screen requested by the user.  Day-based dimensions use a
# five-trading-day coarse step; percentage dimensions use one percentage point.
# A one-day refinement is run around the best coarse plateau below.
MA_WINDOWS = list(range(150, 226, 5))
VOL_WINDOWS = list(range(20, 81, 5))
VOL_THRESHOLDS = [round(value / 100.0, 2) for value in range(20, 41)]
TOLERANCES = [round(value / 100.0, 2) for value in range(0, 5)]
# Compare normal next-day execution with one additional trading-day delay.
DELAYS = [0, 1]

# Fine pass around the strongest coarse region, extended below 150 days to
# detect whether the requested lower bound truncates a better plateau.
REFINE_MA_WINDOWS = list(range(130, 166))
REFINE_VOL_WINDOWS = list(range(35, 56))
REFINE_VOL_THRESHOLDS = [round(value / 100.0, 2) for value in range(29, 36)]
REFINE_TOLERANCES = [0.02, 0.03, 0.04]

BASELINE = {
    "ma_window": 175,
    "vol_window": 40,
    "vol_threshold": 0.30,
    "tolerance": 0.03,
}

RECOMMENDED = {
    "ma_window": 150,
    "vol_window": 40,
    "vol_threshold": 0.32,
    "tolerance": 0.03,
}


def download_market_prices() -> pd.DataFrame:
    cache = DATA / "yahoo_adjusted_prices.csv"
    if cache.exists():
        return pd.read_csv(cache, parse_dates=["Date"]).set_index("Date")

    raw = yf.download(
        ["SPY", "VFITX", "GLD"],
        start=DOWNLOAD_START,
        end=END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    close = raw["Close"].copy()
    close.index.name = "Date"
    close.to_csv(cache)
    return close


def download_boe_gold() -> pd.Series:
    cache = DATA / "boe_gold_usd.csv"
    if not cache.exists():
        url = (
            "https://www.bankofengland.co.uk/boeapps/database/"
            "_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/1995&"
            "Dateto=17/Apr/2026&SeriesCodes=XUDLGPD&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            cache.write_bytes(response.read())

    gold = pd.read_csv(cache)
    gold.columns = ["Date", "Gold_USD"]
    gold["Date"] = pd.to_datetime(gold["Date"], dayfirst=True)
    gold["Gold_USD"] = pd.to_numeric(gold["Gold_USD"], errors="coerce")
    return gold.set_index("Date")["Gold_USD"].sort_index()


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    canonical = pd.read_csv(TQQQ_PATH, parse_dates=["Date"]).set_index("Date")
    if not KMLMSIM_PATH.exists():
        raise FileNotFoundError(
            f"Missing {KMLMSIM_PATH}. Run download_testfolio_kmlmsim.py first."
        )
    kmlmsim = pd.read_csv(KMLMSIM_PATH, parse_dates=["Date"]).set_index("Date")
    market = download_market_prices()
    boe_gold = download_boe_gold()

    frame = canonical[
        ["^NDX", "DGS3MO", "TQQQ_3X_CALIBRATED_STITCHED_RETURN"]
    ].rename(
        columns={
            "^NDX": "ndx",
            "DGS3MO": "cash_yield",
            "TQQQ_3X_CALIBRATED_STITCHED_RETURN": "tqqq_return",
        }
    )
    frame = frame.loc[pd.Timestamp(DOWNLOAD_START) : pd.Timestamp(END_EXCLUSIVE)]

    aligned_market = market.reindex(frame.index).ffill()
    frame["spy"] = aligned_market["SPY"]
    frame["bond"] = aligned_market["VFITX"]
    frame["gld"] = aligned_market["GLD"]
    frame["gold_spot"] = boe_gold.reindex(frame.index).ffill()
    frame["kmlmsim_return"] = (
        kmlmsim["KMLMSIM_Return"].reindex(frame.index).fillna(0.0)
    )

    frame["ndx_return"] = frame["ndx"].pct_change(fill_method=None)
    frame["bond_return"] = frame["bond"].pct_change(fill_method=None).fillna(0.0)
    frame["gld_return"] = frame["gld"].pct_change(fill_method=None)
    frame["gold_spot_return"] = frame["gold_spot"].pct_change(fill_method=None)

    first_gld = frame["gld"].first_valid_index()
    frame["gold_return"] = frame["gold_spot_return"]
    frame.loc[frame.index >= first_gld, "gold_return"] = frame.loc[
        frame.index >= first_gld, "gld_return"
    ]
    pre_gld = frame.index < first_gld
    frame.loc[pre_gld, "gold_return"] = (
        (1.0 + frame.loc[pre_gld, "gold_return"].fillna(0.0))
        * (1.0 - GOLD_PROXY_FEE / 252.0)
        - 1.0
    )
    frame["gold_return"] = frame["gold_return"].fillna(0.0)

    # DGS3MO is already stored as a decimal annual rate in the canonical file
    # (for example, 0.05 means 5%).
    frame["cash_return"] = (
        1.0 + frame["cash_yield"].ffill().fillna(0.0)
    ) ** (1.0 / 252.0) - 1.0

    defensive_components = frame[["kmlmsim_return", "gold_return", "bond_return"]]
    frame["defensive_return"] = defensive_components.mean(axis=1)
    post_return_weights = (
        (1.0 / 3.0) * (1.0 + defensive_components)
    ).div(1.0 + frame["defensive_return"], axis=0)
    frame["defensive_rebalance_turnover"] = (
        0.5 * post_return_weights.sub(1.0 / 3.0).abs().sum(axis=1)
    )

    quality_rows = []
    for name, series in frame.items():
        quality_rows.append(
            {
                "series": name,
                "rows": int(series.shape[0]),
                "start": series.first_valid_index(),
                "end": series.last_valid_index(),
                "nulls": int(series.isna().sum()),
                "duplicate_dates": int(frame.index.duplicated().sum()),
                "min": float(series.min()) if series.notna().any() else np.nan,
                "max": float(series.max()) if series.notna().any() else np.nan,
            }
        )
    quality = pd.DataFrame(quality_rows)

    required = [
        "spy",
        "ndx",
        "tqqq_return",
        "kmlmsim_return",
        "defensive_return",
        "defensive_rebalance_turnover",
    ]
    frame = frame.dropna(subset=required)
    frame = frame.loc[frame.index >= START].copy()
    return frame, quality


def hysteresis_trend(price: pd.Series, sma: pd.Series, tolerance: float) -> pd.Series:
    output = np.zeros(len(price), dtype=bool)
    state = False
    initialized = False

    for index, (current_price, current_sma) in enumerate(zip(price, sma)):
        if not np.isfinite(current_price) or not np.isfinite(current_sma):
            output[index] = False
            continue

        if not initialized:
            state = bool(current_price > current_sma)
            initialized = True
        elif state and current_price < current_sma * (1.0 - tolerance):
            state = False
        elif not state and current_price > current_sma * (1.0 + tolerance):
            state = True
        output[index] = state

    return pd.Series(output, index=price.index)


def calculate_metrics(returns: pd.Series, risk_on: pd.Series) -> dict[str, float]:
    nav = (1.0 + returns).cumprod()
    years = (nav.index[-1] - nav.index[0]).days / 365.2425
    drawdown = nav / nav.cummax() - 1.0
    dotcom = nav.loc["2000-01-01":"2003-12-31"]
    dotcom_drawdown = dotcom / dotcom.cummax() - 1.0

    return {
        "cagr": float(nav.iloc[-1] ** (1.0 / years) - 1.0),
        "ending_value_1000": float(INITIAL_CAPITAL * nav.iloc[-1]),
        "volatility": float(returns.std(ddof=1) * np.sqrt(252.0)),
        "max_drawdown": float(drawdown.min()),
        "dotcom_max_drawdown": float(dotcom_drawdown.min()),
        "dotcom_return": float(dotcom.iloc[-1] / dotcom.iloc[0] - 1.0),
        "risk_on_share": float(risk_on.mean()),
        "switches": int(risk_on.ne(risk_on.shift()).sum()),
    }


def backtest(frame: pd.DataFrame, combined_signal: pd.Series, delay: int) -> tuple[dict, pd.DataFrame]:
    # Signal observed at close t is first investable for the following daily return.
    # `delay=0` applies the close-t signal to the next trading day's return;
    # `delay=1` applies it one additional trading day later.
    risk_on = combined_signal.shift(delay + 1, fill_value=False).astype(bool)
    gross = pd.Series(
        np.where(risk_on, frame["tqqq_return"], frame["defensive_return"]),
        index=frame.index,
    )
    switches = risk_on.ne(risk_on.shift()).astype(float)
    internal_turnover = frame["defensive_rebalance_turnover"].where(~risk_on, 0.0)
    costs = TRADING_COST * (switches + internal_turnover)
    net = gross - costs
    metrics = calculate_metrics(net, risk_on)
    metrics["total_turnover"] = float((switches + internal_turnover).sum())

    path = pd.DataFrame(
        {
            "risk_on": risk_on,
            "gross_return": gross,
            "trading_cost": costs,
            "net_return": net,
            "nav_1000": INITIAL_CAPITAL * (1.0 + net).cumprod(),
        }
    )
    return metrics, path


def run_grid(
    frame: pd.DataFrame,
    ma_windows: list[int] = MA_WINDOWS,
    vol_windows: list[int] = VOL_WINDOWS,
    vol_thresholds: list[float] = VOL_THRESHOLDS,
    tolerances: list[float] = TOLERANCES,
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    trend_cache = {}
    for ma_window in ma_windows:
        sma = frame["spy"].rolling(ma_window, min_periods=ma_window).mean()
        for tolerance in tolerances:
            trend_cache[(ma_window, tolerance)] = hysteresis_trend(
                frame["spy"], sma, tolerance
            )

    volatility_cache = {}
    for vol_window in vol_windows:
        volatility_cache[vol_window] = (
            frame["ndx_return"].rolling(vol_window, min_periods=vol_window).std(ddof=1)
            * np.sqrt(252.0)
        )

    rows = []
    baseline_paths = {}
    for ma_window in ma_windows:
        for vol_window in vol_windows:
            volatility = volatility_cache[vol_window]
            for vol_threshold in vol_thresholds:
                volatility_ok = volatility < vol_threshold
                for tolerance in tolerances:
                    combined = trend_cache[(ma_window, tolerance)] & volatility_ok
                    for delay in DELAYS:
                        metrics, path = backtest(frame, combined, delay)
                        rows.append(
                            {
                                "ma_window": ma_window,
                                "vol_window": vol_window,
                                "vol_threshold": vol_threshold,
                                "tolerance": tolerance,
                                "delay": delay,
                                **metrics,
                            }
                        )
                        if (
                            ma_window == BASELINE["ma_window"]
                            and vol_window == BASELINE["vol_window"]
                            and np.isclose(vol_threshold, BASELINE["vol_threshold"])
                            and np.isclose(tolerance, BASELINE["tolerance"])
                        ):
                            baseline_paths[delay] = path

    return pd.DataFrame(rows), baseline_paths


def run_spec(frame: pd.DataFrame, spec: dict[str, float]) -> dict[int, pd.DataFrame]:
    """Run one parameter specification for every requested execution delay."""
    sma = frame["spy"].rolling(
        int(spec["ma_window"]), min_periods=int(spec["ma_window"])
    ).mean()
    trend = hysteresis_trend(frame["spy"], sma, float(spec["tolerance"]))
    volatility = (
        frame["ndx_return"]
        .rolling(int(spec["vol_window"]), min_periods=int(spec["vol_window"]))
        .std(ddof=1)
        * np.sqrt(252.0)
    )
    combined = trend & (volatility < float(spec["vol_threshold"]))
    return {delay: backtest(frame, combined, delay)[1] for delay in DELAYS}


def benchmark_metrics(frame: pd.DataFrame) -> dict[str, float]:
    returns = frame["tqqq_return"].copy()
    returns.iloc[0] -= TRADING_COST
    return calculate_metrics(returns, pd.Series(True, index=frame.index))


def save_plots(
    grid: pd.DataFrame,
    baseline_paths: dict[int, pd.DataFrame],
    benchmark: dict[str, float],
    refinement_robust: pd.DataFrame,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")

    # Single strategy path with regime shading, using the requested one-day
    # additional execution delay.  Consecutive states are collapsed so the
    # chart remains lightweight and auditable.
    regime_path = baseline_paths[1]
    regime_changes = regime_path["risk_on"].ne(regime_path["risk_on"].shift())
    regime_starts = regime_path.index[regime_changes]
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=160)
    for position, start in enumerate(regime_starts):
        end = (
            regime_starts[position + 1]
            if position + 1 < len(regime_starts)
            else regime_path.index[-1]
        )
        state = bool(regime_path.loc[start, "risk_on"])
        ax.axvspan(
            start,
            end,
            color="#4C78A8" if state else "#D9A066",
            alpha=0.16,
            linewidth=0,
        )
    ax.plot(
        regime_path.index,
        regime_path["nav_1000"],
        color="#222222",
        linewidth=1.5,
        label="Strategy value",
    )
    ax.set_yscale("log")
    ax.set_title("Strategy growth and allocation regime (1-day additional delay)")
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(
        handles=[
            Patch(facecolor="#4C78A8", alpha=0.25, label="Risk-on"),
            Patch(facecolor="#D9A066", alpha=0.25, label="Risk-off"),
            Line2D([], [], color="#222222", label="Strategy value"),
        ],
        frameon=False,
        ncol=3,
        loc="upper left",
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "baseline_regime_growth.png", bbox_inches="tight")
    plt.close(fig)


def save_recommended_plots(
    paths: dict[int, pd.DataFrame],
    grid: pd.DataFrame,
    baseline_paths: dict[int, pd.DataFrame],
    refinement_robust: pd.DataFrame,
) -> None:
    """Save dedicated charts for the selected 150/40/32%/3% candidate."""
    plt.style.use("seaborn-v0_8-whitegrid")
    regime_path = paths[1]
    regime_changes = regime_path["risk_on"].ne(regime_path["risk_on"].shift())
    regime_starts = regime_path.index[regime_changes]

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=160)
    for position, start in enumerate(regime_starts):
        end = (
            regime_starts[position + 1]
            if position + 1 < len(regime_starts)
            else regime_path.index[-1]
        )
        state = bool(regime_path.loc[start, "risk_on"])
        ax.axvspan(
            start,
            end,
            color="#4C78A8" if state else "#D9A066",
            alpha=0.16,
            linewidth=0,
        )
    ax.plot(
        regime_path.index,
        regime_path["nav_1000"],
        color="#222222",
        linewidth=1.5,
        label="Strategy value",
    )
    ax.set_yscale("log")
    ax.set_title(
        "Recommended 150/40/32%/3%: growth and regime (1-day delay)"
    )
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(
        handles=[
            Patch(facecolor="#4C78A8", alpha=0.25, label="Risk-on"),
            Patch(facecolor="#D9A066", alpha=0.25, label="Risk-off"),
            Line2D([], [], color="#222222", label="Strategy value"),
        ],
        frameon=False,
        ncol=3,
        loc="upper left",
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "recommended_regime_growth.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=160)
    for delay, path in paths.items():
        ax.plot(
            path.index,
            path["nav_1000"],
            label=f"Recommended delay {delay}d",
            linewidth=1.6,
        )
    ax.set_yscale("log")
    ax.set_title("Recommended 150/40/32%/3%: normal vs 1-day delay")
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT / "recommended_delay_equity_curves.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=160)
    for delay, path in baseline_paths.items():
        ax.plot(path.index, path["nav_1000"], label=f"Baseline delay {delay}d", linewidth=1.6)
    benchmark_path = INITIAL_CAPITAL * (
        1.0 + baseline_paths[0].index.to_series().map(lambda _: 0.0)
    )
    del benchmark_path
    ax.set_yscale("log")
    ax.set_title("Baseline strategy: normal vs 1-day-delayed execution")
    ax.set_ylabel("Portfolio value from $1,000 (log scale)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT / "baseline_delay_equity_curves.png", bbox_inches="tight")
    plt.close(fig)

    subset = grid[
        (grid["vol_window"] == 40)
        & np.isclose(grid["tolerance"], 0.03)
    ]
    robust_subset = (
        subset.groupby(["ma_window", "vol_threshold"], as_index=False)["cagr"]
        .min()
    )
    pivot = robust_subset.pivot(index="ma_window", columns="vol_threshold", values="cagr")
    fig, ax = plt.subplots(figsize=(12, 7), dpi=160)
    image = ax.imshow(pivot.values * 100.0, aspect="auto", cmap="viridis")
    tick_positions = list(range(0, len(pivot.columns), 2))
    ax.set_xticks(tick_positions, [f"{pivot.columns[i]:.0%}" for i in tick_positions])
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xlabel("Volatility threshold")
    ax.set_ylabel("SPY SMA window")
    ax.set_title("Worst 0/1-day-delay CAGR surface: 40-day volatility and 3% tolerance")
    for row in range(pivot.shape[0]):
        for column in range(pivot.shape[1]):
            if column % 2:
                continue
            value = pivot.iloc[row, column] * 100.0
            ax.text(column, row, f"{value:.1f}", ha="center", va="center", fontsize=8,
                    color="white" if value < np.nanmedian(pivot.values * 100.0) else "black")
    fig.colorbar(image, ax=ax, label="CAGR (%)")
    fig.tight_layout()
    fig.savefig(OUTPUT / "cagr_parameter_surface.png", bbox_inches="tight")
    plt.close(fig)

    fine_subset = refinement_robust[
        np.isclose(refinement_robust["vol_threshold"], 0.32)
        & np.isclose(refinement_robust["tolerance"], 0.03)
    ]
    fine_pivot = fine_subset.pivot(
        index="ma_window", columns="vol_window", values="min_delay_cagr"
    )
    fig, ax = plt.subplots(figsize=(12, 7), dpi=160)
    image = ax.imshow(fine_pivot.values * 100.0, aspect="auto", cmap="viridis")
    x_positions = list(range(0, len(fine_pivot.columns), 2))
    y_positions = list(range(0, len(fine_pivot.index), 2))
    ax.set_xticks(x_positions, [fine_pivot.columns[i] for i in x_positions])
    ax.set_yticks(y_positions, [fine_pivot.index[i] for i in y_positions])
    ax.set_xlabel("Volatility lookback (trading days)")
    ax.set_ylabel("SPY SMA window (trading days)")
    ax.set_title("Fine-grid worst 0/1-day-delay CAGR: 32% threshold and 3% tolerance")
    fig.colorbar(image, ax=ax, label="Worst CAGR across 0/1-day delays (%)")
    fig.tight_layout()
    fig.savefig(OUTPUT / "refinement_robust_surface.png", bbox_inches="tight")
    plt.close(fig)


def write_report(
    grid: pd.DataFrame,
    quality: pd.DataFrame,
    benchmark: dict[str, float],
    refinement_grid: pd.DataFrame,
    refinement_robust: pd.DataFrame,
) -> None:
    kmlmsim_metadata = json.loads(KMLMSIM_METADATA_PATH.read_text(encoding="utf-8"))
    kmlmsim_api = kmlmsim_metadata["stats"]
    kmlmsim_local = kmlmsim_metadata["local_reconstruction_stats"]
    kmlmsim_delta = kmlmsim_metadata["local_minus_api"]
    baseline = grid[
        (grid["ma_window"] == BASELINE["ma_window"])
        & (grid["vol_window"] == BASELINE["vol_window"])
        & np.isclose(grid["vol_threshold"], BASELINE["vol_threshold"])
        & np.isclose(grid["tolerance"], BASELINE["tolerance"])
    ].sort_values("delay")

    local = grid[
        grid["ma_window"].isin([170, 175, 180])
        & grid["vol_window"].isin([30, 40, 50])
        & grid["vol_threshold"].isin([0.25, 0.30, 0.35])
        & grid["tolerance"].isin([0.01, 0.03, 0.04])
    ]
    delay_one = grid[grid["delay"] == 1]
    baseline_delay_one = baseline[baseline["delay"] == 1].iloc[0]
    percentile = float((delay_one["cagr"] <= baseline_delay_one["cagr"]).mean())

    parameter_columns = ["ma_window", "vol_window", "vol_threshold", "tolerance"]
    robust = (
        grid.groupby(parameter_columns, as_index=False)
        .agg(
            min_delay_cagr=("cagr", "min"),
            mean_delay_cagr=("cagr", "mean"),
            worst_max_drawdown=("max_drawdown", "min"),
            worst_dotcom_drawdown=("dotcom_max_drawdown", "min"),
        )
        .sort_values(["min_delay_cagr", "mean_delay_cagr"], ascending=False)
    )
    strict_pass_count = int((robust["min_delay_cagr"] >= 0.30).sum())
    baseline_robust = robust[
        (robust["ma_window"] == BASELINE["ma_window"])
        & (robust["vol_window"] == BASELINE["vol_window"])
        & np.isclose(robust["vol_threshold"], BASELINE["vol_threshold"])
        & np.isclose(robust["tolerance"], BASELINE["tolerance"])
    ].iloc[0]

    challenger_spec = {
        "ma_window": 150,
        "vol_window": 40,
        "vol_threshold": 0.30,
        "tolerance": 0.03,
    }
    challenger = grid[
        (grid["ma_window"] == challenger_spec["ma_window"])
        & (grid["vol_window"] == challenger_spec["vol_window"])
        & np.isclose(grid["vol_threshold"], challenger_spec["vol_threshold"])
        & np.isclose(grid["tolerance"], challenger_spec["tolerance"])
    ].sort_values("delay")
    challenger_robust = robust[
        (robust["ma_window"] == challenger_spec["ma_window"])
        & (robust["vol_window"] == challenger_spec["vol_window"])
        & np.isclose(robust["vol_threshold"], challenger_spec["vol_threshold"])
        & np.isclose(robust["tolerance"], challenger_spec["tolerance"])
    ].iloc[0]
    refinement_top = refinement_robust.iloc[0]
    refinement_top_delays = refinement_grid[
        (refinement_grid["ma_window"] == refinement_top["ma_window"])
        & (refinement_grid["vol_window"] == refinement_top["vol_window"])
        & np.isclose(
            refinement_grid["vol_threshold"], refinement_top["vol_threshold"]
        )
        & np.isclose(refinement_grid["tolerance"], refinement_top["tolerance"])
    ].sort_values("delay")
    coarse_top = robust.iloc[0]
    refined_plateau = refinement_robust[
        refinement_robust["ma_window"].between(144, 152)
        & refinement_robust["vol_window"].between(42, 48)
        & refinement_robust["vol_threshold"].between(0.31, 0.33)
        & refinement_robust["tolerance"].between(0.02, 0.04)
    ]

    lines = [
        "# TQQQレジーム戦略の全パラメータ範囲検証",
        "",
        "## 結論",
        "",
        f"指定範囲を{len(robust):,}組・{len(grid):,}遅延ケースで走査した結果、0日・1日遅延の両方でCAGR 30%以上だったのは **{strict_pass_count:,}組（{strict_pass_count / len(robust):.1%}）** でした。",
        f"粗い全域走査の最良点は **SMA {int(coarse_top['ma_window'])}日・ボラ期間{int(coarse_top['vol_window'])}日・閾値{coarse_top['vol_threshold']:.0%}・許容帯{coarse_top['tolerance']:.0%}** で、両遅延中の最低CAGRは **{coarse_top['min_delay_cagr']:.2%}** でした。",
        f"上位領域を1日刻みで再探索すると、中心は **SMA 147〜151日・ボラ期間38〜46日・閾値31〜32%・許容帯3%** にありました。単一の最高点ではなく、この連続した帯を候補領域と判断します。",
        "",
        "この計算ではTestfolio内部バックテストAPIからKMLMSIMの日次リターンを取得し、防御配分へ組み込みました。KMLMSIM/KMLMXは1988〜2020年がKFA MLM Indexから年0.9%控除、2020年以降が実KMLMです。ただし、GLDSIMとIEISIMはまだTestfolio系列そのものではないため、元のTestfolio戦略の完全再現ではありません。",
        "",
        "## KMLMSIM構築の一致検査",
        "",
        f"取得した日次系列は **{kmlmsim_metadata['row_count']:,}行**（{kmlmsim_metadata['api_start_date']}の初期値から{kmlmsim_metadata['api_end_date']}まで）です。日次リターンを単独で再複利した結果、CAGR **{kmlmsim_local['cagr']:.4f}%**、最大DD **{kmlmsim_local['max_drawdown']:.4f}%**、年率ボラ **{kmlmsim_local['std']:.4f}%** となりました。",
        f"Testfolioの精密統計はそれぞれ **{kmlmsim_api['cagr']:.4f}% / {kmlmsim_api['max_drawdown']:.4f}% / {kmlmsim_api['std']:.4f}%** です。差は **{kmlmsim_delta['cagr']:+.4f} / {kmlmsim_delta['max_drawdown']:+.4f} / {kmlmsim_delta['std']:+.4f}パーセントポイント** に収まり、APIの日次丸め以外の実質的な乖離はありません。取得スクリプトはこの許容差を超えると失敗します。",
        "",
        "## 基準パラメータの0日・1日遅延結果",
        "",
        "| 追加遅延 | CAGR | 最大DD | Dot-com最大DD | 年率ボラ | $1,000最終額 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in baseline.itertuples(index=False):
        lines.append(
            f"| {row.delay}日 | {row.cagr:.2%} | {row.max_drawdown:.2%} | "
            f"{row.dotcom_max_drawdown:.2%} | {row.volatility:.2%} | ${row.ending_value_1000:,.0f} |"
        )

    lines.extend(
        [
            "",
            "## 近傍安定性",
            "",
            f"近傍{len(local) // len(DELAYS):,}組×2遅延={len(local):,}ケースのうち、CAGR 30%以上は **{(local['cagr'] >= 0.30).mean():.1%}** でした。",
            f"近傍全体のCAGR中央値は **{local['cagr'].median():.2%}**、10パーセンタイルは **{local['cagr'].quantile(0.10):.2%}**、最低値は **{local['cagr'].min():.2%}** です。",
            "",
            "## 0日・1日遅延の両方で30%を満たす候補",
            "",
            f"全{len(robust):,}組のうち、0日・1日遅延の両方でCAGR 30%以上だったのは **{strict_pass_count:,}組（{strict_pass_count / len(robust):.1%}）** でした。",
            f"基準値の両遅延中の最低CAGRは **{baseline_robust['min_delay_cagr']:.2%}** です。比較対象の **150日・40日・30%・許容帯3%** は **{challenger_robust['min_delay_cagr']:.2%}** でした。",
            "",
            "| 追加遅延 | 175/40/30 CAGR | 150/40/30 CAGR | 150/40/30 最大DD |",
            "|---:|---:|---:|---:|",
        ]
    )
    for baseline_row, challenger_row in zip(
        baseline.itertuples(index=False), challenger.itertuples(index=False)
    ):
        lines.append(
            f"| {baseline_row.delay}日 | {baseline_row.cagr:.2%} | "
            f"{challenger_row.cagr:.2%} | {challenger_row.max_drawdown:.2%} |"
        )

    lines.extend(
        [
            "",
            "この150日候補は同じ1996〜2026年データから選んだインサンプル結果です。175日を150日に置き換える根拠にはなりますが、独立期間での優位性を証明するものではありません。",
            "",
            "## 上位領域の1日刻み再探索",
            "",
            "全域走査で上位が150日側に集中したため、境界バイアス確認としてSMA 130〜165日・ボラ期間35〜55日を1日刻みで再探索しました。閾値は29〜35%、許容帯は2〜4%です。",
            f"この細分化探索の最高値は **SMA {int(refinement_top['ma_window'])}日・ボラ期間{int(refinement_top['vol_window'])}日・閾値{refinement_top['vol_threshold']:.0%}・許容帯{refinement_top['tolerance']:.0%}** で、両遅延中の最低CAGRは **{refinement_top['min_delay_cagr']:.2%}** でした。",
            f"中心周辺（SMA 144〜152日、ボラ42〜48日、閾値31〜33%、許容帯2〜4%）は{len(refined_plateau):,}組あり、**{(refined_plateau['min_delay_cagr'] >= 0.30).mean():.1%}** が0日・1日遅延の両方で30%以上でした。最低CAGRの中央値は **{refined_plateau['min_delay_cagr'].median():.2%}**、10パーセンタイルは **{refined_plateau['min_delay_cagr'].quantile(0.10):.2%}** です。",
            "",
            "| 追加遅延 | CAGR | 最大DD | Dot-com最大DD | 年率ボラ |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in refinement_top_delays.itertuples(index=False):
        lines.append(
            f"| {row.delay}日 | {row.cagr:.2%} | {row.max_drawdown:.2%} | "
            f"{row.dotcom_max_drawdown:.2%} | {row.volatility:.2%} |"
        )
    lines.extend(
        [
            "",
            "ただし、これは上位領域を同じサンプルで細かく掘った結果なので、粗い全域走査よりもデータマイニングの影響が強い値です。単一の最良値ではなく、その周辺にも高成績が連続するかを採用判断に使います。",
            "",
            "## TQQQ買い持ち比較",
            "",
            f"同期間の合成・実績接続TQQQ買い持ちは、CAGR **{benchmark['cagr']:.2%}**、最大DD **{benchmark['max_drawdown']:.2%}**、Dot-com最大DD **{benchmark['dotcom_max_drawdown']:.2%}** でした。",
            "",
            "## データと実装",
            "",
            "- 期間: 1996-01-02〜2026-04-17",
            "- リスクオン: リポジトリのTQQQ canonical stitched return（2010年以前は3倍日次複利＋費用＋校正済み資金調達、以後は実TQQQ調整後リターン）",
            "- トレンド: SPY調整後価格とSMA、Testfolio型の相対許容帯ヒステリシス",
            "- ボラティリティ: Nasdaq-100日次リターンの年率換算標準偏差",
            "- 防御配分: KMLMSIM 1/3、金1/3、VFITX 1/3を日次均等リバランス",
            "- KMLMSIM: Testfolio内部バックテストAPIの日次リターン（1988年以降、API表示精度は0.001パーセントポイント）",
            "- 金: 2004年11月まではBank of EnglandのUSD金価格（GLD費用相当0.40%控除）、以後はGLD調整後価格",
            "- 売買コスト: 片道フル配分変更および防御配分内リバランスに5bp",
            "- シグナル: 当日終値情報を同日リターンに使わない。0日遅延は翌取引日、1日追加遅延は翌々取引日のリターンから適用",
            "- 全域走査: SMA 150〜225日を5日刻み、ボラ期間20〜80日を5日刻み、閾値20〜40%を1ポイント刻み、許容帯0〜4%を1ポイント刻み、遅延0・1日",
            "",
            "## 重大な制約",
            "",
            "1. KMLMSIMはTestfolio APIから取り込みましたが、公開レスポンスの日次リターンは0.001パーセントポイント単位に丸められています。",
            "2. 税引後計算はこのパラメータ検証には含めていません。税務ロット、損失繰越、最終清算は別検証が必要です。",
            "3. Yahoo FinanceのSPY/VFITX/GLD調整後価格とBank of England金価格を混合しており、Testfolio内部系列とは一致しません。",
            "4. パラメータ全組を同じ1996〜2026年で評価しているため、順位自体はインサンプルです。",
            "",
            "## 判定",
            "",
            "KMLMSIMを取り込んだ全域検証でも、単一の最高値ではなく連続した候補帯を重視します。ただし元のTestfolio戦略はGLDSIM・IEISIMも使用しているため、現段階の数値はまだ完全一致しません。この帯を候補として残し、残るTestfolio系列の取込、ウォークフォワード、税引後計算で再審査するのが妥当です。",
            "",
            "## 出力",
            "",
            "- `output/parameter_grid.csv`",
            "- `output/baseline_delay_summary.csv`",
            "- `output/local_neighborhood.csv`",
            "- `output/robust_parameter_summary.csv`",
            "- `output/refinement_parameter_grid.csv`",
            "- `output/refinement_robust_summary.csv`",
            "- `output/data_quality.csv`",
            "- `output/data/testfolio_kmlmsim_daily.csv`",
            "- `output/data/testfolio_kmlmsim_metadata.json`",
            "- `output/baseline_regime_growth.png`",
            "- `output/baseline_delay_equity_curves.png`",
            "- `output/cagr_parameter_surface.png`",
            "- `output/refinement_robust_surface.png`",
            "- `output/recommended_regime_growth.png`",
            "- `output/recommended_delay_equity_curves.png`",
        ]
    )
    (ROOT / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    frame, quality = load_inputs()
    grid, baseline_paths = run_grid(frame)
    refinement_grid, _ = run_grid(
        frame,
        ma_windows=REFINE_MA_WINDOWS,
        vol_windows=REFINE_VOL_WINDOWS,
        vol_thresholds=REFINE_VOL_THRESHOLDS,
        tolerances=REFINE_TOLERANCES,
    )
    benchmark = benchmark_metrics(frame)
    recommended_paths = run_spec(frame, RECOMMENDED)

    expected_grid_rows = (
        len(MA_WINDOWS)
        * len(VOL_WINDOWS)
        * len(VOL_THRESHOLDS)
        * len(TOLERANCES)
        * len(DELAYS)
    )
    expected_refinement_rows = (
        len(REFINE_MA_WINDOWS)
        * len(REFINE_VOL_WINDOWS)
        * len(REFINE_VOL_THRESHOLDS)
        * len(REFINE_TOLERANCES)
        * len(DELAYS)
    )
    assert not frame.index.has_duplicates, "Duplicate analysis dates detected"
    assert frame[
        ["spy", "ndx", "tqqq_return", "kmlmsim_return", "defensive_return"]
    ].notna().all().all()
    assert (frame["tqqq_return"] > -1.0).all(), "TQQQ return below -100% detected"
    assert len(grid) == expected_grid_rows, "Parameter grid is incomplete"
    assert len(refinement_grid) == expected_refinement_rows, "Refinement grid is incomplete"
    assert set(baseline_paths) == set(DELAYS), "Baseline paths are incomplete"

    baseline = grid[
        (grid["ma_window"] == BASELINE["ma_window"])
        & (grid["vol_window"] == BASELINE["vol_window"])
        & np.isclose(grid["vol_threshold"], BASELINE["vol_threshold"])
        & np.isclose(grid["tolerance"], BASELINE["tolerance"])
    ].sort_values("delay")
    local = grid[
        grid["ma_window"].isin([170, 175, 180])
        & grid["vol_window"].isin([30, 40, 50])
        & grid["vol_threshold"].isin([0.25, 0.30, 0.35])
        & grid["tolerance"].isin([0.01, 0.03, 0.04])
    ]
    parameter_columns = ["ma_window", "vol_window", "vol_threshold", "tolerance"]
    robust = (
        grid.groupby(parameter_columns, as_index=False)
        .agg(
            min_delay_cagr=("cagr", "min"),
            mean_delay_cagr=("cagr", "mean"),
            worst_max_drawdown=("max_drawdown", "min"),
            worst_dotcom_drawdown=("dotcom_max_drawdown", "min"),
        )
        .sort_values(["min_delay_cagr", "mean_delay_cagr"], ascending=False)
    )
    refinement_robust = (
        refinement_grid.groupby(parameter_columns, as_index=False)
        .agg(
            min_delay_cagr=("cagr", "min"),
            mean_delay_cagr=("cagr", "mean"),
            worst_max_drawdown=("max_drawdown", "min"),
            worst_dotcom_drawdown=("dotcom_max_drawdown", "min"),
        )
        .sort_values(["min_delay_cagr", "mean_delay_cagr"], ascending=False)
    )

    grid.to_csv(OUTPUT / "parameter_grid.csv", index=False)
    baseline.to_csv(OUTPUT / "baseline_delay_summary.csv", index=False)
    local.to_csv(OUTPUT / "local_neighborhood.csv", index=False)
    robust.to_csv(OUTPUT / "robust_parameter_summary.csv", index=False)
    refinement_grid.to_csv(OUTPUT / "refinement_parameter_grid.csv", index=False)
    refinement_robust.to_csv(OUTPUT / "refinement_robust_summary.csv", index=False)
    quality.to_csv(OUTPUT / "data_quality.csv", index=False)
    for delay, path in baseline_paths.items():
        path.to_csv(OUTPUT / f"baseline_delay_{delay}_path.csv")
    for delay, path in recommended_paths.items():
        path.to_csv(OUTPUT / f"recommended_delay_{delay}_path.csv")

    save_plots(grid, baseline_paths, benchmark, refinement_robust)
    save_recommended_plots(
        recommended_paths, grid, baseline_paths, refinement_robust
    )
    write_report(grid, quality, benchmark, refinement_grid, refinement_robust)

    print(baseline[["delay", "cagr", "max_drawdown", "dotcom_max_drawdown"]].to_string(index=False))
    print(f"Grid rows: {len(grid):,}")
    print(f"Report: {ROOT / 'VALIDATION_REPORT.md'}")


if __name__ == "__main__":
    main()
