from __future__ import annotations

import argparse
import io
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import yfinance as yf


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS_PER_YEAR = 252
DEFAULT_FETCH_START = "1990-01-01"
DEFAULT_BACKTEST_START = "1992-01-01"
DEFAULT_SIGNAL_SOURCE = "underlier"
DEFAULT_SIGNAL_WINDOW = 160
DEFAULT_TECL_ANNUAL_FEE = 0.0087
DEFAULT_SOXL_ANNUAL_FEE = 0.0075
DEFAULT_SWITCH_DATE = "2021-08-25"
DEFAULT_RATE_SERIES_ID = "DGS3MO"
DEFAULT_BELOW_ENTRY_MODE = "sma_drawdown"
DEFAULT_BELOW_ENTRY_REFERENCE_SOURCE = "signal"
DEFAULT_DRAWDOWN_MIN = 0.0
DEFAULT_DRAWDOWN_MAX = 60.0
DEFAULT_DRAWDOWN_STEP = 0.5
DEFAULT_WAIT_TMF = 50.0
DEFAULT_WAIT_GLD = 50.0
DEFAULT_GLD_PROXY_TICKER = "GC=F"


@dataclass(frozen=True)
class LeveredProxyConfig:
    letf_ticker: str
    leverage: float
    annual_fee: float


def download_adj_close(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    download_kwargs = {
        "tickers": tickers,
        "start": start,
        "auto_adjust": True,
        "progress": False,
        "threads": False,
    }
    if end is not None:
        download_kwargs["end"] = end
    raw = yf.download(**download_kwargs)
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers
    close = close.rename_axis(index="Date", columns="Ticker")
    return close.sort_index()


def download_fred_series(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    frame.columns = ["date", series_id]
    frame["date"] = pd.to_datetime(frame["date"])
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce") / 100.0
    return frame.set_index("date")[series_id].sort_index()


def compute_return_series_from_prices(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    returns = valid.pct_change().fillna(0.0).reindex(series.index)
    returns.name = f"{series.name}_RETURN"
    return returns


def calibrate_constant_log_drag(benchmark_returns: pd.Series, actual_returns: pd.Series) -> float:
    overlap = pd.DataFrame({"benchmark": benchmark_returns, "actual": actual_returns}).dropna()
    if overlap.empty:
        return 0.0
    return float((np.log1p(overlap["benchmark"]).sum() - np.log1p(overlap["actual"]).sum()) / len(overlap))


def compute_beta_proxy(legacy_returns: pd.Series, modern_returns: pd.Series) -> tuple[float, pd.Series]:
    overlap = pd.DataFrame({"legacy": legacy_returns, "modern": modern_returns}).dropna()
    beta = float(np.cov(overlap["legacy"], overlap["modern"], ddof=0)[0, 1] / np.var(overlap["legacy"]))
    return beta, legacy_returns * beta


def splice_returns(
    legacy_proxy_returns: pd.Series,
    modern_returns: pd.Series,
    modern_start: pd.Timestamp,
) -> pd.Series:
    hybrid = legacy_proxy_returns.copy()
    hybrid.loc[hybrid.index >= modern_start] = modern_returns.loc[hybrid.index >= modern_start]
    return hybrid


def build_model_returns(
    benchmark_returns: pd.Series,
    financing_rate: pd.Series,
    leverage: float,
    annual_fee: float,
    financing_multiplier: float,
) -> pd.Series:
    daily_fee_drag = annual_fee / TRADING_DAYS_PER_YEAR
    daily_financing_drag = financing_multiplier * financing_rate / TRADING_DAYS_PER_YEAR
    modeled = leverage * benchmark_returns - daily_fee_drag - daily_financing_drag
    return modeled.clip(lower=-0.999999)


def cumulative_log_gap(
    financing_multiplier: float,
    benchmark_returns: pd.Series,
    actual_returns: pd.Series,
    financing_rate: pd.Series,
    leverage: float,
    annual_fee: float,
) -> float:
    modeled = build_model_returns(
        benchmark_returns,
        financing_rate,
        leverage=leverage,
        annual_fee=annual_fee,
        financing_multiplier=financing_multiplier,
    )
    overlap = pd.DataFrame({"modeled": modeled, "actual": actual_returns}).dropna()
    return float(np.log1p(overlap["modeled"]).sum() - np.log1p(overlap["actual"]).sum())


def calibrate_financing_multiplier(
    benchmark_returns: pd.Series,
    actual_returns: pd.Series,
    financing_rate: pd.Series,
    leverage: float,
    annual_fee: float,
    lower_bound: float = 0.0,
    upper_bound: float = 4.0,
) -> float:
    low = lower_bound
    high = upper_bound
    low_gap = cumulative_log_gap(low, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee)
    high_gap = cumulative_log_gap(high, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee)

    while low_gap * high_gap > 0 and high < 64.0:
        high *= 2.0
        high_gap = cumulative_log_gap(high, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee)

    if low_gap == 0:
        return low
    if high_gap == 0:
        return high

    if low_gap * high_gap > 0:
        candidates = np.arange(0.0, 64.01, 0.01)
        gaps = [
            abs(cumulative_log_gap(k, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee))
            for k in candidates
        ]
        return float(candidates[int(np.argmin(gaps))])

    for _ in range(80):
        mid = (low + high) / 2.0
        mid_gap = cumulative_log_gap(mid, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee)
        if abs(mid_gap) < 1e-12:
            return mid
        if low_gap * mid_gap <= 0:
            high = mid
            high_gap = mid_gap
        else:
            low = mid
            low_gap = mid_gap

    return (low + high) / 2.0


def stitch_return_series(
    synthetic_returns: pd.Series,
    actual_prices: pd.Series,
) -> tuple[pd.Series, pd.Timestamp]:
    actual_prices = actual_prices.dropna()
    actual_returns = actual_prices.pct_change()
    stitched = synthetic_returns.copy()
    first_actual_return_date = actual_returns.first_valid_index()
    if first_actual_return_date is not None:
        stitched.loc[first_actual_return_date:] = actual_returns.loc[first_actual_return_date:]
    return stitched, actual_prices.index[0]


def build_anchored_price_series(
    returns: pd.Series,
    anchor_date: pd.Timestamp,
    anchor_value: float,
    output_name: str,
) -> pd.Series:
    aligned = returns.copy().sort_index()
    levels = pd.Series(index=aligned.index, dtype=float, name=output_name)
    levels.loc[anchor_date] = anchor_value
    index = aligned.index
    anchor_pos = index.get_loc(anchor_date)

    for i in range(anchor_pos + 1, len(index)):
        prev = index[i - 1]
        cur = index[i]
        levels.loc[cur] = levels.loc[prev] * (1.0 + aligned.loc[cur])

    for i in range(anchor_pos - 1, -1, -1):
        cur = index[i]
        nxt = index[i + 1]
        levels.loc[cur] = levels.loc[nxt] / (1.0 + aligned.loc[nxt])

    return levels


def build_proxy_price_series(returns: pd.Series, output_name: str) -> pd.Series:
    levels = (1.0 + returns.fillna(0.0)).cumprod()
    levels.iloc[0] = 1.0
    levels.name = output_name
    return levels


def compare_model_to_actual(actual_prices: pd.Series, modeled_returns: pd.Series) -> dict[str, float]:
    actual_returns = compute_return_series_from_prices(actual_prices)
    overlap = pd.DataFrame({"actual": actual_returns, "modeled": modeled_returns}).dropna()
    return {
        "overlap_start": overlap.index[0].strftime("%Y-%m-%d"),
        "overlap_end": overlap.index[-1].strftime("%Y-%m-%d"),
        "overlap_days": len(overlap),
        "daily_return_corr": float(overlap["actual"].corr(overlap["modeled"])),
        "daily_return_mae_bps": float((overlap["actual"] - overlap["modeled"]).abs().mean() * 10000.0),
        "actual_growth_multiple": float(np.exp(np.log1p(overlap["actual"]).sum())),
        "modeled_growth_multiple": float(np.exp(np.log1p(overlap["modeled"]).sum())),
    }


def load_canonical_tqqq() -> pd.DataFrame:
    path = REPO_DIR / "tqqq_backtest" / "output" / "tqqq_extension_1991.csv"
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()
    return frame[["TQQQ_3X_CALIBRATED_STITCHED_RETURN", "TQQQ_3X_CALIBRATED_STITCHED"]].rename(
        columns={
            "TQQQ_3X_CALIBRATED_STITCHED_RETURN": "TQQQ_RETURN",
            "TQQQ_3X_CALIBRATED_STITCHED": "TQQQ_PRICE",
        }
    )


def load_canonical_tmf() -> pd.DataFrame:
    path = REPO_DIR / "tmf_backtest" / "output" / "tmf_extension_1991.csv"
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()
    return frame[["TMF_3X_CALIBRATED_STITCHED_RETURN", "TMF_3X_CALIBRATED_STITCHED"]].rename(
        columns={
            "TMF_3X_CALIBRATED_STITCHED_RETURN": "TMF_RETURN",
            "TMF_3X_CALIBRATED_STITCHED": "TMF_PRICE",
        }
    )


def build_gld_series(prices: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    proxy_returns = compute_return_series_from_prices(prices[DEFAULT_GLD_PROXY_TICKER]).rename("GOLD_PROXY_RETURN")
    actual_returns = compute_return_series_from_prices(prices["GLD"]).rename("GLD_ACTUAL_RETURN")
    daily_log_drag = calibrate_constant_log_drag(proxy_returns, actual_returns)
    daily_simple_drag = float(np.expm1(daily_log_drag))
    modeled_returns = (proxy_returns - daily_simple_drag).clip(lower=-0.999999).rename("GLD_MODELED_RETURN")
    first_proxy_date = proxy_returns.dropna().index.min()
    if first_proxy_date is not None:
        modeled_returns.loc[first_proxy_date] = 0.0

    stitched_returns, anchor_date = stitch_return_series(modeled_returns, prices["GLD"])
    stitched_price = build_anchored_price_series(
        stitched_returns,
        anchor_date=anchor_date,
        anchor_value=float(prices["GLD"].dropna().iloc[0]),
        output_name="GLD_STITCHED",
    )

    diag = compare_model_to_actual(prices["GLD"], modeled_returns)
    diag.update(
        {
            "proxy": "GLD",
            "legacy_proxy": DEFAULT_GLD_PROXY_TICKER,
            "daily_log_drag": daily_log_drag,
            "annualized_log_drag": daily_log_drag * TRADING_DAYS_PER_YEAR,
            "annualized_simple_drag": daily_simple_drag * TRADING_DAYS_PER_YEAR,
            "history_start": stitched_price.dropna().index[0].strftime("%Y-%m-%d"),
        }
    )

    frame = pd.DataFrame(
        {
            "GLD_RETURN": stitched_returns,
            "GLD_PRICE": stitched_price,
        }
    )
    return frame, diag


def build_tecl_series(prices: pd.DataFrame, rate: pd.Series, annual_fee: float) -> tuple[pd.DataFrame, dict[str, float]]:
    legacy_returns = compute_return_series_from_prices(prices["FSPTX"])
    modern_returns = compute_return_series_from_prices(prices["XLK"])
    beta, legacy_proxy_returns = compute_beta_proxy(legacy_returns, modern_returns)
    xlk_start = prices["XLK"].dropna().index[0]
    tech_hybrid_returns = splice_returns(legacy_proxy_returns, modern_returns, xlk_start).rename("TECH_HYBRID_RETURN")
    tech_hybrid_price = build_proxy_price_series(tech_hybrid_returns, "TECH_HYBRID_PRICE")

    actual_returns = compute_return_series_from_prices(prices["TECL"])
    overlap = pd.DataFrame({"bench": tech_hybrid_returns, "actual": actual_returns, "rate": rate}).dropna()
    financing_multiplier = calibrate_financing_multiplier(
        overlap["bench"],
        overlap["actual"],
        overlap["rate"],
        leverage=3.0,
        annual_fee=annual_fee,
    )
    modeled_returns = build_model_returns(tech_hybrid_returns, rate, 3.0, annual_fee, financing_multiplier).rename(
        "TECL_MODELED_RETURN"
    )
    stitched_returns, anchor_date = stitch_return_series(modeled_returns, prices["TECL"])
    stitched_price = build_anchored_price_series(
        stitched_returns,
        anchor_date=anchor_date,
        anchor_value=float(prices["TECL"].dropna().iloc[0]),
        output_name="TECL_STITCHED",
    )

    diag = compare_model_to_actual(prices["TECL"], modeled_returns)
    diag.update(
        {
            "proxy": "TECL",
            "legacy_proxy": "FSPTX",
            "modern_proxy": "XLK",
            "legacy_beta": beta,
            "financing_multiplier": financing_multiplier,
            "annual_fee": annual_fee,
            "history_start": stitched_price.dropna().index[0].strftime("%Y-%m-%d"),
        }
    )

    frame = pd.DataFrame(
        {
            "TECH_SIGNAL_PRICE": tech_hybrid_price,
            "TECL_RETURN": stitched_returns,
            "TECL_PRICE": stitched_price,
            "TECL_TRIGGER_PRICE": build_proxy_price_series(stitched_returns, "TECL_TRIGGER_PRICE"),
        }
    )
    return frame, diag


def build_soxl_series(
    prices: pd.DataFrame,
    rate: pd.Series,
    annual_fee: float,
    switch_date: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, float]]:
    legacy_returns = compute_return_series_from_prices(prices["FSELX"])
    modern_returns = compute_return_series_from_prices(prices["^SOX"])
    beta, legacy_proxy_returns = compute_beta_proxy(legacy_returns, modern_returns)
    sox_start = prices["^SOX"].dropna().index[0]
    semicon_hybrid_returns = splice_returns(legacy_proxy_returns, modern_returns, sox_start)
    semicon_hybrid_returns.loc[semicon_hybrid_returns.index >= switch_date] = compute_return_series_from_prices(
        prices["SOXX"]
    ).loc[semicon_hybrid_returns.index >= switch_date]
    semicon_hybrid_returns = semicon_hybrid_returns.rename("SEMICON_HYBRID_RETURN")

    actual_returns = compute_return_series_from_prices(prices["SOXL"])
    overlap = pd.DataFrame({"bench": semicon_hybrid_returns, "actual": actual_returns, "rate": rate}).dropna()
    financing_multiplier = calibrate_financing_multiplier(
        overlap["bench"],
        overlap["actual"],
        overlap["rate"],
        leverage=3.0,
        annual_fee=annual_fee,
    )
    modeled_returns = build_model_returns(semicon_hybrid_returns, rate, 3.0, annual_fee, financing_multiplier).rename(
        "SOXL_MODELED_RETURN"
    )
    stitched_returns, anchor_date = stitch_return_series(modeled_returns, prices["SOXL"])
    stitched_price = build_anchored_price_series(
        stitched_returns,
        anchor_date=anchor_date,
        anchor_value=float(prices["SOXL"].dropna().iloc[0]),
        output_name="SOXL_STITCHED",
    )

    diag = compare_model_to_actual(prices["SOXL"], modeled_returns)
    diag.update(
        {
            "proxy": "SOXL",
            "legacy_proxy": "FSELX",
            "modern_proxy": "^SOX/SOXX",
            "legacy_beta": beta,
            "financing_multiplier": financing_multiplier,
            "annual_fee": annual_fee,
            "history_start": stitched_price.dropna().index[0].strftime("%Y-%m-%d"),
        }
    )

    frame = pd.DataFrame(
        {
            "SOXL_RETURN": stitched_returns,
            "SOXL_PRICE": stitched_price,
        }
    )
    return frame, diag


def normalize_weights(*weights: float) -> np.ndarray:
    values = np.array(weights, dtype=float)
    if (values < 0.0).any():
        raise ValueError("Weights must be non-negative.")
    total = float(values.sum())
    if total <= 0.0:
        raise ValueError("At least one weight must be positive.")
    return values / total


def compute_metrics(returns: pd.Series) -> dict[str, float]:
    clipped = returns.clip(lower=-0.999999)
    equity = (1.0 + clipped).cumprod()
    years = len(clipped) / TRADING_DAYS_PER_YEAR
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    vol = float(clipped.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
    peak = equity.cummax()
    max_drawdown = float((equity / peak - 1.0).min())
    sharpe_like = float(cagr / vol) if vol > 0 else np.nan
    return {
        "cagr": cagr,
        "annualized_vol": vol,
        "max_drawdown": max_drawdown,
        "final_multiple": float(equity.iloc[-1]),
        "sharpe_like": sharpe_like,
    }


def simulate_strategy(
    frame: pd.DataFrame,
    signal_source: str,
    signal_window: int,
    below_weights: np.ndarray,
    above_weights: np.ndarray,
    wait_weights: np.ndarray,
    below_entry_mode: str,
    below_entry_reference_source: str,
    below_entry_drawdown_pct: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if signal_source == "underlier":
        signal_price = frame["TECH_SIGNAL_PRICE"]
    elif signal_source == "tecl":
        signal_price = frame["TECL_PRICE"]
    elif signal_source == "gspc":
        signal_price = frame["GSPC_PRICE"]
    else:
        raise ValueError(f"Unsupported signal_source: {signal_source}")

    if below_entry_reference_source == "signal":
        trigger_monitor_price = signal_price
    elif below_entry_reference_source == "tecl":
        trigger_monitor_price = frame["TECL_TRIGGER_PRICE"]
    elif below_entry_reference_source == "tqqq":
        trigger_monitor_price = frame["TQQQ_PRICE"]
    else:
        raise ValueError(f"Unsupported below_entry_reference_source: {below_entry_reference_source}")

    sim = frame.copy()
    sim["SIGNAL_PRICE"] = signal_price
    sim["TRIGGER_MONITOR_PRICE"] = trigger_monitor_price
    sim = sim.dropna(
        subset=[
            "SIGNAL_PRICE",
            "TRIGGER_MONITOR_PRICE",
            "SOXL_RETURN",
            "TECL_RETURN",
            "TQQQ_RETURN",
            "TMF_RETURN",
            "GLD_RETURN",
        ]
    ).copy()
    sim["SIGNAL_SMA"] = sim["SIGNAL_PRICE"].rolling(signal_window).mean()
    sim = sim.dropna(subset=["SIGNAL_SMA"]).copy()
    below_sma = sim["SIGNAL_PRICE"] < sim["SIGNAL_SMA"]

    asset_returns = sim[["SOXL_RETURN", "TECL_RETURN", "TQQQ_RETURN"]]
    below_return = asset_returns.to_numpy(dtype=float) @ below_weights
    above_return = asset_returns[["TECL_RETURN", "TQQQ_RETURN"]].to_numpy(dtype=float) @ above_weights
    wait_return = sim[["TMF_RETURN", "GLD_RETURN"]].to_numpy(dtype=float) @ wait_weights

    target_regime_values: list[str] = []
    trigger_reference_values: list[float] = []
    trigger_monitor_values: list[float] = []
    drawdown_trigger_values: list[bool] = []
    in_below_bucket = False
    crossunder_reference_price: float | None = None
    previous_below_sma = False

    for price, sma_value, monitor_price, is_below_sma in zip(
        sim["SIGNAL_PRICE"].to_numpy(dtype=float),
        sim["SIGNAL_SMA"].to_numpy(dtype=float),
        sim["TRIGGER_MONITOR_PRICE"].to_numpy(dtype=float),
        below_sma.to_numpy(dtype=bool),
    ):
        if not is_below_sma:
            in_below_bucket = False
            crossunder_reference_price = None
            target_regime_values.append("above")
            trigger_reference_values.append(np.nan)
            trigger_monitor_values.append(float(monitor_price))
            drawdown_trigger_values.append(False)
            previous_below_sma = False
            continue

        if not previous_below_sma or crossunder_reference_price is None:
            crossunder_reference_price = float(monitor_price)

        if below_entry_mode == "sma_drawdown":
            trigger_reference = float(sma_value)
            current_monitor_value = float(price)
        elif below_entry_mode == "crossunder_price_drawdown":
            trigger_reference = float(crossunder_reference_price)
            current_monitor_value = float(monitor_price)
        else:
            raise ValueError(f"Unsupported below_entry_mode: {below_entry_mode}")

        is_triggered = bool(current_monitor_value <= trigger_reference * (1.0 - below_entry_drawdown_pct / 100.0))

        if in_below_bucket:
            target_regime_values.append("below")
            trigger_reference_values.append(trigger_reference)
            trigger_monitor_values.append(current_monitor_value)
            drawdown_trigger_values.append(is_triggered)
            previous_below_sma = True
            continue
        if is_triggered:
            in_below_bucket = True
            target_regime_values.append("below")
            trigger_reference_values.append(trigger_reference)
            trigger_monitor_values.append(current_monitor_value)
            drawdown_trigger_values.append(is_triggered)
        else:
            target_regime_values.append("wait_mix")
            trigger_reference_values.append(trigger_reference)
            trigger_monitor_values.append(current_monitor_value)
            drawdown_trigger_values.append(is_triggered)
        previous_below_sma = True

    target_regime = pd.Series(target_regime_values, index=sim.index, name="target_regime")
    target_return = pd.Series(0.0, index=sim.index, name="target_return")
    target_return.loc[target_regime == "above"] = above_return[target_regime == "above"]
    target_return.loc[target_regime == "below"] = below_return[target_regime == "below"]
    target_return.loc[target_regime == "wait_mix"] = wait_return[target_regime == "wait_mix"]

    realized_return = target_return.shift(1).fillna(0.0)
    realized_regime = target_regime.shift(1).fillna("flat")

    if signal_source == "underlier":
        realized_signal_name = "TECH_UNDERLIER"
    elif signal_source == "tecl":
        realized_signal_name = "TECL"
    else:
        realized_signal_name = "GSPC"

    result = pd.DataFrame(
        {
            "signal_source": realized_signal_name,
            "signal_price": sim["SIGNAL_PRICE"],
            "signal_sma": sim["SIGNAL_SMA"],
            "signal_below_sma": below_sma,
            "trigger_monitor_price": trigger_monitor_values,
            "trigger_reference_price": trigger_reference_values,
            "drawdown_trigger": drawdown_trigger_values,
            "target_regime": target_regime,
            "realized_regime": realized_regime,
            "strategy_return": realized_return,
            "strategy_equity": (1.0 + realized_return).cumprod(),
            "tecl_buy_hold_return": sim["TECL_RETURN"],
            "tecl_buy_hold_equity": (1.0 + sim["TECL_RETURN"]).cumprod(),
        },
        index=sim.index,
    )
    result.index.name = "Date"

    stats = pd.DataFrame(
        [
            {
                "series": "strategy",
                **compute_metrics(result["strategy_return"].iloc[1:]),
                "trade_count": int((result["realized_regime"] != result["realized_regime"].shift(1)).sum() - 1),
                "below_regime_share": float((result["realized_regime"] == "below").mean()),
                "wait_regime_share": float((result["realized_regime"] == "wait_mix").mean()),
            },
            {
                "series": "tecl_buy_hold",
                **compute_metrics(result["tecl_buy_hold_return"].iloc[1:]),
                "trade_count": 0,
                "below_regime_share": np.nan,
                "wait_regime_share": np.nan,
            },
        ]
    )
    return result, stats


def run_drawdown_grid(
    frame: pd.DataFrame,
    signal_source: str,
    signal_window: int,
    below_weights: np.ndarray,
    above_weights: np.ndarray,
    wait_weights: np.ndarray,
    below_entry_mode: str,
    below_entry_reference_source: str,
    drawdown_values: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for drawdown_pct in drawdown_values:
        _, stats = simulate_strategy(
            frame=frame,
            signal_source=signal_source,
            signal_window=signal_window,
            below_weights=below_weights,
            above_weights=above_weights,
            wait_weights=wait_weights,
            below_entry_mode=below_entry_mode,
            below_entry_reference_source=below_entry_reference_source,
            below_entry_drawdown_pct=float(drawdown_pct),
        )
        strategy_row = stats[stats["series"] == "strategy"].iloc[0].to_dict()
        strategy_row["below_entry_drawdown_pct"] = float(drawdown_pct)
        rows.append(strategy_row)
    result = pd.DataFrame(rows)
    result = result.sort_values("below_entry_drawdown_pct").reset_index(drop=True)
    return result


def save_log_equity_plot(result: pd.DataFrame, output_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    ax.plot(result.index, result["strategy_equity"], linewidth=2.0, label="Strategy")
    ax.plot(result.index, result["tecl_buy_hold_equity"], linewidth=1.8, label="TECL Buy & Hold")
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_ylabel("Equity (log scale)")
    ax.legend()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_drawdown_optimization_plot(grid: pd.DataFrame, output_path: Path, title: str) -> None:
    fig, ax1 = plt.subplots(figsize=(12, 7), constrained_layout=True)
    ax1.plot(grid["below_entry_drawdown_pct"], grid["cagr"] * 100.0, color="#1565C0", linewidth=2.0, label="CAGR")
    ax1.set_xlabel("Below-SMA Entry Trigger (%)")
    ax1.set_ylabel("CAGR (%)", color="#1565C0")
    ax1.tick_params(axis="y", labelcolor="#1565C0")
    ax1.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)

    ax2 = ax1.twinx()
    ax2.plot(
        grid["below_entry_drawdown_pct"],
        grid["max_drawdown"] * 100.0,
        color="#C62828",
        linewidth=1.6,
        linestyle="--",
        label="Max Drawdown",
    )
    ax2.set_ylabel("Max Drawdown (%)", color="#C62828")
    ax2.tick_params(axis="y", labelcolor="#C62828")

    best = grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).iloc[0]
    ax1.scatter(best["below_entry_drawdown_pct"], best["cagr"] * 100.0, color="#1565C0", s=90, zorder=5)
    ax1.annotate(
        f"best n={best['below_entry_drawdown_pct']:.1f}%\nCAGR={best['cagr'] * 100.0:.2f}%",
        (best["below_entry_drawdown_pct"], best["cagr"] * 100.0),
        textcoords="offset points",
        xytext=(12, 10),
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.85, "edgecolor": "#999999"},
    )

    fig.suptitle(title)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-start", default=DEFAULT_FETCH_START)
    parser.add_argument("--fetch-end", default=None)
    parser.add_argument("--backtest-start", default=DEFAULT_BACKTEST_START)
    parser.add_argument("--signal-source", choices=["underlier", "tecl", "gspc"], default=DEFAULT_SIGNAL_SOURCE)
    parser.add_argument("--signal-window", type=int, default=DEFAULT_SIGNAL_WINDOW)
    parser.add_argument("--below-soxl", type=float, default=100.0)
    parser.add_argument("--below-tecl", type=float, default=0.0)
    parser.add_argument("--below-tqqq", type=float, default=0.0)
    parser.add_argument("--above-tecl", type=float, default=100.0)
    parser.add_argument("--above-tqqq", type=float, default=0.0)
    parser.add_argument("--wait-tmf", type=float, default=DEFAULT_WAIT_TMF)
    parser.add_argument("--wait-gld", type=float, default=DEFAULT_WAIT_GLD)
    parser.add_argument("--tecl-annual-fee", type=float, default=DEFAULT_TECL_ANNUAL_FEE)
    parser.add_argument("--soxl-annual-fee", type=float, default=DEFAULT_SOXL_ANNUAL_FEE)
    parser.add_argument(
        "--below-entry-mode",
        choices=["sma_drawdown", "crossunder_price_drawdown"],
        default=DEFAULT_BELOW_ENTRY_MODE,
    )
    parser.add_argument(
        "--below-entry-reference-source",
        choices=["signal", "tecl", "tqqq"],
        default=DEFAULT_BELOW_ENTRY_REFERENCE_SOURCE,
    )
    parser.add_argument("--below-entry-drawdown-pct", type=float, default=0.0)
    parser.add_argument("--optimize-below-entry-drawdown", action="store_true")
    parser.add_argument("--drawdown-min", type=float, default=DEFAULT_DRAWDOWN_MIN)
    parser.add_argument("--drawdown-max", type=float, default=DEFAULT_DRAWDOWN_MAX)
    parser.add_argument("--drawdown-step", type=float, default=DEFAULT_DRAWDOWN_STEP)
    return parser.parse_args()


def build_output_stem(args: argparse.Namespace) -> str:
    start = args.backtest_start.replace("-", "")
    return (
        f"tecl_sma{args.signal_window}_{args.signal_source}"
        f"_above_tecl{int(args.above_tecl)}_tqqq{int(args.above_tqqq)}"
        f"_wait_tmf{int(args.wait_tmf)}_gld{int(args.wait_gld)}"
        f"_below_soxl{int(args.below_soxl)}_tecl{int(args.below_tecl)}_tqqq{int(args.below_tqqq)}"
        f"_{args.below_entry_mode}"
        f"_ref_{args.below_entry_reference_source}"
        f"_enterdown_{str(args.below_entry_drawdown_pct).replace('.', 'p')}"
        f"_from_{start}"
    )


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = download_adj_close(
        ["TECL", "XLK", "FSPTX", "SOXL", "^SOX", "SOXX", "FSELX", "^GSPC", "GLD", DEFAULT_GLD_PROXY_TICKER],
        start=args.fetch_start,
        end=args.fetch_end,
    )
    rate = download_fred_series(DEFAULT_RATE_SERIES_ID).reindex(prices.index).ffill().bfill()

    tecl_frame, tecl_diag = build_tecl_series(prices, rate, annual_fee=args.tecl_annual_fee)
    soxl_frame, soxl_diag = build_soxl_series(
        prices,
        rate,
        annual_fee=args.soxl_annual_fee,
        switch_date=pd.Timestamp(DEFAULT_SWITCH_DATE),
    )
    tqqq_frame = load_canonical_tqqq()
    tmf_frame = load_canonical_tmf()
    gld_frame, gld_diag = build_gld_series(prices)

    frame = pd.concat([tecl_frame, soxl_frame, tqqq_frame, tmf_frame, gld_frame], axis=1).sort_index()
    frame["GSPC_PRICE"] = prices["^GSPC"]
    frame = frame.loc[pd.Timestamp(args.backtest_start) :].copy()

    below_weights = normalize_weights(args.below_soxl, args.below_tecl, args.below_tqqq)
    above_weights = normalize_weights(args.above_tecl, args.above_tqqq)
    wait_weights = normalize_weights(args.wait_tmf, args.wait_gld)
    diagnostics = pd.DataFrame([tecl_diag, soxl_diag, gld_diag])

    if args.optimize_below_entry_drawdown:
        drawdown_values = np.round(
            np.arange(args.drawdown_min, args.drawdown_max + (args.drawdown_step / 2.0), args.drawdown_step),
            10,
        )
        grid = run_drawdown_grid(
            frame=frame,
            signal_source=args.signal_source,
            signal_window=args.signal_window,
            below_weights=below_weights,
            above_weights=above_weights,
            wait_weights=wait_weights,
            below_entry_mode=args.below_entry_mode,
            below_entry_reference_source=args.below_entry_reference_source,
            drawdown_values=drawdown_values,
        )
        best = grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).iloc[0]
        args.below_entry_drawdown_pct = float(best["below_entry_drawdown_pct"])

        result, stats = simulate_strategy(
            frame=frame,
            signal_source=args.signal_source,
            signal_window=args.signal_window,
            below_weights=below_weights,
            above_weights=above_weights,
            wait_weights=wait_weights,
            below_entry_mode=args.below_entry_mode,
            below_entry_reference_source=args.below_entry_reference_source,
            below_entry_drawdown_pct=args.below_entry_drawdown_pct,
        )

        stem = build_output_stem(args)
        daily_path = OUTPUT_DIR / f"{stem}_daily_path.csv"
        summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
        plot_path = OUTPUT_DIR / f"{stem}_log_equity.png"
        diag_path = OUTPUT_DIR / f"{stem}_proxy_diagnostics.csv"
        grid_path = OUTPUT_DIR / f"{stem}_drawdown_optimization.csv"
        grid_plot_path = OUTPUT_DIR / f"{stem}_drawdown_optimization.png"

        result.to_csv(daily_path)
        stats.insert(1, "start_date", result.index[0].strftime("%Y-%m-%d"))
        stats.insert(2, "end_date", result.index[-1].strftime("%Y-%m-%d"))
        stats.to_csv(summary_path, index=False)
        diagnostics.to_csv(diag_path, index=False)
        grid.to_csv(grid_path, index=False)

        title = (
            f"TECL SMA{args.signal_window} Rotation"
            f" | signal={args.signal_source}"
            f" | above TECL/TQQQ={args.above_tecl}:{args.above_tqqq}"
            f" | wait TMF/GLD={args.wait_tmf}:{args.wait_gld}"
            f" | below SOXL/TECL/TQQQ={args.below_soxl}:{args.below_tecl}:{args.below_tqqq}"
            f" | enter={args.below_entry_drawdown_pct:.1f}% below ref"
        )
        save_log_equity_plot(result, plot_path, title=title)
        save_drawdown_optimization_plot(
            grid=grid,
            output_path=grid_plot_path,
            title=(
                f"Below-SMA Entry Optimization"
                f" | signal={args.signal_source}"
                f" | mode={args.below_entry_mode}"
                f" | ref={args.below_entry_reference_source}"
                f" | wait TMF/GLD={args.wait_tmf}:{args.wait_gld}"
                f" | below SOXL/TECL/TQQQ={args.below_soxl}:{args.below_tecl}:{args.below_tqqq}"
            ),
        )

        print("Optimization complete.")
        print(f"Best below-SMA entry trigger: {args.below_entry_drawdown_pct:.1f}%")
        print(stats.to_string(index=False))
        print(f"Daily path: {daily_path}")
        print(f"Summary: {summary_path}")
        print(f"Plot: {plot_path}")
        print(f"Optimization grid: {grid_path}")
        print(f"Optimization plot: {grid_plot_path}")
        print(f"Diagnostics: {diag_path}")
        return

    result, stats = simulate_strategy(
        frame=frame,
        signal_source=args.signal_source,
        signal_window=args.signal_window,
        below_weights=below_weights,
        above_weights=above_weights,
        wait_weights=wait_weights,
        below_entry_mode=args.below_entry_mode,
        below_entry_reference_source=args.below_entry_reference_source,
        below_entry_drawdown_pct=args.below_entry_drawdown_pct,
    )

    stem = build_output_stem(args)
    daily_path = OUTPUT_DIR / f"{stem}_daily_path.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    plot_path = OUTPUT_DIR / f"{stem}_log_equity.png"
    diag_path = OUTPUT_DIR / f"{stem}_proxy_diagnostics.csv"

    result.to_csv(daily_path)
    stats.insert(1, "start_date", result.index[0].strftime("%Y-%m-%d"))
    stats.insert(2, "end_date", result.index[-1].strftime("%Y-%m-%d"))
    stats.to_csv(summary_path, index=False)
    diagnostics.to_csv(diag_path, index=False)

    title = (
        f"TECL SMA{args.signal_window} Rotation"
        f" | signal={args.signal_source}"
        f" | mode={args.below_entry_mode}"
        f" | ref={args.below_entry_reference_source}"
        f" | above TECL/TQQQ={args.above_tecl}:{args.above_tqqq}"
        f" | wait TMF/GLD={args.wait_tmf}:{args.wait_gld}"
        f" | below SOXL/TECL/TQQQ={args.below_soxl}:{args.below_tecl}:{args.below_tqqq}"
        f" | enter={args.below_entry_drawdown_pct:.1f}% below ref"
    )
    save_log_equity_plot(result, plot_path, title=title)

    print("Simulation complete.")
    print(stats.to_string(index=False))
    print(f"Daily path: {daily_path}")
    print(f"Summary: {summary_path}")
    print(f"Plot: {plot_path}")
    print(f"Diagnostics: {diag_path}")


if __name__ == "__main__":
    main()
