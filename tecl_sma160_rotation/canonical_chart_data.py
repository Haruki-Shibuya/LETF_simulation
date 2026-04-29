from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


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
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"required file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return sorted(csv.DictReader(f), key=lambda row: row["Date"])


def _read_one(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return next(csv.DictReader(f), {})


def _load_meta() -> dict[str, float | str | None]:
    row = _read_one(CANONICAL_SUMMARY_PATH)
    meta: dict[str, float | str | None] = {}
    for key, value in row.items():
        number = finite_or_none(value)
        meta[key] = number if number is not None else (value or None)
    if "uvix_entry_rsi" in meta:
        meta["entry_rsi"] = meta["uvix_entry_rsi"]
    if "uvix_exit_rsi" in meta:
        meta["exit_rsi"] = meta["uvix_exit_rsi"]
    meta.setdefault("entry_rsi", 69.5)
    meta.setdefault("exit_rsi", 68.5)
    return meta


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR))
    except ValueError:
        return str(path)


def _uvix_spans(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    start_i: int | None = None
    entry_tqqq_open: float | None = None
    meta = _load_meta()
    exit_rsi_threshold = finite_or_none(meta.get("exit_rsi")) or 68.5
    drop_exit_pct = finite_or_none(meta.get("uvix_tqqq_drop_exit_pct")) or 0.0

    for i, row in enumerate(rows):
        action = str(row.get("action") or "")
        if "enter_uvix" in action and start_i is None:
            start_i = i
            entry_tqqq_open = row["tqqq_open"]
            continue

        last = i == len(rows) - 1
        should_close = start_i is not None and ("exit_uvix" in action or last)
        if should_close:
            end_i = i
            if end_i >= start_i:
                first = rows[start_i]
                last_row = rows[end_i]
                entry_gspc = first["gspc_price"]
                exit_gspc = last_row["gspc_price"]
                entry_uvix = first["uvix_price"]
                exit_uvix = last_row["uvix_price"]
                exit_reasons: list[str] = []
                if "exit_uvix" in action:
                    if last_row["rsi"] is not None and last_row["rsi"] <= exit_rsi_threshold:
                        exit_reasons.append("RSI exit")
                    tqqq_open = last_row["tqqq_open"]
                    if entry_tqqq_open is not None and tqqq_open is not None:
                        drop_trigger = entry_tqqq_open * (1.0 - drop_exit_pct / 100.0)
                        if tqqq_open <= drop_trigger:
                            exit_reasons.append("TQQQ open drop exit")
                elif last:
                    exit_reasons.append("open episode")
                spans.append(
                    {
                        "start": first["date"],
                        "end": last_row["date"],
                        "days": end_i - start_i + 1,
                        "entry_rsi": first["rsi"],
                        "exit_rsi": last_row["rsi"],
                        "entry_tqqq_open": entry_tqqq_open,
                        "exit_tqqq_open": last_row["tqqq_open"],
                        "exit_action": action,
                        "exit_reason": " + ".join(exit_reasons) if exit_reasons else "exit_uvix",
                        "gspc_return": None if not entry_gspc or exit_gspc is None else exit_gspc / entry_gspc - 1.0,
                        "uvix_return": None if not entry_uvix or exit_uvix is None else exit_uvix / entry_uvix - 1.0,
                    }
                )
            start_i = None
            entry_tqqq_open = None
    return spans


def build_canonical_chart_payload() -> dict[str, Any]:
    canonical = _read_rows(CANONICAL_DAILY_PATH)
    gspc_by_date = {row["Date"]: finite_or_none(row.get("GSPC_OPEN")) for row in _read_rows(GSPC_OHLC_PATH)}
    uvix_by_date = {row["Date"]: finite_or_none(row.get("UVIX_OPEN")) for row in _read_rows(UVIX_OHLC_PATH)}

    rows: list[dict[str, Any]] = []
    for row in canonical:
        date = row["Date"]
        gspc_price = gspc_by_date.get(date)
        uvix_price = uvix_by_date.get(date)
        rsi = finite_or_none(row.get("gspc_open_implied_rsi14"))
        tqqq_open = finite_or_none(row.get("TQQQ_OPEN"))
        if gspc_price is None or uvix_price is None or rsi is None:
            continue
        rows.append(
            {
                "date": date,
                "gspc_price": gspc_price,
                "uvix_price": uvix_price,
                "rsi": rsi,
                "bb20_z": finite_or_none(row.get("GSPC_BB20_Z")),
                "tqqq_open": tqqq_open,
                "action": row.get("action") or "",
                "uvix_hold": row.get("selected_leg") == "UVIX",
            }
        )

    spans = _uvix_spans(rows)
    return {
        "title": "Canonical UVIX high-RSI episodes | GSPC open / UVIX open / RSI14",
        "subtitle": "GSPC and UVIX are normalized to each episode entry open; RSI is plotted on the lower pane.",
        "dates": [row["date"] for row in rows],
        "gspc_price": [row["gspc_price"] for row in rows],
        "uvix_price": [row["uvix_price"] for row in rows],
        "rsi": [row["rsi"] for row in rows],
        "bb20_z": [row["bb20_z"] for row in rows],
        "uvix_hold": [row["uvix_hold"] for row in rows],
        "spans": spans,
        "meta": _load_meta(),
        "source_files": {
            "canonical_daily": _relative(CANONICAL_DAILY_PATH),
            "gspc_open": _relative(GSPC_OHLC_PATH),
            "uvix_open": _relative(UVIX_OHLC_PATH),
        },
    }


def canonical_chart_json() -> str:
    return json.dumps(build_canonical_chart_payload(), ensure_ascii=False, separators=(",", ":"))
