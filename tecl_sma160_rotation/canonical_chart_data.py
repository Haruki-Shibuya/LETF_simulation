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

CANONICAL_VARIANTS = {
    "2005": {
        "label": "2005-12-20開始",
        "start": "2005-12-20",
        "stem": "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220",
    },
    "2010": {
        "label": "2010-02-12開始",
        "start": "2010-02-12",
        "stem": "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212",
    },
}
DEFAULT_VARIANT = "2005"
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


def _variant_paths(variant: str) -> tuple[dict[str, str], Path, Path]:
    spec = CANONICAL_VARIANTS.get(variant) or CANONICAL_VARIANTS[DEFAULT_VARIANT]
    stem = spec["stem"]
    return spec, OUTPUT_DIR / f"{stem}_daily_path.csv", OUTPUT_DIR / f"{stem}_summary.csv"


def _load_meta(summary_path: Path) -> dict[str, float | str | None]:
    row = _read_one(summary_path)
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


def _uvix_spans(rows: list[dict[str, Any]], meta: dict[str, float | str | None]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    start_i: int | None = None
    entry_tqqq_open: float | None = None
    entry_gspc_open: float | None = None
    entry_rsi_threshold = finite_or_none(meta.get("entry_rsi")) or 69.5
    entry_bbz_threshold = finite_or_none(meta.get("uvix_entry_min_bb_z"))
    exit_rsi_threshold = finite_or_none(meta.get("exit_rsi")) or 68.5
    has_drop_exit = "uvix_tqqq_drop_exit_pct" in meta
    drop_exit_pct = finite_or_none(meta.get("uvix_tqqq_drop_exit_pct")) if has_drop_exit else None
    has_gspc_profit_exit = "uvix_gspc_profit_exit_pct" in meta
    gspc_profit_exit_pct = (
        finite_or_none(meta.get("uvix_gspc_profit_exit_pct")) if has_gspc_profit_exit else None
    )

    for i, row in enumerate(rows):
        action = str(row.get("action") or "")
        is_hold = bool(row["uvix_hold"])
        if is_hold and start_i is None:
            start_i = i
            entry_tqqq_open = row["tqqq_open"]
            entry_gspc_open = row["gspc_price"]

        last = i == len(rows) - 1
        should_close = start_i is not None and ((not is_hold) or last)
        if should_close:
            end_i = i if (not is_hold) else i
            if end_i >= start_i:
                first = rows[start_i]
                last_row = rows[end_i]
                entry_gspc = first["gspc_price"]
                exit_gspc = last_row["gspc_price"]
                entry_uvix = first["uvix_price"]
                exit_uvix = last_row["uvix_price"]
                previous_row = rows[start_i - 1] if start_i > 0 else None
                entry_reasons = ["RSI >= " + f"{entry_rsi_threshold:g}"]
                if entry_bbz_threshold is not None:
                    entry_reasons.append("BB20Z >= " + f"{entry_bbz_threshold:g}")
                entry_reason = " & ".join(entry_reasons)
                if previous_row is not None:
                    prev_bits: list[str] = []
                    if previous_row["rsi"] is not None:
                        prev_bits.append("prior RSI " + f"{previous_row['rsi']:.2f}")
                    if previous_row["bb20_z"] is not None:
                        prev_bits.append("prior BB20Z " + f"{previous_row['bb20_z']:.2f}")
                    if prev_bits:
                        entry_reason += " (" + ", ".join(prev_bits) + ")"
                exit_reasons: list[str] = []
                if "exit_uvix" in action:
                    if "rsi" in action and last_row["rsi"] is not None and last_row["rsi"] <= exit_rsi_threshold:
                        exit_reasons.append("RSI exit")
                    tqqq_open = last_row["tqqq_open"]
                    if "drop" in action and drop_exit_pct is not None and entry_tqqq_open is not None and tqqq_open is not None:
                        drop_trigger = entry_tqqq_open * (1.0 - drop_exit_pct / 100.0)
                        if tqqq_open <= drop_trigger:
                            exit_reasons.append("TQQQ open <= entry")
                    if (
                        "gspc_profit" in action
                        and gspc_profit_exit_pct is not None
                        and entry_gspc_open is not None
                        and last_row["gspc_price"] is not None
                    ):
                        gspc_profit_trigger = entry_gspc_open * (1.0 + gspc_profit_exit_pct / 100.0)
                        if last_row["gspc_price"] <= gspc_profit_trigger:
                            exit_reasons.append("GSPC open <= entry + " + f"{gspc_profit_exit_pct:g}%")
                elif last and is_hold:
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
                        "entry_gspc_open": entry_gspc,
                        "exit_gspc_open": exit_gspc,
                        "entry_action": first.get("action") or "",
                        "entry_reason": entry_reason,
                        "previous_rsi": None if previous_row is None else previous_row["rsi"],
                        "previous_bb20_z": None if previous_row is None else previous_row["bb20_z"],
                        "exit_action": action,
                        "exit_reason": " + ".join(exit_reasons) if exit_reasons else "exit_uvix",
                        "gspc_return": None if not entry_gspc or exit_gspc is None else exit_gspc / entry_gspc - 1.0,
                        "uvix_return": None if not entry_uvix or exit_uvix is None else exit_uvix / entry_uvix - 1.0,
                    }
                )
            start_i = None
            entry_tqqq_open = None
            entry_gspc_open = None
    return spans


def build_canonical_chart_payload(variant: str = DEFAULT_VARIANT) -> dict[str, Any]:
    spec, daily_path, summary_path = _variant_paths(variant)
    canonical = _read_rows(daily_path)
    meta = _load_meta(summary_path)
    gspc_by_date = {row["Date"]: finite_or_none(row.get("GSPC_OPEN")) for row in _read_rows(GSPC_OHLC_PATH)}
    uvix_by_date = {row["Date"]: finite_or_none(row.get("UVIX_OPEN")) for row in _read_rows(UVIX_OHLC_PATH)}

    rows: list[dict[str, Any]] = []
    for row in canonical:
        date = row["Date"]
        gspc_price = finite_or_none(row.get("GSPC_OPEN")) or gspc_by_date.get(date)
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

    spans = _uvix_spans(rows, meta)
    return {
        "variant": variant if variant in CANONICAL_VARIANTS else DEFAULT_VARIANT,
        "variant_label": spec["label"],
        "available_variants": {
            key: {"label": value["label"], "start": value["start"]} for key, value in CANONICAL_VARIANTS.items()
        },
        "title": f"Canonical UVIX high-RSI episodes | {spec['label']} | GSPC open / UVIX open / RSI14",
        "subtitle": "GSPC and UVIX are normalized to each episode entry open; RSI is plotted on the lower pane.",
        "dates": [row["date"] for row in rows],
        "gspc_price": [row["gspc_price"] for row in rows],
        "uvix_price": [row["uvix_price"] for row in rows],
        "rsi": [row["rsi"] for row in rows],
        "bb20_z": [row["bb20_z"] for row in rows],
        "uvix_hold": [row["uvix_hold"] for row in rows],
        "spans": spans,
        "meta": meta,
        "source_files": {
            "canonical_daily": _relative(daily_path),
            "gspc_open": _relative(GSPC_OHLC_PATH),
            "uvix_open": _relative(UVIX_OHLC_PATH),
        },
    }


def canonical_chart_site_payload() -> dict[str, Any]:
    return {
        "selected_variant": DEFAULT_VARIANT,
        "available_variants": {
            key: {"label": value["label"], "start": value["start"]} for key, value in CANONICAL_VARIANTS.items()
        },
        "variants": {key: build_canonical_chart_payload(key) for key in CANONICAL_VARIANTS},
    }


def canonical_chart_json() -> str:
    return json.dumps(canonical_chart_site_payload(), ensure_ascii=False, separators=(",", ":"))
