from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "output"
TRADING_DAYS = 252

CANONICAL_2005_PATH = (
    OUTPUT_DIR
    / "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220_daily_path.csv"
)
CANONICAL_2010_PATH = (
    OUTPUT_DIR
    / "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_daily_path.csv"
)
VALUATION_DAILY_PATH = OUTPUT_DIR / "valuation_forward_pe_daily.csv"
MARKET_OHLC_PATH = OUTPUT_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"
UVIX_OHLC_PATH = REPO_DIR / "uvix_backtest" / "output" / "uvix_ohlc_series.csv"


def compute_metrics(returns: pd.Series) -> dict[str, float]:
    returns = returns.astype(float).clip(lower=-0.999999)
    equity = (1.0 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    mean = returns.mean()
    vol = returns.std(ddof=0) * np.sqrt(TRADING_DAYS)
    return {
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "annualized_vol": float(vol),
        "max_drawdown": float((equity / equity.cummax() - 1.0).min()),
        "final_multiple": float(equity.iloc[-1]),
        "cagr_over_vol": float((equity.iloc[-1] ** (1.0 / years) - 1.0) / vol) if vol else np.nan,
    }


def normalize_state(state: str) -> str:
    if state in {"TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"}:
        return "TQQQ"
    if state == "UVIX":
        return "UVIX"
    return "wait_mix"


def load_frame(path: Path) -> pd.DataFrame:
    canonical = pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()
    valuation = pd.read_csv(VALUATION_DAILY_PATH, parse_dates=["date"]).rename(columns={"date": "Date"}).set_index("Date")
    market = pd.read_csv(MARKET_OHLC_PATH, parse_dates=["Date"]).set_index("Date")
    uvix = pd.read_csv(UVIX_OHLC_PATH, parse_dates=["Date"]).set_index("Date")

    frame = canonical[["selected_leg", "base_target_regime_at_open"]].join(
        valuation[["sp500_forward_pe", "qqq_forward_pe"]],
        how="inner",
    )
    frame = frame.join(
        market[
            [
                "TQQQ_CTO_RETURN",
                "TQQQ_OTC_RETURN",
                "TMF_CTO_RETURN",
                "TMF_OTC_RETURN",
                "GLD_CTO_RETURN",
                "GLD_OTC_RETURN",
            ]
        ],
        how="inner",
    )
    frame = frame.join(uvix[["UVIX_CTO_RETURN", "UVIX_OTC_RETURN"]], how="inner")
    return frame.dropna().copy()


def leg_return(frame: pd.DataFrame, state: pd.Series, suffix: str) -> pd.Series:
    normalized = state.astype(str).map(normalize_state)
    wait = 0.5 * frame[f"TMF_{suffix}_RETURN"] + 0.5 * frame[f"GLD_{suffix}_RETURN"]
    return pd.Series(
        np.select(
            [normalized.eq("UVIX"), normalized.eq("TQQQ")],
            [frame[f"UVIX_{suffix}_RETURN"], frame[f"TQQQ_{suffix}_RETURN"]],
            default=wait,
        ),
        index=frame.index,
        dtype=float,
    )


def simulate(frame: pd.DataFrame, selected: pd.Series) -> tuple[dict[str, float], pd.DataFrame]:
    selected = selected.astype(str)
    previous = selected.shift(1)
    previous.iloc[0] = selected.iloc[0]
    returns = (1.0 + leg_return(frame, previous, "CTO")) * (1.0 + leg_return(frame, selected, "OTC")) - 1.0
    metrics = compute_metrics(returns)
    out = frame[["selected_leg", "base_target_regime_at_open", "sp500_forward_pe", "qqq_forward_pe"]].copy()
    out["filtered_leg"] = selected
    out["strategy_return"] = returns
    out["strategy_equity"] = (1.0 + returns.clip(lower=-0.999999)).cumprod()
    return metrics, out


def base_series(frame: pd.DataFrame) -> pd.Series:
    return frame["base_target_regime_at_open"].where(frame["base_target_regime_at_open"].eq("wait_mix"), "TQQQ")


def replace_tqqq_with_wait(selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    out.loc[mask & selected.isin(["TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"])] = "wait_mix"
    return out


def replace_wait_with_tqqq(selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    out.loc[mask & selected.eq("wait_mix")] = "TQQQ"
    return out


def replace_uvix_with_base(frame: pd.DataFrame, selected: pd.Series, mask: pd.Series) -> pd.Series:
    out = selected.copy()
    out.loc[mask & selected.eq("UVIX")] = base_series(frame).loc[mask & selected.eq("UVIX")]
    return out


@dataclass(frozen=True)
class Trial:
    name: str
    params: dict[str, float]
    apply: Callable[[pd.DataFrame], pd.Series]


def build_trials(frame: pd.DataFrame) -> list[Trial]:
    sp_grid = np.round(np.arange(12.0, 24.51, 0.5), 2)
    q_grid = np.round(np.arange(16.0, 32.51, 0.5), 2)
    trials: list[Trial] = [
        Trial("baseline", {}, lambda f: f["selected_leg"].copy()),
    ]

    for th in sp_grid:
        trials.append(
            Trial(
                "sp500_high_pe_tqqq_to_wait",
                {"sp500_pe_max": float(th)},
                lambda f, th=th: replace_tqqq_with_wait(f["selected_leg"], f["sp500_forward_pe"] > th),
            )
        )
        trials.append(
            Trial(
                "sp500_low_pe_wait_to_tqqq",
                {"sp500_pe_min": float(th)},
                lambda f, th=th: replace_wait_with_tqqq(f["selected_leg"], f["sp500_forward_pe"] < th),
            )
        )
        trials.append(
            Trial(
                "sp500_low_pe_only_uvix",
                {"sp500_uvix_pe_min": float(th)},
                lambda f, th=th: replace_uvix_with_base(f, f["selected_leg"], f["sp500_forward_pe"] < th),
            )
        )
        trials.append(
            Trial(
                "sp500_high_pe_block_uvix",
                {"sp500_uvix_pe_max": float(th)},
                lambda f, th=th: replace_uvix_with_base(f, f["selected_leg"], f["sp500_forward_pe"] > th),
            )
        )

    for th in q_grid:
        trials.append(
            Trial(
                "qqq_high_pe_tqqq_to_wait",
                {"qqq_pe_max": float(th)},
                lambda f, th=th: replace_tqqq_with_wait(f["selected_leg"], f["qqq_forward_pe"] > th),
            )
        )
        trials.append(
            Trial(
                "qqq_low_pe_wait_to_tqqq",
                {"qqq_pe_min": float(th)},
                lambda f, th=th: replace_wait_with_tqqq(f["selected_leg"], f["qqq_forward_pe"] < th),
            )
        )
        trials.append(
            Trial(
                "qqq_low_pe_only_uvix",
                {"qqq_uvix_pe_min": float(th)},
                lambda f, th=th: replace_uvix_with_base(f, f["selected_leg"], f["qqq_forward_pe"] < th),
            )
        )
        trials.append(
            Trial(
                "qqq_high_pe_block_uvix",
                {"qqq_uvix_pe_max": float(th)},
                lambda f, th=th: replace_uvix_with_base(f, f["selected_leg"], f["qqq_forward_pe"] > th),
            )
        )

    for sp in np.round(np.arange(14.0, 23.51, 0.5), 2):
        for q in np.round(np.arange(18.0, 31.51, 0.5), 2):
            trials.append(
                Trial(
                    "either_high_pe_tqqq_to_wait",
                    {"sp500_pe_max": float(sp), "qqq_pe_max": float(q)},
                    lambda f, sp=sp, q=q: replace_tqqq_with_wait(
                        f["selected_leg"], (f["sp500_forward_pe"] > sp) | (f["qqq_forward_pe"] > q)
                    ),
                )
            )
            trials.append(
                Trial(
                    "both_low_pe_wait_to_tqqq",
                    {"sp500_pe_min": float(sp), "qqq_pe_min": float(q)},
                    lambda f, sp=sp, q=q: replace_wait_with_tqqq(
                        f["selected_leg"], (f["sp500_forward_pe"] < sp) & (f["qqq_forward_pe"] < q)
                    ),
                )
            )
            trials.append(
                Trial(
                    "combined_high_block_low_add",
                    {"sp500_pe_max": float(sp), "qqq_pe_max": float(q), "sp500_pe_min": float(sp - 2), "qqq_pe_min": float(q - 2)},
                    lambda f, sp=sp, q=q: replace_wait_with_tqqq(
                        replace_tqqq_with_wait(
                            f["selected_leg"], (f["sp500_forward_pe"] > sp) | (f["qqq_forward_pe"] > q)
                        ),
                        (f["sp500_forward_pe"] < sp - 2) & (f["qqq_forward_pe"] < q - 2),
                    ),
                )
            )

    return trials


def run_suite(label: str, path: Path) -> pd.DataFrame:
    frame = load_frame(path)
    rows: list[dict[str, object]] = []
    best_paths: dict[str, pd.DataFrame] = {}

    for trial in build_trials(frame):
        selected = trial.apply(frame)
        metrics, path_df = simulate(frame, selected)
        changed = selected.ne(frame["selected_leg"])
        rows.append(
            {
                "period": label,
                "trial": trial.name,
                **trial.params,
                **metrics,
                "start": frame.index.min().date().isoformat(),
                "end": frame.index.max().date().isoformat(),
                "days": int(len(frame)),
                "changed_days": int(changed.sum()),
                "changed_day_share": float(changed.mean()),
                "uvix_day_share": float(selected.eq("UVIX").mean()),
                "tqqq_day_share": float(selected.isin(["TQQQ", "low_rsi_tqqq_override", "low_rsi_tqqq_priority"]).mean()),
                "wait_day_share": float(selected.eq("wait_mix").mean()),
            }
        )
        key = f"{label}_{trial.name}"
        if key not in best_paths or metrics["cagr"] > best_paths[key].attrs["cagr"]:
            path_df.attrs["cagr"] = metrics["cagr"]
            best_paths[key] = path_df

    result = pd.DataFrame(rows)
    result = result.sort_values(["period", "cagr"], ascending=[True, False])
    result.to_csv(OUTPUT_DIR / f"forward_pe_filter_tests_{label}.csv", index=False)

    top = result.head(1).iloc[0]
    best_key = f"{label}_{top['trial']}"
    if best_key in best_paths:
        best_paths[best_key].to_csv(OUTPUT_DIR / f"forward_pe_filter_tests_{label}_best_daily_path.csv")
    return result


def main() -> None:
    results = pd.concat(
        [
            run_suite("from_20051220", CANONICAL_2005_PATH),
            run_suite("from_20100212", CANONICAL_2010_PATH),
        ],
        ignore_index=True,
    )
    results.to_csv(OUTPUT_DIR / "forward_pe_filter_tests_summary.csv", index=False)

    view_cols = [
        "period",
        "trial",
        "cagr",
        "annualized_vol",
        "max_drawdown",
        "cagr_over_vol",
        "changed_day_share",
        "sp500_pe_max",
        "qqq_pe_max",
        "sp500_pe_min",
        "qqq_pe_min",
        "sp500_uvix_pe_min",
        "qqq_uvix_pe_min",
        "sp500_uvix_pe_max",
        "qqq_uvix_pe_max",
    ]
    for period, group in results.groupby("period", sort=False):
        print(f"\\n=== {period} top CAGR ===")
        print(group.sort_values("cagr", ascending=False)[view_cols].head(15).to_string(index=False))
        baseline = group[group["trial"].eq("baseline")].iloc[0]
        print(
            "baseline "
            f"CAGR={baseline['cagr']*100:.2f}% "
            f"Vol={baseline['annualized_vol']*100:.2f}% "
            f"MDD={baseline['max_drawdown']*100:.2f}% "
            f"CAGR/Vol={baseline['cagr_over_vol']:.2f}"
        )
        print(f"\\n=== {period} top CAGR/Vol ===")
        print(group.sort_values("cagr_over_vol", ascending=False)[view_cols].head(15).to_string(index=False))
        print(f"\\n=== {period} lower vol with CAGR >= baseline ===")
        lv = group[group["cagr"] >= baseline["cagr"]].sort_values("annualized_vol")
        print(lv[view_cols].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
