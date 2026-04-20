from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


DEFAULT_FETCH_START = "2009-01-01"
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LONGVOL_HISTORY_URL = "https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/_LONGVOL.json"
TRADING_DAYS_PER_YEAR = 252
UVIX_TARGET_LEVERAGE = 2.0
UVIX_ANNUAL_FEE = 0.0165


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    vol_return_col: str
    vol_label: str


BASE_DATASETS = [
    DatasetConfig(name="strict_uvix", vol_return_col="UVIX_RETURN", vol_label="UVIX"),
    DatasetConfig(
        name="synthetic_uvix_longvol_2x",
        vol_return_col="UVIX_LONGVOL_2X_SYNTH_RETURN",
        vol_label="UVIX_LONGVOL_2X_SYNTH",
    ),
    DatasetConfig(
        name="stitched_uvix_longvol_2x",
        vol_return_col="UVIX_LONGVOL_2X_STITCHED_RETURN",
        vol_label="UVIX_LONGVOL_2X_STITCHED",
    ),
]
UVXY_DATASET = DatasetConfig(name="proxy_uvxy", vol_return_col="UVXY_RETURN", vol_label="UVXY")


DEFAULT_ENTRY_MIN = 55.0
DEFAULT_ENTRY_MAX = 95.0
DEFAULT_EXIT_MIN = 45.0
DEFAULT_EXIT_MAX = 90.0
DEFAULT_ENTRY_STEP = 0.5
DEFAULT_EXIT_STEP = 0.5

LOW_RSI_ENTRY = 30.5
LOW_RSI_EXIT = 33.5
SMA_ENTER_MULT = 1.04
SMA_EXIT_MULT = 0.96


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
    close = close.sort_index()
    return close


def download_longvol_index() -> pd.Series:
    response = requests.get(LONGVOL_HISTORY_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    data = payload["data"]
    frame = pd.DataFrame(data, columns=["date", "close"]).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    series = frame.set_index("date")["close"].dropna().sort_index()
    series.name = "LONGVOL"
    return series


def build_daily_reset_leveraged_series(
    underlier: pd.Series,
    leverage: float,
    annual_fee: float,
    output_name: str,
    base_value: float = 100.0,
) -> pd.Series:
    daily_fee_drag = annual_fee / TRADING_DAYS_PER_YEAR
    underlier_ret = underlier.pct_change()
    leveraged_ret = leverage * underlier_ret - daily_fee_drag
    leveraged_ret = leveraged_ret.clip(lower=-0.999999)
    leveraged_ret.iloc[0] = 0.0
    synthetic = (1.0 + leveraged_ret).cumprod() * base_value
    synthetic.name = output_name
    return synthetic


def compute_return_series_from_prices(series: pd.Series, output_name: str) -> pd.Series:
    valid_prices = series.dropna()
    returns = valid_prices.pct_change().fillna(0.0).reindex(series.index)
    returns.name = output_name
    return returns


def build_daily_reset_leveraged_returns(
    underlier: pd.Series,
    leverage: float,
    annual_fee: float,
    output_name: str,
) -> pd.Series:
    daily_fee_drag = annual_fee / TRADING_DAYS_PER_YEAR
    leveraged_returns = leverage * underlier.pct_change() - daily_fee_drag
    leveraged_returns = leveraged_returns.clip(lower=-0.999999).fillna(0.0)
    leveraged_returns.name = output_name
    return leveraged_returns


def stitch_return_series(
    synthetic_returns: pd.Series,
    actual_prices: pd.Series,
    output_name: str,
) -> pd.Series:
    actual_prices = actual_prices.dropna().copy()
    actual_returns = actual_prices.pct_change()
    stitched_returns = synthetic_returns.copy()
    first_actual_return_date = actual_returns.first_valid_index()
    if first_actual_return_date is not None:
        stitched_returns.loc[first_actual_return_date:] = actual_returns.loc[first_actual_return_date:]
    stitched_returns = stitched_returns.fillna(0.0)
    stitched_returns.name = output_name
    return stitched_returns


def compare_proxy_to_actual(actual: pd.Series, proxy: pd.Series) -> dict[str, float]:
    compare = pd.DataFrame({"actual": actual, "proxy": proxy}).dropna()
    returns = compare.pct_change().dropna()
    return {
        "overlap_start": compare.index[0].strftime("%Y-%m-%d"),
        "overlap_end": compare.index[-1].strftime("%Y-%m-%d"),
        "days": len(compare),
        "daily_return_corr": returns["actual"].corr(returns["proxy"]),
        "daily_return_mae_bps": (returns["actual"] - returns["proxy"]).abs().mean() * 10000.0,
        "actual_final_multiple": compare["actual"].iloc[-1] / compare["actual"].iloc[0],
        "proxy_final_multiple": compare["proxy"].iloc[-1] / compare["proxy"].iloc[0],
    }


def compare_proxy_returns_to_actual(actual_prices: pd.Series, proxy_returns: pd.Series) -> dict[str, float]:
    actual_returns = actual_prices.dropna().pct_change()
    compare = pd.DataFrame({"actual": actual_returns, "proxy": proxy_returns}).dropna()
    actual_growth = float(np.exp(np.log1p(compare["actual"]).sum()))
    proxy_growth = float(np.exp(np.log1p(compare["proxy"]).sum()))
    return {
        "overlap_start": compare.index[0].strftime("%Y-%m-%d"),
        "overlap_end": compare.index[-1].strftime("%Y-%m-%d"),
        "days": len(compare),
        "daily_return_corr": compare["actual"].corr(compare["proxy"]),
        "daily_return_mae_bps": (compare["actual"] - compare["proxy"]).abs().mean() * 10000.0,
        "actual_final_multiple": actual_growth,
        "proxy_final_multiple": proxy_growth,
    }


def enrich_with_volatility_series(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    longvol = download_longvol_index()
    uvix_synth = build_daily_reset_leveraged_series(
        longvol,
        leverage=UVIX_TARGET_LEVERAGE,
        annual_fee=UVIX_ANNUAL_FEE,
        output_name="UVIX_LONGVOL_2X_SYNTH",
    )
    uvix_return = compute_return_series_from_prices(prices["UVIX"], "UVIX_RETURN")
    uvxy_return = compute_return_series_from_prices(prices["UVXY"], "UVXY_RETURN")
    uvix_synth_return = build_daily_reset_leveraged_returns(
        longvol,
        leverage=UVIX_TARGET_LEVERAGE,
        annual_fee=UVIX_ANNUAL_FEE,
        output_name="UVIX_LONGVOL_2X_SYNTH_RETURN",
    )
    uvix_stitched_return = stitch_return_series(
        uvix_synth_return,
        prices["UVIX"],
        "UVIX_LONGVOL_2X_STITCHED_RETURN",
    )

    enriched = prices.copy()
    enriched = enriched.join(longvol, how="left")
    enriched = enriched.join(uvix_synth, how="left")
    enriched = enriched.join(uvix_return, how="left")
    enriched = enriched.join(uvxy_return, how="left")
    enriched = enriched.join(uvix_synth_return, how="left")
    enriched = enriched.join(uvix_stitched_return, how="left")

    proxy_compare = pd.DataFrame(
        [
            compare_proxy_to_actual(prices["UVIX"], uvix_synth),
            compare_proxy_returns_to_actual(prices["UVIX"], uvix_stitched_return),
        ],
        index=["uvix_vs_synth_longvol_2x", "uvix_vs_return_stitched_longvol_2x"],
    ).reset_index(names="comparison")
    return enriched, proxy_compare


def build_datasets(include_uvxy: bool) -> list[DatasetConfig]:
    datasets = list(BASE_DATASETS)
    if include_uvxy:
        datasets.append(UVXY_DATASET)
    return datasets


def compute_rsi_wilder(series: pd.Series, lookback: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / lookback, adjust=False, min_periods=lookback).mean()
    avg_loss = loss.ewm(alpha=1 / lookback, adjust=False, min_periods=lookback).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    both_zero = (avg_gain == 0) & (avg_loss == 0)
    rsi = rsi.mask(avg_loss == 0, 100.0)
    rsi = rsi.mask(avg_gain == 0, 0.0)
    rsi = rsi.mask(both_zero, 50.0)
    return rsi


def hysteresis_lt(values: np.ndarray, enter_level: float, exit_level: float) -> np.ndarray:
    state = False
    out = np.zeros(len(values), dtype=bool)
    for i, value in enumerate(values):
        if not np.isnan(value):
            if not state and value < enter_level:
                state = True
            elif state and value > exit_level:
                state = False
        out[i] = state
    return out


def hysteresis_sma(price: np.ndarray, sma: np.ndarray) -> np.ndarray:
    state = False
    out = np.zeros(len(price), dtype=bool)
    for i, (px, avg) in enumerate(zip(price, sma)):
        if not (np.isnan(px) or np.isnan(avg)):
            if not state and px > avg * SMA_ENTER_MULT:
                state = True
            elif state and px < avg * SMA_EXIT_MULT:
                state = False
        out[i] = state
    return out


def build_frame(config: DatasetConfig, prices: pd.DataFrame) -> pd.DataFrame:
    needed = ["SPY", "SOXL", "TQQQ", "UGL", "TMF", config.vol_return_col]
    frame = prices[needed].copy()
    frame["SPY_RSI_14"] = compute_rsi_wilder(prices["SPY"], 14)
    frame["SPY_SMA_160"] = prices["SPY"].rolling(160).mean()
    frame = frame.dropna().copy()
    return frame


def filter_frame(frame: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start is not None:
        frame = frame.loc[pd.Timestamp(start) :]
    if end is not None:
        frame = frame.loc[: pd.Timestamp(end)]
    return frame.copy()


def build_threshold_grid(
    entry_min: float,
    entry_max: float,
    exit_min: float,
    exit_max: float,
    entry_step: float,
    exit_step: float,
) -> tuple[np.ndarray, np.ndarray]:
    entry_values = np.round(np.arange(entry_min, entry_max + (entry_step / 2.0), entry_step), 10)
    exit_values = np.round(np.arange(exit_min, exit_max + (exit_step / 2.0), exit_step), 10)
    entry_grid, exit_grid = np.meshgrid(entry_values, exit_values, indexing="ij")
    valid = exit_grid <= entry_grid
    return entry_grid[valid], exit_grid[valid]


def compute_strategy_stats(frame: pd.DataFrame, entry_level: float, exit_level: float, vol_return_col: str) -> dict[str, float]:
    spy = frame["SPY"].to_numpy(dtype=float)
    rsi = frame["SPY_RSI_14"].to_numpy(dtype=float)
    sma = frame["SPY_SMA_160"].to_numpy(dtype=float)

    returns = frame[["SOXL", "TQQQ", "UGL", "TMF"]].pct_change().fillna(0.0)
    ret_vol = frame[vol_return_col].to_numpy(dtype=float)
    ret_soxl = returns["SOXL"].to_numpy(dtype=float)
    ret_tqqq = returns["TQQQ"].to_numpy(dtype=float)
    ret_def = (0.5 * returns["UGL"] + 0.5 * returns["TMF"]).to_numpy(dtype=float)

    low_state = hysteresis_lt(rsi, LOW_RSI_ENTRY, LOW_RSI_EXIT)
    trend_state = hysteresis_sma(spy, sma)

    high_state = False
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    held_code = -1
    trade_count = 0
    vol_days = 0

    for i in range(len(frame)):
        if i > 0 and held_code >= 0:
            if held_code == 0:
                equity *= 1.0 + ret_vol[i]
            elif held_code == 1:
                equity *= 1.0 + ret_soxl[i]
            elif held_code == 2:
                equity *= 1.0 + ret_tqqq[i]
            else:
                equity *= 1.0 + ret_def[i]
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1.0)

        value = rsi[i]
        if not np.isnan(value):
            if not high_state and value > entry_level:
                high_state = True
            elif high_state and value < exit_level:
                high_state = False

        if high_state:
            next_code = 0
            vol_days += 1
        elif low_state[i]:
            next_code = 1
        elif trend_state[i]:
            next_code = 2
        else:
            next_code = 3

        if held_code != -1 and next_code != held_code:
            trade_count += 1
        held_code = next_code

    start_date = frame.index[0]
    end_date = frame.index[-1]
    years = (end_date - start_date).days / 365.25
    cagr = equity ** (1.0 / years) - 1.0 if years > 0 else np.nan
    return {
        "entry": entry_level,
        "exit": exit_level,
        "cagr": cagr,
        "final_multiple": equity,
        "max_drawdown": max_drawdown,
        "trade_count": trade_count,
        "vol_days": vol_days,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }


def run_grid(frame: pd.DataFrame, config: DatasetConfig, entries: np.ndarray, exits: np.ndarray) -> pd.DataFrame:
    spy = frame["SPY"].to_numpy(dtype=float)
    rsi = frame["SPY_RSI_14"].to_numpy(dtype=float)
    sma = frame["SPY_SMA_160"].to_numpy(dtype=float)

    returns = frame[["SOXL", "TQQQ", "UGL", "TMF"]].pct_change().fillna(0.0)
    ret_vol = frame[config.vol_return_col].to_numpy(dtype=float)
    ret_soxl = returns["SOXL"].to_numpy(dtype=float)
    ret_tqqq = returns["TQQQ"].to_numpy(dtype=float)
    ret_def = (0.5 * returns["UGL"] + 0.5 * returns["TMF"]).to_numpy(dtype=float)

    low_state = hysteresis_lt(rsi, LOW_RSI_ENTRY, LOW_RSI_EXIT)
    trend_state = hysteresis_sma(spy, sma)
    fallback_codes = np.where(low_state, 1, np.where(trend_state, 2, 3)).astype(np.int8)

    count = len(entries)
    high_state = np.zeros(count, dtype=bool)
    equity = np.ones(count, dtype=float)
    peak = np.ones(count, dtype=float)
    max_drawdown = np.zeros(count, dtype=float)
    held_code = np.full(count, -1, dtype=np.int8)
    trade_count = np.zeros(count, dtype=np.int32)
    vol_days = np.zeros(count, dtype=np.int32)

    for i, value in enumerate(rsi):
        if i > 0:
            vol_mask = held_code == 0
            soxl_mask = held_code == 1
            tqqq_mask = held_code == 2
            def_mask = held_code == 3

            equity[vol_mask] *= 1.0 + ret_vol[i]
            equity[soxl_mask] *= 1.0 + ret_soxl[i]
            equity[tqqq_mask] *= 1.0 + ret_tqqq[i]
            equity[def_mask] *= 1.0 + ret_def[i]

            peak = np.maximum(peak, equity)
            max_drawdown = np.minimum(max_drawdown, equity / peak - 1.0)

        if not np.isnan(value):
            enter_mask = (~high_state) & (value > entries)
            exit_mask = high_state & (value < exits)
            high_state[enter_mask] = True
            high_state[exit_mask] = False

        next_code = np.full(count, fallback_codes[i], dtype=np.int8)
        next_code[high_state] = 0

        trade_count += ((held_code != -1) & (next_code != held_code)).astype(np.int32)
        vol_days += high_state.astype(np.int32)
        held_code = next_code

    start_date = frame.index[0]
    end_date = frame.index[-1]
    years = (end_date - start_date).days / 365.25
    cagr = np.power(equity, 1.0 / years) - 1.0 if years > 0 else np.full(count, np.nan)

    result = pd.DataFrame(
        {
            "entry": entries,
            "exit": exits,
            "cagr": cagr,
            "final_multiple": equity,
            "max_drawdown": max_drawdown,
            "trade_count": trade_count,
            "vol_days": vol_days,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }
    )
    result = result.sort_values(["cagr", "final_multiple"], ascending=[False, False]).reset_index(drop=True)
    return result


def summarize(config: DatasetConfig, frame: pd.DataFrame, results: pd.DataFrame, output_suffix: str) -> pd.DataFrame:
    baseline = compute_strategy_stats(frame, 71.0, 68.0, config.vol_return_col)
    baseline_row = pd.DataFrame([baseline])
    baseline_row.insert(0, "dataset", config.name)
    baseline_row.insert(1, "vol_label", config.vol_label)
    top = results.head(10).copy()
    top.insert(0, "dataset", config.name)
    top.insert(1, "vol_label", config.vol_label)
    baseline_path = OUTPUT_DIR / f"{config.name}_baseline_71_68{output_suffix}.csv"
    top_path = OUTPUT_DIR / f"{config.name}_top10{output_suffix}.csv"
    full_path = OUTPUT_DIR / f"{config.name}_full_grid{output_suffix}.csv"
    baseline_row.to_csv(baseline_path, index=False)
    top.to_csv(top_path, index=False)
    results.to_csv(full_path, index=False)
    return baseline_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch-start",
        default=DEFAULT_FETCH_START,
        help="Market data download start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--fetch-end",
        default=None,
        help="Optional market data download end date in YYYY-MM-DD format. Omit for latest available data.",
    )
    parser.add_argument(
        "--backtest-start",
        default=None,
        help="Optional backtest start date in YYYY-MM-DD format after indicators are computed.",
    )
    parser.add_argument(
        "--backtest-end",
        default=None,
        help="Optional backtest end date in YYYY-MM-DD format after indicators are computed.",
    )
    parser.add_argument(
        "--entry-step",
        type=float,
        default=DEFAULT_ENTRY_STEP,
        help="Grid step for the high RSI entry threshold.",
    )
    parser.add_argument(
        "--exit-step",
        type=float,
        default=DEFAULT_EXIT_STEP,
        help="Grid step for the high RSI exit threshold.",
    )
    parser.add_argument(
        "--include-uvxy",
        action="store_true",
        help="Also run the legacy UVXY comparison dataset.",
    )
    return parser.parse_args()


def format_step_for_suffix(step: float) -> str:
    return str(step).replace(".", "p")


def build_output_suffix(
    backtest_start: str | None,
    backtest_end: str | None,
    entry_step: float,
    exit_step: float,
) -> str:
    parts: list[str] = []
    if backtest_start is not None:
        parts.append(f"from_{backtest_start.replace('-', '')}")
    if backtest_end is not None:
        parts.append(f"to_{backtest_end.replace('-', '')}")
    parts.append(f"entrystep_{format_step_for_suffix(entry_step)}")
    parts.append(f"exitstep_{format_step_for_suffix(exit_step)}")
    return f"_{'_'.join(parts)}" if parts else ""


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    market_tickers = sorted({"SPY", "SOXL", "TQQQ", "UGL", "TMF", "UVIX", "UVXY"})
    prices = download_adj_close(market_tickers, start=args.fetch_start, end=args.fetch_end)
    prices, proxy_compare = enrich_with_volatility_series(prices)
    datasets = build_datasets(include_uvxy=args.include_uvxy)
    output_suffix = build_output_suffix(
        args.backtest_start,
        args.backtest_end,
        args.entry_step,
        args.exit_step,
    )
    entries, exits = build_threshold_grid(
        entry_min=DEFAULT_ENTRY_MIN,
        entry_max=DEFAULT_ENTRY_MAX,
        exit_min=DEFAULT_EXIT_MIN,
        exit_max=DEFAULT_EXIT_MAX,
        entry_step=args.entry_step,
        exit_step=args.exit_step,
    )

    overview_rows = []
    baseline_rows = []

    for config in datasets:
        frame = build_frame(config, prices)
        frame = filter_frame(frame, start=args.backtest_start, end=args.backtest_end)
        results = run_grid(frame, config, entries=entries, exits=exits)
        baseline = summarize(config, frame, results, output_suffix=output_suffix)
        best = results.iloc[0]
        overview_rows.append(
            {
                "dataset": config.name,
                "vol_label": config.vol_label,
                "start_date": frame.index[0].strftime("%Y-%m-%d"),
                "end_date": frame.index[-1].strftime("%Y-%m-%d"),
                "days": len(frame),
                "best_entry": best["entry"],
                "best_exit": best["exit"],
                "best_cagr": best["cagr"],
                "best_final_multiple": best["final_multiple"],
                "best_max_drawdown": best["max_drawdown"],
                "best_trade_count": best["trade_count"],
                "best_vol_days": best["vol_days"],
            }
        )
        baseline_rows.append(baseline)

    overview = pd.DataFrame(overview_rows)
    overview.to_csv(OUTPUT_DIR / f"rsi_entry_exit_optimization_overview{output_suffix}.csv", index=False)

    baseline_compare = pd.concat(baseline_rows, ignore_index=True)
    baseline_compare.to_csv(OUTPUT_DIR / f"rsi_entry_exit_baseline_compare{output_suffix}.csv", index=False)

    proxy_compare.to_csv(OUTPUT_DIR / "uvix_proxy_alignment.csv", index=False)

    print("Optimization complete.")
    print(overview.to_string(index=False))
    print("\nBaseline 71/68")
    print(baseline_compare.to_string(index=False))
    print("\nUVIX proxy alignment")
    print(proxy_compare.to_string(index=False))


if __name__ == "__main__":
    main()
