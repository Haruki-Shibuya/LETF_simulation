from __future__ import annotations

import argparse
import json
import math
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
OUTPUT_DIR = BASE_DIR / "output"
CANONICAL_PATH = (
    OUTPUT_DIR
    / "canonical_prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212_daily_path.csv"
)
TQQQ_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"

UVIX_ENTRY_RSI = 69.5
UVIX_EXIT_RSI = 68.5
LOW_RSI_ENTRY = 30.0
LOW_RSI_EXIT = 32.5
TQQQ_DRAWDOWN_ALPHA = 54.5
RSI_PERIOD = 14
SMA_WINDOW = 160


@dataclass
class StrategyState:
    as_of: str
    selected_leg: str
    active_uvix: bool
    active_low_rsi_override: bool
    uvix_entry_tqqq_open: float | None
    tqqq_peak_open: float


def finite_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def read_canonical_state(current_position: str = "TQQQ", uvix_entry_tqqq_open: float | None = None) -> StrategyState:
    path = pd.read_csv(CANONICAL_PATH, parse_dates=["Date"]).sort_values("Date")
    tqqq = pd.read_csv(TQQQ_OHLC_PATH, parse_dates=["Date"]).sort_values("Date")
    merged = path.merge(tqqq[["Date", "TQQQ_OPEN"]], on="Date", how="left", suffixes=("", "_source"))
    if "TQQQ_OPEN_source" in merged.columns:
        merged["TQQQ_OPEN"] = merged["TQQQ_OPEN"].fillna(merged["TQQQ_OPEN_source"])

    last = merged.iloc[-1]
    active_uvix = current_position == "UVIX"
    active_low = current_position == "low_rsi_tqqq_override"

    return StrategyState(
        as_of=f"manual input; canonical path latest {pd.Timestamp(last['Date']).date().isoformat()}",
        selected_leg=current_position,
        active_uvix=active_uvix,
        active_low_rsi_override=active_low,
        uvix_entry_tqqq_open=uvix_entry_tqqq_open,
        tqqq_peak_open=float(merged["TQQQ_OPEN"].dropna().max()),
    )


def flatten_download(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        if ticker in frame.columns.get_level_values(-1):
            frame = frame.xs(ticker, axis=1, level=-1)
        else:
            frame.columns = frame.columns.get_level_values(0)
    return frame.dropna(how="all")


def download_daily(ticker: str, period: str = "2y") -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        timeout=12,
    )
    frame = flatten_download(frame, ticker)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame


def download_intraday(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(
        ticker,
        period="5d",
        interval="1m",
        auto_adjust=False,
        prepost=True,
        progress=False,
        threads=False,
        timeout=12,
    )
    frame = flatten_download(frame, ticker)
    if not frame.empty:
        frame.index = pd.to_datetime(frame.index)
    return frame


def wilder_rsi_from_open(prior_closes: pd.Series, open_value: float, period: int = RSI_PERIOD) -> float:
    series = pd.Series(prior_closes, dtype=float).dropna()
    if len(series) < period + 1:
        raise ValueError("not enough GSPC close history for RSI")
    synthetic = pd.concat([series, pd.Series([float(open_value)])], ignore_index=True)
    delta = synthetic.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return float((100.0 - 100.0 / (1.0 + rs)).iloc[-1])


def sma(prior_closes: pd.Series, window: int = SMA_WINDOW) -> float:
    values = pd.Series(prior_closes, dtype=float).dropna()
    if len(values) < window:
        raise ValueError("not enough GSPC close history for SMA")
    return float(values.iloc[-window:].mean())


def latest_price(frame: pd.DataFrame) -> float | None:
    if frame.empty or "Close" not in frame:
        return None
    close = frame["Close"].dropna()
    if close.empty:
        return None
    return float(close.iloc[-1])


def latest_intraday_price(ticker: str) -> float | None:
    try:
        return latest_price(download_intraday(ticker))
    except Exception:
        return None


def ny_now() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def market_is_open_now() -> bool:
    now = ny_now()
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def build_base_state(gspc_open: float, tqqq_open: float, prior_gspc_closes: pd.Series, tqqq_peak_open: float) -> dict:
    sma160 = sma(prior_gspc_closes)
    peak_with_candidate = max(float(tqqq_peak_open), float(tqqq_open))
    drawdown = 1.0 - float(tqqq_open) / peak_with_candidate
    above_sma = float(gspc_open) >= sma160
    bottom_pick = drawdown >= TQQQ_DRAWDOWN_ALPHA / 100.0
    if above_sma or bottom_pick:
        position = "TQQQ"
        reason = "GSPC Openが前日までのSMA160以上" if above_sma else "TQQQ Openがrunning peakからalpha%以上下落"
    else:
        position = "TMF 50% / GLD 50%"
        reason = "GSPC OpenがSMA160未満で、TQQQのalpha%底拾い条件も未達"
    return {
        "position": position,
        "reason": reason,
        "gspc_sma160": sma160,
        "tqqq_peak_open": peak_with_candidate,
        "tqqq_drawdown_pct": drawdown * 100.0,
        "above_sma": above_sma,
        "bottom_pick": bottom_pick,
    }


def decide_for_scenario(
    *,
    name: str,
    description: str,
    gspc_open: float,
    tqqq_open: float,
    prior_gspc_closes: pd.Series,
    state: StrategyState,
    data_notes: list[str],
) -> dict:
    rsi = wilder_rsi_from_open(prior_gspc_closes, gspc_open)
    base = build_base_state(gspc_open, tqqq_open, prior_gspc_closes, state.tqqq_peak_open)
    action = "hold_base"
    position = base["position"]
    applied_rule = "Base"
    reasons = [base["reason"]]

    if state.active_uvix:
        tqqq_exit = state.uvix_entry_tqqq_open is not None and tqqq_open <= state.uvix_entry_tqqq_open
        rsi_exit = rsi <= UVIX_EXIT_RSI
        if rsi_exit or tqqq_exit:
            position = base["position"]
            action = "exit_uvix"
            applied_rule = "UVIX exit"
            reasons = []
            if rsi_exit:
                reasons.append(f"RSI {rsi:.2f} <= {UVIX_EXIT_RSI}")
            if tqqq_exit:
                reasons.append(f"TQQQ Open {tqqq_open:.2f} <= UVIX entry TQQQ Open {state.uvix_entry_tqqq_open:.2f}")
            reasons.append(f"exit後はbase: {base['reason']}")
            # Practical dashboard rule: if exit is triggered, do not re-enter UVIX at the same open.
        else:
            position = "UVIX"
            action = "hold_uvix"
            applied_rule = "UVIX hold"
            reasons = [f"UVIX exit未達: RSI {rsi:.2f}, TQQQ Open {tqqq_open:.2f}"]
    elif state.active_low_rsi_override:
        if rsi >= LOW_RSI_EXIT:
            position = base["position"]
            action = "exit_low_rsi_tqqq_override"
            applied_rule = "Low-RSI TQQQ exit"
            reasons = [f"RSI {rsi:.2f} >= {LOW_RSI_EXIT}", f"exit後はbase: {base['reason']}"]
        else:
            position = "TQQQ"
            action = "hold_low_rsi_tqqq_override"
            applied_rule = "Low-RSI TQQQ hold"
            reasons = [f"RSI {rsi:.2f} < {LOW_RSI_EXIT} のためoverride継続"]
    else:
        if rsi >= UVIX_ENTRY_RSI:
            position = "UVIX"
            action = "enter_uvix"
            applied_rule = "UVIX entry"
            reasons = [f"RSI {rsi:.2f} >= {UVIX_ENTRY_RSI}"]
        elif base["position"].startswith("TMF") and rsi < LOW_RSI_ENTRY:
            position = "TQQQ"
            action = "enter_low_rsi_tqqq_override"
            applied_rule = "Low-RSI TQQQ entry"
            reasons = [f"baseは待機、かつ RSI {rsi:.2f} < {LOW_RSI_ENTRY}"]

    return {
        "name": name,
        "description": description,
        "position": position,
        "action": action,
        "applied_rule": applied_rule,
        "reasons": reasons,
        "data_notes": data_notes,
        "values": {
            "gspc_open": gspc_open,
            "tqqq_open": tqqq_open,
            "gspc_open_implied_rsi14": rsi,
            "gspc_sma160": base["gspc_sma160"],
            "tqqq_running_peak_open": base["tqqq_peak_open"],
            "tqqq_drawdown_pct": base["tqqq_drawdown_pct"],
            "uvix_entry_tqqq_open": state.uvix_entry_tqqq_open,
        },
    }


def build_scenarios(gspc_daily: pd.DataFrame, tqqq_daily: pd.DataFrame) -> tuple[pd.Series, list[dict]]:
    gspc_close = gspc_daily["Close"].dropna()
    tqqq_close = tqqq_daily["Close"].dropna()
    gspc_prev_close = float(gspc_close.iloc[-1])
    tqqq_prev_close = float(tqqq_close.iloc[-1])
    scenarios = [
        {
            "name": "前日Close据え置き",
            "description": "今夜のGSPC/TQQQ Openが前日Closeと同じだった場合",
            "gspc_open": gspc_prev_close,
            "tqqq_open": tqqq_prev_close,
            "notes": ["Open前の基準シナリオ", "GSPC/TQQQとも前日Closeを仮Openとして使用"],
        }
    ]

    tqqq_live = latest_intraday_price("TQQQ")
    spy_live = latest_intraday_price("SPY")
    spy_daily = None
    try:
        spy_daily = download_daily("SPY", period="10d")
    except Exception:
        spy_daily = None
    if spy_live is not None and spy_daily is not None and not spy_daily.empty:
        spy_prev_close = float(spy_daily["Close"].dropna().iloc[-1])
        implied_gspc = gspc_prev_close * (spy_live / spy_prev_close)
        scenarios.append(
            {
                "name": "SPY premarket/last示唆",
                "description": "SPYの最新値からGSPC Openを近似し、TQQQは最新値を使う場合",
                "gspc_open": implied_gspc,
                "tqqq_open": tqqq_live if tqqq_live is not None else tqqq_prev_close,
                "notes": ["GSPC現物にpremarketがないためSPYで近似", "TQQQは取得できた最新1分足を使用"],
            }
        )

    try:
        es_daily = download_daily("ES=F", period="10d")
        es_live = latest_intraday_price("ES=F")
        if es_live is not None and not es_daily.empty:
            es_prev_close = float(es_daily["Close"].dropna().iloc[-1])
            implied_gspc = gspc_prev_close * (es_live / es_prev_close)
            tqqq_guess = tqqq_live if tqqq_live is not None else tqqq_prev_close * (1.0 + 3.0 * (implied_gspc / gspc_prev_close - 1.0))
            scenarios.append(
                {
                    "name": "S&P futures示唆",
                    "description": "ES futuresの最新値からGSPC Openを近似する場合",
                    "gspc_open": implied_gspc,
                    "tqqq_open": tqqq_guess,
                    "notes": ["ES=FからGSPCを比率近似", "TQQQ最新値がなければ3倍近似を使用"],
                }
            )
    except Exception:
        pass

    if market_is_open_now():
        today = pd.Timestamp(ny_now().date())
        if today in gspc_daily.index and today in tqqq_daily.index:
            scenarios.insert(
                0,
                {
                    "name": "市場Open後の実Open",
                    "description": "今日の実際のGSPC/TQQQ Openを使う場合",
                    "gspc_open": float(gspc_daily.loc[today, "Open"]),
                    "tqqq_open": float(tqqq_daily.loc[today, "Open"]),
                    "notes": ["米国市場Open後のみ表示", "日足Openを使用"],
                },
            )

    return gspc_close, scenarios


def parse_state_params(query: dict[str, list[str]]) -> tuple[str, float | None]:
    current_position = query.get("current_position", ["TQQQ"])[0]
    if current_position not in {"TQQQ", "UVIX", "wait_mix", "low_rsi_tqqq_override"}:
        current_position = "TQQQ"
    uvix_entry = finite_or_none(query.get("uvix_entry_tqqq_open", [None])[0])
    return current_position, uvix_entry


def build_decision_payload(query: dict[str, list[str]] | None = None) -> dict:
    current_position, uvix_entry = parse_state_params(query or {})
    state = read_canonical_state(current_position=current_position, uvix_entry_tqqq_open=uvix_entry)
    gspc_daily = download_daily("^GSPC", period="2y")
    tqqq_daily = download_daily("TQQQ", period="2y")
    prior_gspc_closes, raw_scenarios = build_scenarios(gspc_daily, tqqq_daily)

    decisions = [
        decide_for_scenario(
            name=item["name"],
            description=item["description"],
            gspc_open=float(item["gspc_open"]),
            tqqq_open=float(item["tqqq_open"]),
            prior_gspc_closes=prior_gspc_closes,
            state=state,
            data_notes=list(item["notes"]),
        )
        for item in raw_scenarios
    ]

    return {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "ny_time": ny_now().isoformat(timespec="seconds"),
        "market_is_open": market_is_open_now(),
        "strategy": {
            "name": "prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit",
            "rules": {
                "base": f"GSPC Open vs previous Close SMA160; below SMA uses TMF/GLD unless TQQQ drawdown >= {TQQQ_DRAWDOWN_ALPHA}%",
                "uvix": f"entry RSI >= {UVIX_ENTRY_RSI}; exit RSI <= {UVIX_EXIT_RSI} or TQQQ Open <= entry-time TQQQ Open",
                "low_rsi": f"entry RSI < {LOW_RSI_ENTRY}; exit RSI >= {LOW_RSI_EXIT}",
            },
        },
        "detected_state": {
            "as_of": state.as_of,
            "selected_leg": state.selected_leg,
            "active_uvix": state.active_uvix,
            "active_low_rsi_override": state.active_low_rsi_override,
            "uvix_entry_tqqq_open": state.uvix_entry_tqqq_open,
            "tqqq_peak_open": state.tqqq_peak_open,
        },
        "scenarios": decisions,
        "disclaimer": "This dashboard displays the repository strategy output only; it is not financial advice.",
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/decision":
            self.respond_json(parse_qs(parsed.query))
            return
        self.respond_static(parsed.path)

    def respond_json(self, query: dict[str, list[str]]) -> None:
        try:
            payload = build_decision_payload(query)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (DASHBOARD_DIR / relative).resolve()
        if DASHBOARD_DIR.resolve() not in target.parents and target != DASHBOARD_DIR.resolve():
            self.send_error(403)
            return
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", ""} else args.host
    print(f"Dashboard: http://{display_host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
