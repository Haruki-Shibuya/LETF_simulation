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
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS_PER_YEAR = 252
DEFAULT_FETCH_START = "1990-01-01"
DEFAULT_HISTORY_START = "1991-01-01"
DEFAULT_LEVERAGE = 3.0
DEFAULT_ANNUAL_FEE = 0.0082
DEFAULT_BENCHMARK_TICKER = "^NDX"
DEFAULT_LETF_TICKER = "TQQQ"
DEFAULT_RATE_SERIES_ID = "DGS3MO"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    financing_multiplier: float
    label: str


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


def download_fred_series(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    frame.columns = ["date", series_id]
    frame["date"] = pd.to_datetime(frame["date"])
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce") / 100.0
    series = frame.set_index("date")[series_id].sort_index()
    series.name = series_id
    return series


def compute_return_series_from_prices(series: pd.Series, output_name: str) -> pd.Series:
    valid = series.dropna()
    returns = valid.pct_change().fillna(0.0).reindex(series.index)
    returns.name = output_name
    return returns


def build_model_returns(
    benchmark_returns: pd.Series,
    financing_rate: pd.Series,
    leverage: float,
    annual_fee: float,
    financing_multiplier: float,
    output_name: str,
) -> pd.Series:
    daily_fee_drag = annual_fee / TRADING_DAYS_PER_YEAR
    daily_financing_drag = financing_multiplier * financing_rate / TRADING_DAYS_PER_YEAR
    modeled = leverage * benchmark_returns - daily_fee_drag - daily_financing_drag
    modeled = modeled.clip(lower=-0.999999).fillna(0.0)
    modeled.name = output_name
    return modeled


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
        output_name="MODELED_RETURN",
    )
    return float(np.log1p(modeled).sum() - np.log1p(actual_returns).sum())


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

    while low_gap * high_gap > 0 and high < 32.0:
        high *= 2.0
        high_gap = cumulative_log_gap(high, benchmark_returns, actual_returns, financing_rate, leverage, annual_fee)

    if low_gap == 0:
        return low
    if high_gap == 0:
        return high

    if low_gap * high_gap > 0:
        candidates = np.arange(0.0, 32.01, 0.01)
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


def stitch_return_series(
    synthetic_returns: pd.Series,
    actual_prices: pd.Series,
    output_name: str,
) -> tuple[pd.Series, pd.Timestamp]:
    actual_prices = actual_prices.dropna()
    actual_returns = actual_prices.pct_change()
    stitched = synthetic_returns.copy()
    first_actual_return_date = actual_returns.first_valid_index()
    if first_actual_return_date is not None:
        stitched.loc[first_actual_return_date:] = actual_returns.loc[first_actual_return_date:]
    stitched = stitched.fillna(0.0)
    stitched.name = output_name
    return stitched, actual_prices.index[0]


def compare_model_to_actual(
    actual_prices: pd.Series,
    synthetic_returns: pd.Series,
    stitched_prices: pd.Series,
    model_name: str,
    financing_multiplier: float,
    annual_fee: float,
) -> dict[str, float]:
    actual_returns = actual_prices.dropna().pct_change()
    overlap = pd.DataFrame({"actual": actual_returns, "synthetic": synthetic_returns}).dropna()
    actual_growth = float(np.exp(np.log1p(overlap["actual"]).sum()))
    synthetic_growth = float(np.exp(np.log1p(overlap["synthetic"]).sum()))

    actual_first_date = actual_prices.dropna().index[0]
    actual_last_date = actual_prices.dropna().index[-1]
    stitched_window = stitched_prices.loc[actual_first_date:actual_last_date].dropna()

    return {
        "model": model_name,
        "annual_fee": annual_fee,
        "financing_multiplier": financing_multiplier,
        "overlap_start": overlap.index[0].strftime("%Y-%m-%d"),
        "overlap_end": overlap.index[-1].strftime("%Y-%m-%d"),
        "overlap_days": len(overlap),
        "daily_return_corr": overlap["actual"].corr(overlap["synthetic"]),
        "daily_return_mae_bps": (overlap["actual"] - overlap["synthetic"]).abs().mean() * 10000.0,
        "overlap_actual_growth_multiple": actual_growth,
        "overlap_synthetic_growth_multiple": synthetic_growth,
        "overlap_log_return_gap": float(np.log1p(overlap["synthetic"]).sum() - np.log1p(overlap["actual"]).sum()),
        "anchor_date": actual_first_date.strftime("%Y-%m-%d"),
        "anchor_price": float(actual_prices.dropna().iloc[0]),
        "actual_final_price": float(actual_prices.dropna().iloc[-1]),
        "stitched_final_price": float(stitched_window.iloc[-1]),
    }


def build_normalized_overlap_frame(
    actual_prices: pd.Series,
    modeled_prices: dict[str, pd.Series],
) -> pd.DataFrame:
    overlap_start = actual_prices.dropna().index[0]
    overlap_end = actual_prices.dropna().index[-1]
    frame = pd.DataFrame(index=actual_prices.loc[overlap_start:overlap_end].index)
    frame["Actual TQQQ"] = actual_prices.loc[overlap_start:overlap_end]
    for label, series in modeled_prices.items():
        frame[label] = series.loc[overlap_start:overlap_end]
    frame = frame.dropna(how="all")
    return frame.divide(frame.iloc[0]).mul(100.0)


def plot_overlap_validation(normalized_overlap: pd.DataFrame, output_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 7))
    for column in normalized_overlap.columns:
        linewidth = 2.2 if column == "Actual TQQQ" else 1.8
        ax.plot(normalized_overlap.index, normalized_overlap[column], label=column, linewidth=linewidth)
    ax.set_title("TQQQ Overlap Validation (Normalized To 100 At Inception)")
    ax.set_ylabel("Normalized Price")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_long_history(frame: pd.DataFrame, output_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        frame.index,
        frame["TQQQ_3X_CALIBRATED_STITCHED"],
        label="TQQQ stitched (canonical)",
        linewidth=2.3,
        color="#1565C0",
    )
    ax.plot(
        frame.index,
        frame["TQQQ_3X_CALIBRATED"],
        label="TQQQ synthetic (continued)",
        linewidth=1.6,
        color="#EF6C00",
        alpha=0.9,
    )
    actual = frame["TQQQ"].dropna()
    ax.plot(actual.index, actual, label="Actual TQQQ", linewidth=1.8, color="#2E7D32", alpha=0.9)
    ax.set_yscale("log")
    ax.set_title("TQQQ Extended To 1991 (Log Scale)")
    ax.set_ylabel("Adjusted Close / Synthetic Level")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch-start",
        default=DEFAULT_FETCH_START,
        help="Market data download start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--history-start",
        default=DEFAULT_HISTORY_START,
        help="Requested history start date for the extended series in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Optional market data download end date in YYYY-MM-DD format. Omit for latest available data.",
    )
    parser.add_argument(
        "--benchmark-ticker",
        default=DEFAULT_BENCHMARK_TICKER,
        help="Underlying benchmark ticker used for the synthetic LETF model.",
    )
    parser.add_argument(
        "--letf-ticker",
        default=DEFAULT_LETF_TICKER,
        help="Live LETF ticker used for overlap calibration and stitching.",
    )
    parser.add_argument(
        "--rate-series-id",
        default=DEFAULT_RATE_SERIES_ID,
        help="FRED short-rate series id used for financing cost modeling.",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=DEFAULT_LEVERAGE,
        help="Daily leverage target.",
    )
    parser.add_argument(
        "--annual-fee",
        type=float,
        default=DEFAULT_ANNUAL_FEE,
        help="Annual expense ratio expressed as a decimal.",
    )
    parser.add_argument(
        "--calibrated-financing-multiplier",
        type=float,
        default=None,
        help="Optional override for the net financing multiplier. Omit to calibrate from overlap.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = download_adj_close([args.benchmark_ticker, args.letf_ticker], args.fetch_start, args.end)
    financing_rate = download_fred_series(args.rate_series_id).reindex(prices.index).ffill().bfill()
    prices = prices.join(financing_rate, how="left")

    benchmark_returns = compute_return_series_from_prices(prices[args.benchmark_ticker], f"{args.benchmark_ticker}_RETURN")
    actual_returns = compute_return_series_from_prices(prices[args.letf_ticker], f"{args.letf_ticker}_RETURN")
    actual_overlap_returns = prices[args.letf_ticker].dropna().pct_change()

    overlap = pd.DataFrame(
        {
            "benchmark_return": benchmark_returns,
            "actual_return": actual_overlap_returns,
            "financing_rate": financing_rate,
        }
    ).dropna()

    if args.calibrated_financing_multiplier is None:
        calibrated_multiplier = calibrate_financing_multiplier(
            overlap["benchmark_return"],
            overlap["actual_return"],
            overlap["financing_rate"],
            leverage=args.leverage,
            annual_fee=args.annual_fee,
        )
    else:
        calibrated_multiplier = args.calibrated_financing_multiplier

    models = [
        ModelSpec(name="fee_only", financing_multiplier=0.0, label="TQQQ 3x fee only"),
        ModelSpec(name="theoretical_excess_cash", financing_multiplier=args.leverage - 1.0, label="TQQQ 3x fee + 2x cash"),
        ModelSpec(name="calibrated", financing_multiplier=calibrated_multiplier, label="TQQQ 3x calibrated"),
    ]

    frame = prices[[args.benchmark_ticker, args.letf_ticker, args.rate_series_id]].copy()
    frame[actual_returns.name] = actual_returns

    anchored_prices: dict[str, pd.Series] = {}
    diagnostics_rows: list[dict[str, float]] = []

    actual_price_series = prices[args.letf_ticker].dropna()
    anchor_date = actual_price_series.index[0]
    anchor_value = float(actual_price_series.iloc[0])

    for model in models:
        return_col = f"{args.letf_ticker}_3X_{model.name.upper()}_RETURN"
        price_col = f"{args.letf_ticker}_3X_{model.name.upper()}"
        modeled_returns = build_model_returns(
            benchmark_returns=benchmark_returns,
            financing_rate=financing_rate,
            leverage=args.leverage,
            annual_fee=args.annual_fee,
            financing_multiplier=model.financing_multiplier,
            output_name=return_col,
        )
        frame[return_col] = modeled_returns
        anchored = build_anchored_price_series(
            modeled_returns,
            anchor_date=anchor_date,
            anchor_value=anchor_value,
            output_name=price_col,
        )
        frame[price_col] = anchored
        anchored_prices[model.label] = anchored

        if model.name == "calibrated":
            stitched_returns, stitched_anchor_date = stitch_return_series(
                modeled_returns,
                actual_price_series,
                f"{args.letf_ticker}_3X_CALIBRATED_STITCHED_RETURN",
            )
            frame[stitched_returns.name] = stitched_returns
            stitched_prices = build_anchored_price_series(
                stitched_returns,
                anchor_date=stitched_anchor_date,
                anchor_value=anchor_value,
                output_name=f"{args.letf_ticker}_3X_CALIBRATED_STITCHED",
            )
            frame[stitched_prices.name] = stitched_prices
        else:
            stitched_prices = anchored

        diagnostics_rows.append(
            compare_model_to_actual(
                actual_prices=actual_price_series,
                synthetic_returns=modeled_returns,
                stitched_prices=stitched_prices,
                model_name=model.name,
                financing_multiplier=model.financing_multiplier,
                annual_fee=args.annual_fee,
            )
        )

    history_start = pd.Timestamp(args.history_start)
    frame = frame.loc[frame.index >= history_start].copy()

    normalized_overlap = build_normalized_overlap_frame(actual_price_series, anchored_prices)

    diagnostics = pd.DataFrame(diagnostics_rows)
    diagnostics_path = OUTPUT_DIR / "tqqq_model_diagnostics.csv"
    diagnostics.to_csv(diagnostics_path, index=False)

    summary = pd.DataFrame(
        [
            {
                "history_start": frame.index[0].strftime("%Y-%m-%d"),
                "history_end": frame.index[-1].strftime("%Y-%m-%d"),
                "benchmark_ticker": args.benchmark_ticker,
                "letf_ticker": args.letf_ticker,
                "rate_series_id": args.rate_series_id,
                "leverage": args.leverage,
                "annual_fee": args.annual_fee,
                "calibrated_financing_multiplier": calibrated_multiplier,
                "actual_inception": anchor_date.strftime("%Y-%m-%d"),
                "actual_anchor_price": anchor_value,
                "canonical_start_level": float(frame["TQQQ_3X_CALIBRATED_STITCHED"].iloc[0]),
                "canonical_end_level": float(frame["TQQQ_3X_CALIBRATED_STITCHED"].iloc[-1]),
            }
        ]
    )
    summary_path = OUTPUT_DIR / "tqqq_extension_summary.csv"
    summary.to_csv(summary_path, index=False)

    data_path = OUTPUT_DIR / "tqqq_extension_1991.csv"
    frame.to_csv(data_path, index_label="Date")

    overlap_plot_path = OUTPUT_DIR / "tqqq_overlap_validation.png"
    plot_overlap_validation(normalized_overlap, overlap_plot_path)

    long_history_plot_path = OUTPUT_DIR / "tqqq_1991_extension.png"
    plot_long_history(frame, long_history_plot_path)

    print("Saved:")
    print(f"- {data_path}")
    print(f"- {summary_path}")
    print(f"- {diagnostics_path}")
    print(f"- {overlap_plot_path}")
    print(f"- {long_history_plot_path}")
    print()
    print("Canonical calibrated financing multiplier:", round(calibrated_multiplier, 6))
    print("History window:", frame.index[0].strftime("%Y-%m-%d"), "..", frame.index[-1].strftime("%Y-%m-%d"))
    print("Actual anchor:", anchor_date.strftime("%Y-%m-%d"), "price", round(anchor_value, 6))
    print(
        "Canonical synthetic start/end:",
        round(float(frame["TQQQ_3X_CALIBRATED_STITCHED"].iloc[0]), 6),
        "->",
        round(float(frame["TQQQ_3X_CALIBRATED_STITCHED"].iloc[-1]), 6),
    )


if __name__ == "__main__":
    main()
