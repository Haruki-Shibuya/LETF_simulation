#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import statistics
import time
import urllib.request
from bisect import bisect_left
from datetime import date, datetime
from pathlib import Path

from canonical_chart_data import build_canonical_chart_payload


REPO_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_DIR / "output"
CACHE_DIR = OUTPUT_DIR / "sec_submissions_cache"

TOP5 = {
    "NVDA": ["0001045810"],
    "AAPL": ["0000320193"],
    "MSFT": ["0000789019"],
    "AMZN": ["0001018724"],
    "GOOGL": ["0001288776", "0001652044"],
}

SEC_USER_AGENT = "Haruki Shibuya event-study research haruki@example.com"


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def fetch_sec_submissions(ticker: str, cik: str) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker}_{cik}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read().decode("utf-8")
    cache_path.write_text(data, encoding="utf-8")
    return json.loads(data)


def fetch_sec_submission_file(ticker: str, file_name: str) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker}_{file_name}"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    url = f"https://data.sec.gov/submissions/{file_name}"
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    last_error = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read().decode("utf-8")
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"failed to fetch SEC file {file_name}") from last_error
    cache_path.write_text(data, encoding="utf-8")
    return json.loads(data)


def iter_sec_filing_blocks(ticker: str, cik: str):
    data = fetch_sec_submissions(ticker, cik)
    yield data["filings"]["recent"]
    for file_info in data["filings"].get("files", []):
        name = file_info.get("name")
        if name:
            yield fetch_sec_submission_file(ticker, name)


def sec_filing_dates(ticker: str, cik: str, start: date, end: date) -> list[dict]:
    rows = []
    seen = set()
    for block in iter_sec_filing_blocks(ticker, cik):
        for form, filing_date, report_date, accession in zip(
            block.get("form", []),
            block.get("filingDate", []),
            block.get("reportDate", []),
            block.get("accessionNumber", []),
        ):
            if form not in {"10-Q", "10-K"}:
                continue
            d = parse_date(filing_date)
            key = (ticker, filing_date, form, accession)
            if key in seen or not (start <= d <= end):
                continue
            seen.add(key)
            rows.append(
                {
                    "ticker": ticker,
                    "event_date": d.isoformat(),
                    "form": form,
                    "report_date": report_date,
                    "accession": accession,
                    "source": "SEC submissions filingDate",
                }
            )
    rows.sort(key=lambda row: row["event_date"])
    return rows


def nearest_trading_index(trading_dates: list[date], event: date) -> int | None:
    idx = bisect_left(trading_dates, event)
    if idx >= len(trading_dates):
        return None
    return idx


def load_episodes(variant: str) -> tuple[list[dict], list[date]]:
    payload = build_canonical_chart_payload(variant)
    trading_dates = [parse_date(d) for d in payload["dates"]]
    date_to_idx = {d: i for i, d in enumerate(trading_dates)}
    episodes = []
    for i, span in enumerate(payload["spans"], start=1):
        start = parse_date(span["start"])
        end = parse_date(span["end"])
        tqqq_return = span["exit_tqqq_open"] / span["entry_tqqq_open"] - 1.0
        uvix_return = span["uvix_return"]
        episodes.append(
            {
                "variant": variant,
                "episode": i,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "start_idx": date_to_idx[start],
                "end_idx": date_to_idx[end],
                "days": span["days"],
                "uvix_return": uvix_return,
                "tqqq_return": tqqq_return,
                "uvix_minus_tqqq_return": uvix_return - tqqq_return,
                "entry_rsi": span["entry_rsi"],
                "exit_rsi": span["exit_rsi"],
                "exit_reason": span["exit_reason"],
            }
        )
    return episodes, trading_dates


def summarize(values: list[float]) -> dict:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "stdev": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "positive_rate": sum(1 for x in values if x > 0) / len(values),
    }


def welch_t(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    va = statistics.variance(a)
    vb = statistics.variance(b)
    denom = (va / len(a) + vb / len(b)) ** 0.5
    if denom == 0:
        return None
    return (statistics.fmean(a) - statistics.fmean(b)) / denom


def run_variant(variant: str, all_event_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    episodes, trading_dates = load_episodes(variant)
    start = parse_date(episodes[0]["start"])
    end = parse_date(episodes[-1]["end"])
    event_rows = [row for row in all_event_rows if start <= parse_date(row["event_date"]) <= end]
    event_indices = []
    for row in event_rows:
        idx = nearest_trading_index(trading_dates, parse_date(row["event_date"]))
        if idx is not None:
            event_indices.append((idx, row))

    episode_rows = []
    summary_rows = []
    for window in [0, 1, 3, 5]:
        flagged = []
        unflagged = []
        for ep in episodes:
            matched = [
                row
                for idx, row in event_indices
                if ep["start_idx"] - window <= idx <= ep["end_idx"] + window
            ]
            spread = ep["uvix_minus_tqqq_return"]
            (flagged if matched else unflagged).append(spread)
            episode_rows.append(
                {
                    **{k: v for k, v in ep.items() if not k.endswith("_idx")},
                    "window_trading_days": window,
                    "top5_earnings_window": bool(matched),
                    "matched_tickers": ",".join(sorted({m["ticker"] for m in matched})),
                    "matched_event_dates": ",".join(sorted({m["event_date"] for m in matched})),
                }
            )

        flagged_stats = summarize(flagged)
        unflagged_stats = summarize(unflagged)
        summary_rows.append(
            {
                "variant": variant,
                "window_trading_days": window,
                "event_episode_count": flagged_stats["n"],
                "non_event_episode_count": unflagged_stats["n"],
                "event_mean_spread": flagged_stats["mean"],
                "non_event_mean_spread": unflagged_stats["mean"],
                "event_minus_non_event_mean": None
                if flagged_stats["mean"] is None or unflagged_stats["mean"] is None
                else flagged_stats["mean"] - unflagged_stats["mean"],
                "event_median_spread": flagged_stats["median"],
                "non_event_median_spread": unflagged_stats["median"],
                "event_minus_non_event_median": None
                if flagged_stats["median"] is None or unflagged_stats["median"] is None
                else flagged_stats["median"] - unflagged_stats["median"],
                "event_stdev": flagged_stats["stdev"],
                "non_event_stdev": unflagged_stats["stdev"],
                "event_positive_rate": flagged_stats["positive_rate"],
                "non_event_positive_rate": unflagged_stats["positive_rate"],
                "welch_t_event_minus_non_event": welch_t(flagged, unflagged),
            }
        )
    return episode_rows, summary_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    all_events = []
    for ticker, ciks in TOP5.items():
        for cik in ciks:
            all_events.extend(sec_filing_dates(ticker, cik, date(2005, 1, 1), date(2026, 12, 31)))
    write_csv(OUTPUT_DIR / "top5_tqqq_equity_sec_10q_10k_event_dates.csv", all_events)

    all_episode_rows = []
    all_summary_rows = []
    for variant in ["2005", "2010"]:
        episode_rows, summary_rows = run_variant(variant, all_events)
        all_episode_rows.extend(episode_rows)
        all_summary_rows.extend(summary_rows)

    write_csv(OUTPUT_DIR / "uvix_tqqq_spread_top5_earnings_event_study_episodes.csv", all_episode_rows)
    write_csv(OUTPUT_DIR / "uvix_tqqq_spread_top5_earnings_event_study_summary.csv", all_summary_rows)

    print("Top5 tickers:", ", ".join(TOP5))
    print("Saved event dates:", OUTPUT_DIR / "top5_tqqq_equity_sec_10q_10k_event_dates.csv")
    print("Saved episode rows:", OUTPUT_DIR / "uvix_tqqq_spread_top5_earnings_event_study_episodes.csv")
    print("Saved summary:", OUTPUT_DIR / "uvix_tqqq_spread_top5_earnings_event_study_summary.csv")
    for row in all_summary_rows:
        print(
            row["variant"],
            f"w={row['window_trading_days']}",
            f"n={row['event_episode_count']}/{row['non_event_episode_count']}",
            f"mean_diff={row['event_minus_non_event_mean']:.4f}"
            if row["event_minus_non_event_mean"] is not None
            else "mean_diff=NA",
            f"median_diff={row['event_minus_non_event_median']:.4f}"
            if row["event_minus_non_event_median"] is not None
            else "median_diff=NA",
        )


if __name__ == "__main__":
    main()
