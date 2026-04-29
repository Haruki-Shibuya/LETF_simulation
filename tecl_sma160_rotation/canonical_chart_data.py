from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
DASHBOARD_DIR = BASE_DIR / "dashboard"

CANONICAL_STEM = "canonical_prev_close_sma_same_open_running_dd_uvix_bb20z_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212"
CANONICAL_DAILY_PATH = OUTPUT_DIR / f"{CANONICAL_STEM}_daily_path.csv"
CANONICAL_SUMMARY_PATH = OUTPUT_DIR / f"{CANONICAL_STEM}_summary.csv"
GSPC_OHLC_PATH = OUTPUT_DIR / "gspc_actual_ohlc_for_soxl_sma200_exit.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"


def finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _jsonable_series(series: pd.Series) -> list[float | None]:
    return [finite_or_none(value) for value in series.tolist()]


def _read_csv(path: Path, *, parse_dates: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required file is missing: {path}")
    return pd.read_csv(path, parse_dates=parse_dates).sort_values(parse_dates[0])


def _load_meta() -> dict[str, float | str | int | None]:
    if not CANONICAL_SUMMARY_PATH.exists():
        return {"entry_rsi": 69.5, "exit_rsi": 68.5}
    row = pd.read_csv(CANONICAL_SUMMARY_PATH).iloc[0].to_dict()
    meta: dict[str, float | str | int | None] = {}
    for key, value in row.items():
        meta[key] = finite_or_none(value)
        if meta[key] is None and value == value:
            meta[key] = str(value)
    if "uvix_entry_rsi" in meta:
        meta["entry_rsi"] = meta["uvix_entry_rsi"]
    if "uvix_exit_rsi" in meta:
        meta["exit_rsi"] = meta["uvix_exit_rsi"]
    meta.setdefault("entry_rsi", 69.5)
    meta.setdefault("exit_rsi", 68.5)
    return meta


def _uvix_spans(frame: pd.DataFrame) -> list[dict[str, Any]]:
    hold = frame["uvix_hold"].tolist()
    dates = frame["Date"].dt.strftime("%Y-%m-%d").tolist()
    spans: list[dict[str, Any]] = []
    start_i: int | None = None

    for i, is_hold in enumerate(hold):
        if is_hold and start_i is None:
            start_i = i
        last = i == len(hold) - 1
        if start_i is not None and ((not is_hold) or last):
            end_i = i if is_hold and last else i - 1
            if end_i >= start_i:
                segment = frame.iloc[start_i : end_i + 1]
                entry_gspc = finite_or_none(segment["GSPC_CLOSE"].iloc[0])
                exit_gspc = finite_or_none(segment["GSPC_CLOSE"].iloc[-1])
                entry_uvix = finite_or_none(segment["UVIX_CLOSE"].iloc[0])
                exit_uvix = finite_or_none(segment["UVIX_CLOSE"].iloc[-1])
                spans.append(
                    {
                        "start": dates[start_i],
                        "end": dates[end_i],
                        "days": int(end_i - start_i + 1),
                        "entry_rsi": finite_or_none(segment["gspc_open_implied_rsi14"].iloc[0]),
                        "exit_rsi": finite_or_none(segment["gspc_open_implied_rsi14"].iloc[-1]),
                        "gspc_return": None
                        if not entry_gspc or exit_gspc is None
                        else exit_gspc / entry_gspc - 1.0,
                        "uvix_return": None
                        if not entry_uvix or exit_uvix is None
                        else exit_uvix / entry_uvix - 1.0,
                    }
                )
            start_i = None
    return spans


def build_canonical_chart_payload() -> dict[str, Any]:
    canonical = _read_csv(CANONICAL_DAILY_PATH, parse_dates=["Date"])
    gspc = _read_csv(GSPC_OHLC_PATH, parse_dates=["Date"])
    uvix = _read_csv(UVIX_OHLC_PATH, parse_dates=["Date"])

    frame = (
        canonical.merge(gspc[["Date", "GSPC_CLOSE"]], on="Date", how="inner")
        .merge(uvix[["Date", "UVIX_CLOSE"]], on="Date", how="inner")
        .sort_values("Date")
    )
    frame["uvix_hold"] = frame["selected_leg"].astype(str).eq("UVIX")
    frame = frame.dropna(subset=["gspc_open_implied_rsi14", "GSPC_CLOSE", "UVIX_CLOSE"]).reset_index(drop=True)

    dates = frame["Date"].dt.strftime("%Y-%m-%d").tolist()
    meta = _load_meta()
    spans = _uvix_spans(frame)

    return {
        "title": "Canonical UVIX high-RSI episodes | GSPC close / UVIX close / RSI14",
        "subtitle": "GSPC and UVIX are normalized to each episode entry; RSI is plotted on the lower pane.",
        "dates": dates,
        "gspc_close": _jsonable_series(frame["GSPC_CLOSE"]),
        "uvix_close": _jsonable_series(frame["UVIX_CLOSE"]),
        "rsi": _jsonable_series(frame["gspc_open_implied_rsi14"]),
        "bb20_z": _jsonable_series(frame["GSPC_BB20_Z"]) if "GSPC_BB20_Z" in frame.columns else None,
        "uvix_hold": frame["uvix_hold"].tolist(),
        "spans": spans,
        "meta": meta,
        "source_files": {
            "canonical_daily": str(CANONICAL_DAILY_PATH.relative_to(REPO_DIR)),
            "gspc_ohlc": str(GSPC_OHLC_PATH.relative_to(REPO_DIR)),
            "uvix_ohlc": str(UVIX_OHLC_PATH.relative_to(REPO_DIR)),
        },
    }


def canonical_chart_json() -> str:
    return json.dumps(build_canonical_chart_payload(), ensure_ascii=False, separators=(",", ":"))
