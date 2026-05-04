"""
Build truly daily forward P/E for S&P 500 and QQQ, without look-ahead bias.

Logic:
  forward_EPS_month_M  = index_level_M / pe_M          (derived from existing monthly data)
  daily_forward_pe_day_D = daily_price_D / forward_EPS_{M-1}
  (Day D uses the PREVIOUS month's EPS estimate → no look-ahead bias)

Price data: yfinance (^GSPC, QQQ)
Monthly P/E source: existing valuation_forward_pe_2005_sim_daily_ffill.csv
Output: output/valuation_forward_pe_daily.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR  = Path(__file__).resolve().parent
OUTPUT    = BASE_DIR / "output"
SRC_PATH  = OUTPUT / "valuation_forward_pe_2005_sim_daily_ffill.csv"
OUT_PATH  = OUTPUT / "valuation_forward_pe_daily.csv"

START = "2005-01-01"
END   = "2026-05-05"


def load_monthly_pe() -> pd.DataFrame:
    df = pd.read_csv(SRC_PATH, parse_dates=["date"]).set_index("date")
    # Keep one row per month (use first trading day of each month as anchor)
    df["month"] = df.index.to_period("M")
    monthly = df.groupby("month").first()
    monthly.index = monthly.index.to_timestamp()
    return monthly[["sp500_forward_pe", "sp500_level", "qqq_forward_pe"]]


def _close(ticker: str) -> pd.Series:
    df = yf.download(ticker, start=START, end=END, auto_adjust=True, progress=False)
    s = df["Close"]
    if isinstance(s.columns if hasattr(s, "columns") else None, pd.MultiIndex) or isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.squeeze()


def derive_forward_eps(monthly: pd.DataFrame) -> pd.DataFrame:
    """Derive forward EPS from level / pe, then shift 1 month to remove look-ahead bias."""
    m = monthly.copy()
    m["sp500_fwd_eps"] = m["sp500_level"] / m["sp500_forward_pe"]

    # For QQQ we need the QQQ price at the time the P/E was recorded.
    # Fetch month-end QQQ prices aligned with the monthly index.
    qqq_raw = _close("QQQ")
    qqq_raw.index = pd.to_datetime(qqq_raw.index).tz_localize(None)

    # Resample to month-start to align with monthly P/E (first trading day of month)
    qqq_monthly = qqq_raw.resample("MS").first()
    m["qqq_price_at_pe"] = qqq_monthly.reindex(m.index).ffill()
    m["qqq_fwd_eps"] = m["qqq_price_at_pe"] / m["qqq_forward_pe"]

    # Shift 1 month: January trading days use December's EPS estimate
    m["sp500_fwd_eps_lagged"] = m["sp500_fwd_eps"].shift(1)
    m["qqq_fwd_eps_lagged"]   = m["qqq_fwd_eps"].shift(1)

    return m[["sp500_fwd_eps_lagged", "qqq_fwd_eps_lagged"]]


def build_daily(eps: pd.DataFrame) -> pd.DataFrame:
    # Daily prices
    gspc = _close("^GSPC")
    qqq  = _close("QQQ")

    prices = pd.DataFrame({"gspc": gspc, "qqq": qqq}).dropna()

    # Merge lagged EPS onto daily index (ffill from prior month-start)
    combined = eps.reindex(prices.index.union(eps.index).sort_values()).ffill()
    combined = combined.reindex(prices.index)

    out = pd.DataFrame(index=prices.index)
    out["sp500_forward_pe"] = prices["gspc"] / combined["sp500_fwd_eps_lagged"]
    out["qqq_forward_pe"]   = prices["qqq"]  / combined["qqq_fwd_eps_lagged"]
    out.index.name = "date"
    return out.dropna()


def main() -> None:
    print("Loading monthly P/E source ...")
    monthly = load_monthly_pe()

    print("Deriving forward EPS (with 1-month lag) ...")
    eps = derive_forward_eps(monthly)

    print("Downloading daily prices and building daily P/E ...")
    daily = build_daily(eps)

    daily.to_csv(OUT_PATH)
    print(f"\nSaved {len(daily)} rows → {OUT_PATH}")
    print(daily.head())
    print(daily.tail())
    print(daily.describe())


if __name__ == "__main__":
    main()
