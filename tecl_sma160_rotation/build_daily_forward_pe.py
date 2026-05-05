"""
Build daily forward P/E for S&P 500 and QQQ/NDX, without look-ahead bias.

Sources:
  S&P 500: Doinoff monthly (1982–2025) + Trendonify 2026 extension
  QQQ/NDX: Trendonify monthly (2005–present)  ← earliest available source

Coverage:
  sp500_forward_pe : 1982-02 onward (daily from first available trading day)
  qqq_forward_pe   : 2005-01 onward (no point-in-time EPS source exists before 2005)

Method:
  1. Derive implied forward EPS per month: EPS_M = index_level_M / pe_M
  2. Shift EPS by 1 month (M+1 uses M's EPS) → eliminates look-ahead bias
  3. daily_pe(D) = daily_price(D) / EPS_{M-1}  where M is the calendar month of D

Output: output/valuation_forward_pe_daily.csv  (replaces previous file)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
OUTPUT   = BASE_DIR / "output"
OUT_PATH = OUTPUT / "valuation_forward_pe_daily.csv"

DOINOFF_PATH     = OUTPUT / "valuation_sp500_forward_pe_doinoff_monthly.csv"
TRENDONIFY_NDX   = OUTPUT / "valuation_nasdaq100_forward_pe_trendonify_monthly.csv"
TRENDONIFY_SP500 = OUTPUT / "valuation_sp500_forward_pe_trendonify_monthly.csv"

SP500_START = "1982-01-01"
QQQ_START   = "2005-01-01"
PRICE_START = "1982-01-01"
END         = "2026-05-05"


def _close(ticker: str, start: str) -> pd.Series:
    df = yf.download(ticker, start=start, end=END, auto_adjust=True, progress=False)
    s = df["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s.squeeze()


def load_sp500_monthly() -> pd.DataFrame:
    """Doinoff 1982-2025, extended with Trendonify for 2026."""
    doinoff = pd.read_csv(DOINOFF_PATH, parse_dates=["date"]).set_index("date")
    doinoff = doinoff[["sp500_level", "sp500_forward_pe_doinoff"]].rename(
        columns={"sp500_forward_pe_doinoff": "sp500_forward_pe"}
    )

    # Trendonify extension for months not covered by Doinoff
    if TRENDONIFY_SP500.exists():
        trend = pd.read_csv(TRENDONIFY_SP500, parse_dates=["date"]).set_index("date")
        trend_col = [c for c in trend.columns if "forward_pe" in c][0]
        trend = trend[[trend_col]].rename(columns={trend_col: "sp500_forward_pe"})
        # fill sp500_level for Trendonify rows using yfinance later
        missing = trend[~trend.index.isin(doinoff.index)]
        if not missing.empty:
            gspc_monthly = _close("^GSPC", SP500_START).resample("MS").first()
            missing = missing.copy()
            missing["sp500_level"] = gspc_monthly.reindex(missing.index).ffill().values
            doinoff = pd.concat([doinoff, missing]).sort_index()

    # Normalize to month-start for alignment
    doinoff.index = doinoff.index.to_period("M").to_timestamp()
    return doinoff.groupby(level=0).last()


def load_qqq_monthly() -> pd.Series:
    """Trendonify NDX forward P/E 2005–present."""
    df = pd.read_csv(TRENDONIFY_NDX, parse_dates=["date"]).set_index("date")
    col = [c for c in df.columns if "forward_pe" in c][0]
    s = df[col].rename("qqq_forward_pe")
    s.index = s.index.to_period("M").to_timestamp()
    return s.groupby(level=0).last()


def build_sp500_daily(monthly: pd.DataFrame) -> pd.Series:
    """Daily S&P 500 forward P/E from 1982."""
    gspc = _close("^GSPC", SP500_START)

    # Derive forward EPS and shift 1 month
    eps = (monthly["sp500_level"] / monthly["sp500_forward_pe"]).rename("eps")
    eps_lagged = eps.shift(1)  # M+1 uses M's EPS

    # Forward-fill lagged EPS onto daily index
    all_idx = gspc.index.union(eps_lagged.index).sort_values()
    eps_daily = eps_lagged.reindex(all_idx).ffill().reindex(gspc.index)

    pe = (gspc / eps_daily).rename("sp500_forward_pe")
    return pe.dropna()


def build_qqq_daily(monthly: pd.Series) -> pd.Series:
    """Daily QQQ forward P/E from 2005."""
    qqq = _close("QQQ", QQQ_START)

    # Derive QQQ forward EPS using QQQ price at month-start as reference
    qqq_monthly = qqq.resample("MS").first()
    eps = (qqq_monthly / monthly).rename("eps")
    eps_lagged = eps.shift(1)

    all_idx = qqq.index.union(eps_lagged.index).sort_values()
    eps_daily = eps_lagged.reindex(all_idx).ffill().reindex(qqq.index)

    pe = (qqq / eps_daily).rename("qqq_forward_pe")
    return pe.dropna()


def main() -> None:
    print("Loading monthly S&P 500 forward P/E (Doinoff 1982+) ...")
    sp500_monthly = load_sp500_monthly()
    print(f"  {sp500_monthly.index[0].date()} – {sp500_monthly.index[-1].date()}, {len(sp500_monthly)} months")

    print("Loading monthly QQQ/NDX forward P/E (Trendonify 2005+) ...")
    qqq_monthly = load_qqq_monthly()
    print(f"  {qqq_monthly.index[0].date()} – {qqq_monthly.index[-1].date()}, {len(qqq_monthly)} months")

    print("Building daily S&P 500 forward P/E ...")
    sp500_daily = build_sp500_daily(sp500_monthly)
    print(f"  {sp500_daily.index[0].date()} – {sp500_daily.index[-1].date()}, {len(sp500_daily)} days")

    print("Building daily QQQ forward P/E ...")
    qqq_daily = build_qqq_daily(qqq_monthly)
    print(f"  {qqq_daily.index[0].date()} – {qqq_daily.index[-1].date()}, {len(qqq_daily)} days")

    out = pd.DataFrame({"sp500_forward_pe": sp500_daily, "qqq_forward_pe": qqq_daily})
    out.index.name = "date"
    out = out.sort_index()
    out.to_csv(OUT_PATH)

    print(f"\nSaved {len(out)} rows → {OUT_PATH}")
    print(out.head(3).to_string())
    print("...")
    print(out.tail(3).to_string())
    print(out.describe().to_string())


if __name__ == "__main__":
    main()
