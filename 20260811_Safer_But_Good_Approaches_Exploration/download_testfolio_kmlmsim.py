from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output" / "data"
API_URL = "https://testfol.io/api/backtest"


def calculate_local_stats(daily: pd.DataFrame) -> dict[str, float]:
    """Rebuild headline statistics from the rounded daily return series."""
    returns = daily["KMLMSIM_Return"]
    nav = (1.0 + returns).cumprod()
    years = (daily["Date"].iloc[-1] - daily["Date"].iloc[0]).days / 365.2425
    drawdown = nav / nav.cummax() - 1.0
    return {
        "cagr": 100.0 * (nav.iloc[-1] ** (1.0 / years) - 1.0),
        "max_drawdown": 100.0 * drawdown.min(),
        "std": 100.0 * returns.std(ddof=1) * (252.0**0.5),
        "nom_end_val": 10_000.0 * nav.iloc[-1],
    }


def validate_reconstruction(local: dict[str, float], api: dict) -> dict[str, float]:
    """Fail loudly if the downloaded series no longer reproduces Testfolio."""
    differences = {key: local[key] - float(api[key]) for key in local}
    limits = {
        "cagr": 0.01,          # percentage points
        "max_drawdown": 0.05, # percentage points
        "std": 0.01,           # percentage points
        "nom_end_val": 100.0,  # dollars from a $10,000 start
    }
    failures = {
        key: difference
        for key, difference in differences.items()
        if abs(difference) > limits[key]
    }
    if failures:
        raise RuntimeError(
            "Rounded daily KMLMSIM series no longer matches Testfolio stats: "
            f"{failures}"
        )
    return differences


def build_payload() -> dict:
    """Return the minimal Testfolio backtest request for 100% KMLMSIM."""
    return {
        "start_date": "",
        "end_date": "",
        "start_val": 10_000,
        "adj_inflation": False,
        "adjust_cashflows_for_inflation": False,
        "annual_cashflow_growth_rate": 0,
        "target_currency": "USD",
        "cashflow": 0,
        "cashflow_freq": "Yearly",
        "cashflow_offset": 0,
        "cashflow_legs": [],
        "one_time_cashflows": [],
        "rolling_window": 60,
        "withdrawal_surface_include": False,
        "backtests": [
            {
                "allocation": {"KMLMSIM": 100},
                "invest_dividends": True,
                "rebalance_freq": "Yearly",
                "rebalance_offset": 0,
                "drag": 0,
                "absolute_dev": 0,
                "relative_dev": 0,
                "rebalance_band_mode": "SYMMETRIC",
            }
        ],
    }


def download() -> tuple[pd.DataFrame, dict]:
    payload = json.dumps(build_payload()).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LETF-simulation-research/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        result = json.load(response)

    errors = result.get("errors") or []
    if errors:
        raise RuntimeError(f"Testfolio returned errors: {errors}")

    rows = result.get("daily_returns") or []
    if not rows:
        raise RuntimeError("Testfolio response did not contain daily_returns")

    daily = pd.DataFrame(rows, columns=["Date", "Return_Percent", "NAV_10000"])
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily["KMLMSIM_Return"] = daily["Return_Percent"] / 100.0
    daily = daily[["Date", "KMLMSIM_Return", "NAV_10000"]]

    api_stats = (result.get("stats") or [{}])[0]
    local_stats = calculate_local_stats(daily)
    differences = validate_reconstruction(local_stats, api_stats)

    metadata = {
        "source": API_URL,
        "ticker": "KMLMSIM",
        "definition": "KFA MLM Index minus 0.9% p.a. (1988-2020), KMLM thereafter",
        "api_start_date": result.get("start_date"),
        "api_end_date": result.get("end_date"),
        "limiting_ticker": result.get("limiting_ticker"),
        "row_count": len(daily),
        "stats": api_stats,
        "local_reconstruction_stats": local_stats,
        "local_minus_api": differences,
        "precision_note": (
            "Testfolio API daily_returns are reported to three decimal percentage "
            "points. The precise API headline stats are retained separately."
        ),
    }
    return daily, metadata


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    daily, metadata = download()

    csv_path = OUTPUT / "testfolio_kmlmsim_daily.csv"
    metadata_path = OUTPUT / "testfolio_kmlmsim_metadata.json"
    daily.to_csv(csv_path, index=False)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Saved {len(daily):,} rows to {csv_path}")
    print(json.dumps(metadata["stats"], indent=2))
    print("Local reconstruction minus API:")
    print(json.dumps(metadata["local_minus_api"], indent=2))


if __name__ == "__main__":
    main()
