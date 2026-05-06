from __future__ import annotations

import csv
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
OUTPUT_DIR = BASE_DIR / "output"
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
    "1991": {
        "label": "1991-01-02開始（スティッチ）",
        "start": "1991-01-02",
        "stem": "canonical_stitched_1991",
    },
}
DEFAULT_VARIANT = "2005"
GSPC_OHLC_PATH = OUTPUT_DIR / "gspc_actual_ohlc_for_soxl_sma200_exit.csv"

JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")


def finite_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _variant_paths(variant: str) -> tuple[dict[str, str], Path, Path]:
    spec = CANONICAL_VARIANTS.get(variant) or CANONICAL_VARIANTS[DEFAULT_VARIANT]
    stem = spec["stem"]
    return spec, OUTPUT_DIR / f"{stem}_daily_path.csv", OUTPUT_DIR / f"{stem}_summary.csv"


def _load_summary(summary_path: Path) -> dict[str, float | str | None]:
    rows = _read_rows(summary_path)
    if not rows:
        return {}
    out: dict[str, float | str | None] = {}
    for key, value in rows[0].items():
        out[key] = finite_or_none(value)
        if out[key] is None and value not in {None, ""}:
            out[key] = value
    return out


def _iso_minutes(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M JST")


def _ny_open_as_jst(date_text: str | None) -> str | None:
    if not date_text:
        return None
    try:
        date_value = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None
    open_et = datetime.combine(date_value, time(9, 30), tzinfo=ET)
    return _iso_minutes(open_et.astimezone(JST))


def _market_phase(now_et: datetime) -> str:
    if now_et.weekday() >= 5:
        return "closed"
    current = now_et.time()
    if time(4, 0) <= current < time(9, 30):
        return "premarket"
    if time(9, 30) <= current < time(16, 0):
        return "regular"
    if time(16, 0) <= current < time(20, 0):
        return "after_hours"
    return "closed"


def _mode_availability(now_et: datetime) -> dict[str, bool]:
    current = now_et.time()
    is_weekday = now_et.weekday() < 5
    # Treat 20:00-04:00 ET as the next session's pre-market not started yet.
    # During 04:00-09:30, use live pre-market. During 09:30-20:00, keep the
    # final pre-market value available for comparison.
    premarket_available = is_weekday and time(4, 0) <= current < time(20, 0)
    # Today open is meaningful from the regular open through after-hours.
    # After 20:00 ET, reset to the next session and gray it out.
    today_open_available = is_weekday and time(9, 30) <= current < time(20, 0)
    return {
        "latest": True,
        "previous_close": True,
        "premarket": premarket_available,
        "today_open": today_open_available,
    }


def _yahoo_chart(symbol: str) -> dict[str, Any] | None:
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1m&range=1d&includePrePost=true"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return None
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    closes = quote.get("close") or []
    points: list[dict[str, Any]] = []
    for ts, open_value, close in zip(timestamps, opens, closes):
        close_price = finite_or_none(close)
        open_price = finite_or_none(open_value)
        if close_price is None and open_price is None:
            continue
        points.append({"ts": ts, "open": open_price, "close": close_price})
    last_price = None
    last_ts = None
    for point in reversed(points):
        price = point["close"] or point["open"]
        if price is not None:
            last_price = price
            last_ts = point["ts"]
            break
    previous_close = finite_or_none(meta.get("chartPreviousClose")) or finite_or_none(meta.get("previousClose"))
    return {
        "symbol": symbol,
        "last_price": last_price,
        "last_ts": last_ts,
        "previous_close": previous_close,
        "regular_market_price": finite_or_none(meta.get("regularMarketPrice")),
        "timezone": meta.get("exchangeTimezoneName"),
        "points": points,
    }


def _rsi_wilder(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, current in zip(values, values[1:]):
        delta = current - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _bb20_z(previous_closes: list[float], open_input: float) -> float | None:
    window = previous_closes[-20:]
    if len(window) < 20:
        return None
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / len(window)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (open_input - mean) / std


def _build_chart_history(n_days: int = 30) -> list[dict]:
    rows = _read_rows(GSPC_OHLC_PATH)
    dates: list[str] = []
    opens: list[float] = []
    closes: list[float] = []
    for row in rows:
        d = row.get("Date")
        o = finite_or_none(row.get("GSPC_OPEN"))
        c = finite_or_none(row.get("GSPC_CLOSE"))
        if d and o is not None and c is not None:
            dates.append(d)
            opens.append(o)
            closes.append(c)
    n = len(closes)
    if n < 21:
        return []
    start = max(20, n - n_days)
    points: list[dict] = []
    for i in range(start, n):
        bb20_win = closes[i - 20 : i]
        bb20_mean = sum(bb20_win) / 20
        bb20_var = sum((v - bb20_mean) ** 2 for v in bb20_win) / 20
        bb20_std = math.sqrt(bb20_var) if bb20_var > 0 else 0.0
        bb20_upper = bb20_mean + 1.6 * bb20_std
        rsi = _rsi_wilder(closes[:i] + [opens[i]])
        points.append({
            "date": dates[i],
            "gspc_open": opens[i],
            "gspc_close": closes[i],
            "bb20_upper": bb20_upper,
            "rsi14": rsi,
        })
    return points


def _gspc_close_history(before_date: str | None = None) -> list[float]:
    rows = _read_rows(GSPC_OHLC_PATH)
    closes: list[float] = []
    for row in rows:
        if before_date is not None and row.get("Date", "") >= before_date:
            break
        close = finite_or_none(row.get("GSPC_CLOSE"))
        if close is not None:
            closes.append(close)
    return closes


def _latest_gspc_close_row() -> dict[str, Any] | None:
    rows = _read_rows(GSPC_OHLC_PATH)
    for row in reversed(rows):
        close = finite_or_none(row.get("GSPC_CLOSE"))
        if close is not None:
            return {"date": row.get("Date"), "close": close, "open": finite_or_none(row.get("GSPC_OPEN"))}
    return None


def _input_from_gspc_value(label: str, mode: str, source_date: str, source_time_jst: str, gspc_input: float) -> dict[str, Any] | None:
    previous_closes = _gspc_close_history(source_date)
    rsi = _rsi_wilder(previous_closes + [gspc_input])
    bbz = _bb20_z(previous_closes, gspc_input)
    if rsi is None or bbz is None:
        return None
    return {
        "mode": mode,
        "label": label,
        "source_time_jst": source_time_jst,
        "source_date": source_date,
        "gspc_open": gspc_input,
        "tqqq_open": None,
        "rsi": rsi,
        "bb20_z": bbz,
        "notes": ["Implied RSI (14) と BB20 Z は、前日までのGSPC終値にこのGSPC入力値を1点追加して再計算しています。"],
    }


def _previous_close_proxy(now_et: datetime) -> dict[str, Any] | None:
    latest_close = _latest_gspc_close_row()
    if latest_close is None or latest_close["date"] is None or latest_close["close"] is None:
        return None
    # Use the next NY date for the what-if input, so the prior close remains outside the lookback window.
    source_date = now_et.strftime("%Y-%m-%d")
    if source_date <= latest_close["date"]:
        source_date = latest_close["date"]
    source_time = _iso_minutes(datetime.combine(now_et.date(), time(0, 0), tzinfo=ET).astimezone(JST))
    return _input_from_gspc_value(
        "GSPC前日終値",
        "previous_close",
        source_date,
        source_time,
        latest_close["close"],
    )


def _point_price(point: dict[str, Any]) -> float | None:
    return finite_or_none(point.get("close")) or finite_or_none(point.get("open"))


def _last_point_between(chart: dict[str, Any], date_et: datetime, start: time, end: time) -> dict[str, Any] | None:
    selected = None
    for point in chart.get("points") or []:
        ts = point.get("ts")
        price = _point_price(point)
        if ts is None or price is None:
            continue
        dt_et = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC")).astimezone(ET)
        if dt_et.date() == date_et.date() and start <= dt_et.time() < end:
            selected = point
    return selected


def _first_point_between(chart: dict[str, Any], date_et: datetime, start: time, end: time) -> dict[str, Any] | None:
    for point in chart.get("points") or []:
        ts = point.get("ts")
        price = _point_price(point)
        if ts is None or price is None:
            continue
        dt_et = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC")).astimezone(ET)
        if dt_et.date() == date_et.date() and start <= dt_et.time() < end:
            return point
    return None


def _gspc_from_spy(spy_price: float, spy_previous_close: float, gspc_previous_close: float) -> float:
    return gspc_previous_close * (spy_price / spy_previous_close)


def _premarket_proxy(now_et: datetime | None = None) -> dict[str, Any] | None:
    now_et = now_et or datetime.now(ET)
    spy = _yahoo_chart("SPY")
    if not spy or spy["previous_close"] is None:
        return None
    premarket_point = _last_point_between(spy, now_et, time(4, 0), time(9, 30))
    if premarket_point is None:
        return None
    spy_price = _point_price(premarket_point)
    if spy_price is None:
        return None
    gspc = _yahoo_chart("^GSPC")
    tqqq = _yahoo_chart("TQQQ")
    gspc_previous_close = None
    if gspc:
        gspc_previous_close = gspc.get("previous_close") or gspc.get("regular_market_price")
    if gspc_previous_close is None:
        history = _gspc_close_history()
        gspc_previous_close = history[-1] if history else None
    if gspc_previous_close is None:
        return None
    implied_gspc_open = _gspc_from_spy(spy_price, spy["previous_close"], gspc_previous_close)
    source_dt_jst = datetime.fromtimestamp(premarket_point["ts"], tz=ZoneInfo("UTC")).astimezone(JST)
    source_date = source_dt_jst.astimezone(ET).strftime("%Y-%m-%d")
    previous_closes = _gspc_close_history(source_date)
    rsi = _rsi_wilder(previous_closes + [implied_gspc_open])
    bbz = _bb20_z(previous_closes, implied_gspc_open)
    return {
        "mode": "live_premarket_proxy",
        "label": "SPY pre-marketから推定",
        "source_time_jst": _iso_minutes(source_dt_jst),
        "source_date": source_date,
        "gspc_open": implied_gspc_open,
        "tqqq_open": tqqq.get("last_price") if tqqq else None,
        "rsi": rsi,
        "bb20_z": bbz,
        "notes": [
            "GSPC入力値は、SPY pre-market価格の前日終値比から推定しています。",
            "Implied RSI (14) と BB20 Z は、前日までのGSPC終値に推定GSPC入力値を1点追加して再計算しています。",
        ],
    }


def _today_open_proxy(now_et: datetime | None = None) -> dict[str, Any] | None:
    now_et = now_et or datetime.now(ET)
    gspc = _yahoo_chart("^GSPC")
    source_point = _first_point_between(gspc, now_et, time(9, 30), time(16, 0)) if gspc else None
    gspc_open = _point_price(source_point) if source_point else None
    source_ts = source_point.get("ts") if source_point else None
    if gspc_open is None:
        rows = _read_rows(GSPC_OHLC_PATH)
        today = now_et.strftime("%Y-%m-%d")
        row = next((item for item in reversed(rows) if item.get("Date") == today), None)
        if row:
            gspc_open = finite_or_none(row.get("GSPC_OPEN"))
            source_ts = int(datetime.combine(now_et.date(), time(9, 30), tzinfo=ET).timestamp())
    if gspc_open is None or source_ts is None:
        return None
    tqqq = _yahoo_chart("TQQQ")
    tqqq_point = _first_point_between(tqqq, now_et, time(9, 30), time(16, 0)) if tqqq else None
    source_dt_jst = datetime.fromtimestamp(source_ts, tz=ZoneInfo("UTC")).astimezone(JST)
    proxy = _input_from_gspc_value(
        "Today GSPC open",
        "today_open",
        source_dt_jst.astimezone(ET).strftime("%Y-%m-%d"),
        _iso_minutes(source_dt_jst),
        gspc_open,
    )
    if proxy is None:
        return None
    proxy["tqqq_open"] = _point_price(tqqq_point) if tqqq_point else None
    return proxy


def _base_position(base_regime: str) -> str:
    return "TMF 50% / GLD 50%" if base_regime == "wait_mix" else "TQQQ"


def _active_entry(rows: list[dict[str, str]], leg: str) -> dict[str, str] | None:
    if not rows or rows[-1].get("selected_leg") != leg:
        return None
    start = len(rows) - 1
    while start > 0 and rows[start - 1].get("selected_leg") == leg:
        start -= 1
    return rows[start]


def _latest_action(latest: dict[str, Any], summary: dict[str, Any], entry: dict[str, Any] | None) -> dict[str, Any]:
    leg = latest.get("selected_leg") or "-"
    action = latest.get("action") or ""
    rsi = finite_or_none(latest.get("gspc_open_implied_rsi14"))
    bbz = finite_or_none(latest.get("GSPC_BB20_Z"))
    gspc_open = finite_or_none(latest.get("GSPC_OPEN"))
    base_position = _base_position(latest.get("base_target_regime_at_open", ""))

    entry_rsi = finite_or_none(summary.get("uvix_entry_rsi")) or 67.5
    entry_bbz = finite_or_none(summary.get("uvix_entry_min_bb_z")) or 1.6
    exit_rsi = finite_or_none(summary.get("uvix_exit_rsi")) or 66.0
    gamma = finite_or_none(summary.get("uvix_gspc_profit_exit_pct")) or 0.1

    if leg == "UVIX":
        entry_gspc = finite_or_none(entry.get("GSPC_OPEN")) if entry else None
        gspc_trigger = entry_gspc * (1.0 + gamma / 100.0) if entry_gspc is not None else None
        exit_rsi_hit = rsi is not None and rsi <= exit_rsi
        gspc_profit_hit = gspc_open is not None and gspc_trigger is not None and gspc_open <= gspc_trigger
        reasons = []
        if entry is not None:
            reasons.append(f"高RSI UVIX最優先ルールは {entry.get('Date') or entry.get('date')} に発動しています。")
        if exit_rsi_hit:
            reasons.append(f"Implied RSI (14)終了条件に到達: {rsi:.2f} <= {exit_rsi:g}。")
        if gspc_profit_hit and gspc_trigger is not None:
            reasons.append(f"GSPC利確終了条件に到達: 始値 {gspc_open:.2f} <= 判定値 {gspc_trigger:.2f}。")
        if exit_rsi_hit or gspc_profit_hit:
            reasons.append("同じ始値では高RSI UVIX最優先ルールへ入り直さず、その日の基本ポジションへ戻ります。")
            return {
                "headline": f"{base_position}へ切り替え",
                "position": base_position,
                "action": action or "exit_uvix_live_check",
                "status": "exit_uvix",
                "reasons": reasons,
                "exit_checks": {
                    "rsi_exit": exit_rsi_hit,
                    "gspc_profit_exit": gspc_profit_hit,
                    "gspc_profit_trigger": gspc_trigger,
                },
            }
        if not exit_rsi_hit:
            reasons.append(f"Implied RSI (14)終了条件は未達: {rsi:.2f} > {exit_rsi:g}。")
        if not gspc_profit_hit and gspc_trigger is not None:
            reasons.append(f"GSPC利確終了条件は未達: 始値 {gspc_open:.2f} > 判定値 {gspc_trigger:.2f}。")
        return {
            "headline": "UVIXを継続保有",
            "position": "UVIX",
            "action": action or "hold_uvix",
            "status": "active_uvix",
            "reasons": reasons,
            "exit_checks": {
                "rsi_exit": exit_rsi_hit,
                "gspc_profit_exit": gspc_profit_hit,
                "gspc_profit_trigger": gspc_trigger,
            },
        }

    if leg in {"low_rsi_tqqq_override", "low_rsi_tqqq_priority"}:
        low_exit = finite_or_none(summary.get("low_rsi_exit")) or 32.5
        return {
            "headline": "TQQQを継続保有",
            "position": "TQQQ",
            "action": action or "hold_low_rsi_tqqq_priority",
            "status": "active_low_rsi_priority",
            "reasons": [f"低RSI TQQQ最優先ルールが発動中です。Implied RSI (14) >= {low_exit:g} で終了します。"],
            "exit_checks": {"low_rsi_exit": rsi is not None and rsi >= low_exit},
        }

    if action.startswith("enter_uvix") or (rsi is not None and bbz is not None and rsi >= entry_rsi and bbz >= entry_bbz):
        return {
            "headline": "UVIXへ切り替え",
            "position": "UVIX",
            "action": action or "enter_uvix_high_rsi_bb20z",
            "status": "enter_uvix",
            "reasons": [f"RSI {rsi:.2f} >= {entry_rsi:g}.", f"BB20Z {bbz:.2f} >= {entry_bbz:g}."],
            "exit_checks": {},
        }

    return {
        "headline": f"{base_position}を継続保有",
        "position": base_position,
        "action": action or "hold_base",
        "status": "base",
        "reasons": [f"高RSI UVIX最優先ルールは現在の判定始値では発動していません。現在のポジションは {leg} です。"],
        "exit_checks": {},
    }


def _choose_source(mode: str, phase: str, now_et: datetime) -> dict[str, Any] | None:
    if mode == "previous_close":
        return _previous_close_proxy(now_et)
    if mode == "premarket":
        if not _mode_availability(now_et)["premarket"]:
            return {
                "mode": "premarket_unavailable",
                "label": "pre-market判定は利用不可",
                "source_time_jst": None,
                "notes": ["現在のNY営業日のpre-marketがまだ始まっていません。"],
                "disabled": True,
            }
        return _premarket_proxy(now_et)
    if mode == "today_open":
        if not _mode_availability(now_et)["today_open"]:
            return {
                "mode": "today_open_unavailable",
                "label": "本日始値判定は利用不可",
                "source_time_jst": None,
                "notes": ["通常取引開始前のため、本日始値はまだ利用できません。"],
                "disabled": True,
            }
        return _today_open_proxy(now_et)
    if mode == "latest":
        availability = _mode_availability(now_et)
        if availability["today_open"]:
            return _today_open_proxy(now_et)
        if phase == "premarket" or availability["premarket"]:
            return _premarket_proxy(now_et)
        return _previous_close_proxy(now_et)
    return None


def build_position_dashboard_payload(mode: str = "latest", variant: str = DEFAULT_VARIANT) -> dict[str, Any]:
    spec, daily_path, summary_path = _variant_paths(variant)
    selected_variant = variant if variant in CANONICAL_VARIANTS else DEFAULT_VARIANT
    rows = _read_rows(daily_path)
    if not rows:
        raise RuntimeError(f"No rows in {daily_path}")
    summary = _load_summary(summary_path)
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    uvix_entry = _active_entry(rows, "UVIX")
    low_rsi_entry = _active_entry(rows, "low_rsi_tqqq_priority") or _active_entry(rows, "low_rsi_tqqq_override")
    active_entry = uvix_entry or low_rsi_entry
    now_jst = datetime.now(JST)
    now_et = now_jst.astimezone(ET)
    phase = _market_phase(now_et)
    availability = _mode_availability(now_et)
    selected_mode = mode if mode in availability else "latest"
    source: dict[str, Any] = {
        "generated_at_jst": _iso_minutes(now_jst),
        "market_time_et": now_et.strftime("%Y-%m-%d %H:%M ET"),
        "market_phase": phase,
        "mode": "canonical_csv",
        "selected_mode": selected_mode,
        "label": "Canonical CSV latest row",
        "source_time_jst": _ny_open_as_jst(latest.get("Date")),
        "notes": [],
    }

    effective_latest: dict[str, Any] = dict(latest)
    if selected_mode != "canonical_csv":
        proxy = _choose_source(selected_mode, phase, now_et)
        if (
            proxy
            and not proxy.get("disabled")
            and proxy.get("gspc_open") is not None
            and proxy.get("rsi") is not None
            and proxy.get("bb20_z") is not None
        ):
            effective_latest.update(
                {
                    "Date": proxy["source_date"],
                    "gspc_open_implied_rsi14": proxy["rsi"],
                    "GSPC_BB20_Z": proxy["bb20_z"],
                    "GSPC_OPEN": proxy["gspc_open"],
                    "TQQQ_OPEN": proxy.get("tqqq_open") or effective_latest.get("TQQQ_OPEN"),
                    "action": "",
                }
            )
            source.update(proxy)
            source["selected_mode"] = selected_mode
        else:
            if proxy:
                source.update(proxy)
            else:
                source["mode"] = "canonical_csv_fallback"
                source["label"] = "カノニカルCSV最終行。ライブ入力値は利用不可"
                source["notes"] = [f"{selected_mode} data could not be fetched; falling back to canonical CSV."]
            source["selected_mode"] = selected_mode

    decision = _latest_action(effective_latest, summary, active_entry)

    chart_history = _build_chart_history(30)
    chart_current: dict[str, Any] | None = None
    src_date = effective_latest.get("Date")
    src_open = finite_or_none(effective_latest.get("GSPC_OPEN"))
    if src_date and src_open is not None:
        prev_c = _gspc_close_history(src_date)
        if len(prev_c) >= 20:
            bb20_win = prev_c[-20:]
            bb20_mean = sum(bb20_win) / 20
            bb20_var = sum((v - bb20_mean) ** 2 for v in bb20_win) / 20
            bb20_std = math.sqrt(bb20_var) if bb20_var > 0 else 0.0
            bb20_upper = bb20_mean + 1.6 * bb20_std
            rsi_c = _rsi_wilder(prev_c + [src_open])
            if not chart_history or src_date > chart_history[-1]["date"]:
                chart_current = {
                    "date": src_date,
                    "source_time_jst": source.get("source_time_jst"),
                    "gspc_open": src_open,
                    "gspc_close": None,
                    "bb20_upper": bb20_upper,
                    "rsi14": rsi_c,
                    "is_current": True,
                }

    def compact(row: dict[str, str] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "date": row.get("Date"),
            "rsi": finite_or_none(row.get("gspc_open_implied_rsi14")),
            "bb20_z": finite_or_none(row.get("GSPC_BB20_Z")),
            "gspc_open": finite_or_none(row.get("GSPC_OPEN")),
            "tqqq_open": finite_or_none(row.get("TQQQ_OPEN")),
            "base_regime": row.get("base_target_regime_at_open"),
            "selected_leg": row.get("selected_leg"),
            "action": row.get("action") or "",
            "skip_reason": row.get("skip_reason") or "",
            "strategy_equity": finite_or_none(row.get("strategy_equity")),
            "strategy_return": finite_or_none(row.get("strategy_return")),
        }

    return {
        "title": "Canonical position dashboard",
        "variant": selected_variant,
        "variant_label": spec["label"],
        "available_variants": {
            key: {"label": value["label"], "start": value["start"]} for key, value in CANONICAL_VARIANTS.items()
        },
        "generated_from": str(daily_path.relative_to(REPO_DIR)),
        "source": source,
        "modes": {
            "selected": selected_mode,
            "availability": availability,
            "labels": {
                "latest": "最新情報で判断",
                "previous_close": "前日終値で判断",
                "premarket": "pre-marketで判断",
                "today_open": "本日始値で判断",
            },
        },
        "latest": compact(latest),
        "decision_input": compact(effective_latest),
        "previous": compact(previous),
        "active_entry": compact(active_entry),
        "decision": decision,
        "chart_history": chart_history,
        "chart_current": chart_current,
        "summary": summary,
        "rules": {
            "取引タイミング": "現canonicalは当日始値を判断入力として使い、その同じ当日始値で1回だけ乗り換える。前日終値から当日始値までのリターンは前日から持っていたポジションで受け、当日始値から終値までのリターンは乗り換え後のポジションで受ける。",
            "判断時点": "高RSI UVIX、低RSI TQQQ、SMA160、直前ピーク基準ドローダウンα%はいずれも当日始値参照。2010開始の固定パラメータ比較では、前日終値参照版CAGR 108.40%に対して、当日始値参照版CAGR 153.45%だった。",
            "基本ポジション": "GSPCがSMA160以上ならTQQQ。GSPCがSMA160を下回った直後は安全資産としてTMF 50% / GLD 50%。",
            "TQQQ再エントリー": f"安全資産中にTQQQ始値が直前ピークからα%以上下落したらTQQQを拾う。この開始日版ではCAGR最大化でα = {finite_or_none(summary.get('alpha_drawdown_pct')):g}%。",
            "高RSI UVIX最優先ルール": "Implied RSI (14) >= 67.5 かつ GSPC BB20 Z >= 1.6 なら、基本ポジションより優先してUVIXへ乗り換える。",
            "高RSI UVIX終了条件": "Implied RSI (14) <= 66.0、またはGSPC始値 <= 高RSI UVIX発動時のGSPC始値 +0.1% でUVIXを終了する。",
            "低RSI TQQQ最優先ルール": "安全資産中にImplied RSI (14) < 30.0ならTQQQへ乗り換え、32.5以上で終了する。",
        },
    }


def position_dashboard_site_payload() -> dict[str, Any]:
    return {
        "selected_variant": DEFAULT_VARIANT,
        "available_variants": {
            key: {"label": value["label"], "start": value["start"]} for key, value in CANONICAL_VARIANTS.items()
        },
        "variants": {key: build_position_dashboard_payload(variant=key) for key in CANONICAL_VARIANTS},
    }


def position_dashboard_json() -> str:
    return json.dumps(position_dashboard_site_payload(), ensure_ascii=False, separators=(",", ":"))
