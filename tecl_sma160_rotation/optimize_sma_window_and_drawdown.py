from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SIM_PATH = BASE_DIR / "simulate_tecl_sma160_rotation.py"


def load_sim_module():
    spec = importlib.util.spec_from_file_location("teclsim", SIM_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-start", default="1990-01-01")
    parser.add_argument("--fetch-end", default=None)
    parser.add_argument("--backtest-start", default="2002-01-01")
    parser.add_argument("--signal-source", choices=["underlier", "tecl", "gspc"], default="gspc")
    parser.add_argument(
        "--below-entry-mode",
        choices=["sma_drawdown", "crossunder_price_drawdown"],
        default="crossunder_price_drawdown",
    )
    parser.add_argument(
        "--below-entry-reference-source",
        choices=["signal", "tecl", "tqqq"],
        default="tqqq",
    )
    parser.add_argument("--below-soxl", type=float, default=0.0)
    parser.add_argument("--below-tecl", type=float, default=0.0)
    parser.add_argument("--below-tqqq", type=float, default=100.0)
    parser.add_argument("--above-tecl", type=float, default=0.0)
    parser.add_argument("--above-tqqq", type=float, default=100.0)
    parser.add_argument("--wait-tmf", type=float, default=50.0)
    parser.add_argument("--wait-gld", type=float, default=50.0)
    parser.add_argument("--m-min", type=int, default=50)
    parser.add_argument("--m-max", type=int, default=250)
    parser.add_argument("--m-step", type=int, default=5)
    parser.add_argument("--n-min", type=float, default=0.0)
    parser.add_argument("--n-max", type=float, default=60.0)
    parser.add_argument("--n-step", type=float, default=0.5)
    return parser.parse_args()


def build_output_stem(args: argparse.Namespace) -> str:
    start = args.backtest_start.replace("-", "")
    return (
        f"sma_window_and_drawdown_opt_"
        f"{args.signal_source}_"
        f"above_tecl{int(args.above_tecl)}_tqqq{int(args.above_tqqq)}_"
        f"wait_tmf{int(args.wait_tmf)}_gld{int(args.wait_gld)}_"
        f"below_soxl{int(args.below_soxl)}_tecl{int(args.below_tecl)}_tqqq{int(args.below_tqqq)}_"
        f"{args.below_entry_mode}_ref_{args.below_entry_reference_source}_"
        f"m{args.m_min}to{args.m_max}step{args.m_step}_"
        f"n{str(args.n_min).replace('.', 'p')}to{str(args.n_max).replace('.', 'p')}step{str(args.n_step).replace('.', 'p')}_"
        f"from_{start}"
    )


def save_heatmap(grid: pd.DataFrame, output_path: Path, title: str) -> None:
    pivot = grid.pivot(index="signal_window", columns="below_entry_drawdown_pct", values="cagr")
    x = pivot.columns.to_numpy(dtype=float)
    y = pivot.index.to_numpy(dtype=float)
    z = pivot.to_numpy(dtype=float) * 100.0

    best = grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).iloc[0]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    mesh = ax.pcolormesh(x, y, z, shading="nearest", cmap="viridis")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("CAGR (%)")
    ax.scatter(
        [best["below_entry_drawdown_pct"]],
        [best["signal_window"]],
        color="red",
        s=120,
        edgecolor="white",
        linewidth=1.2,
        zorder=5,
    )
    ax.annotate(
        f"best m={int(best['signal_window'])}, n={best['below_entry_drawdown_pct']:.1f}%\nCAGR={best['cagr']*100:.2f}%",
        (best["below_entry_drawdown_pct"], best["signal_window"]),
        textcoords="offset points",
        xytext=(12, 12),
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.9, "edgecolor": "#999999"},
    )
    ax.set_title(title)
    ax.set_xlabel("n (%)")
    ax.set_ylabel("SMA window (days)")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sim = load_sim_module()

    prices = sim.download_adj_close(
        ["TECL", "XLK", "FSPTX", "SOXL", "^SOX", "SOXX", "FSELX", "^GSPC", "GLD", sim.DEFAULT_GLD_PROXY_TICKER],
        start=args.fetch_start,
        end=args.fetch_end,
    )
    rate = sim.download_fred_series(sim.DEFAULT_RATE_SERIES_ID).reindex(prices.index).ffill().bfill()
    tecl_frame, _ = sim.build_tecl_series(prices, rate, annual_fee=sim.DEFAULT_TECL_ANNUAL_FEE)
    soxl_frame, _ = sim.build_soxl_series(
        prices,
        rate,
        annual_fee=sim.DEFAULT_SOXL_ANNUAL_FEE,
        switch_date=pd.Timestamp(sim.DEFAULT_SWITCH_DATE),
    )
    tqqq_frame = sim.load_canonical_tqqq()
    tmf_frame = sim.load_canonical_tmf()
    gld_frame, _ = sim.build_gld_series(prices)

    frame = pd.concat([tecl_frame, soxl_frame, tqqq_frame, tmf_frame, gld_frame], axis=1).sort_index()
    frame["GSPC_PRICE"] = prices["^GSPC"]
    frame = frame.loc[pd.Timestamp(args.backtest_start) :].copy()

    below_weights = sim.normalize_weights(args.below_soxl, args.below_tecl, args.below_tqqq)
    above_weights = sim.normalize_weights(args.above_tecl, args.above_tqqq)
    wait_weights = sim.normalize_weights(args.wait_tmf, args.wait_gld)

    m_values = list(range(args.m_min, args.m_max + 1, args.m_step))
    n_values = np.round(np.arange(args.n_min, args.n_max + args.n_step / 2.0, args.n_step), 10)

    rows: list[dict[str, float]] = []
    for signal_window in m_values:
        for drawdown_pct in n_values:
            _, stats = sim.simulate_strategy(
                frame=frame,
                signal_source=args.signal_source,
                signal_window=signal_window,
                below_weights=below_weights,
                above_weights=above_weights,
                wait_weights=wait_weights,
                below_entry_mode=args.below_entry_mode,
                below_entry_reference_source=args.below_entry_reference_source,
                below_entry_drawdown_pct=float(drawdown_pct),
            )
            strategy_row = stats[stats["series"] == "strategy"].iloc[0].to_dict()
            strategy_row["signal_window"] = signal_window
            strategy_row["below_entry_drawdown_pct"] = float(drawdown_pct)
            rows.append(strategy_row)

    grid = pd.DataFrame(rows).sort_values(["signal_window", "below_entry_drawdown_pct"]).reset_index(drop=True)
    best = grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).iloc[0]

    stem = build_output_stem(args)
    grid_path = OUTPUT_DIR / f"{stem}_grid.csv"
    top10_path = OUTPUT_DIR / f"{stem}_top10.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    heatmap_path = OUTPUT_DIR / f"{stem}_cagr_heatmap.png"

    grid.to_csv(grid_path, index=False)
    grid.sort_values(["cagr", "final_multiple"], ascending=[False, False]).head(10).to_csv(top10_path, index=False)

    baseline_mask = (grid["signal_window"] == 160) & (grid["below_entry_drawdown_pct"] == 50.5)
    baseline = grid.loc[baseline_mask].iloc[0] if baseline_mask.any() else None
    summary = pd.DataFrame(
        [
            {
                "best_signal_window": int(best["signal_window"]),
                "best_drawdown_pct": float(best["below_entry_drawdown_pct"]),
                "best_cagr": float(best["cagr"]),
                "best_annualized_vol": float(best["annualized_vol"]),
                "best_max_drawdown": float(best["max_drawdown"]),
                "best_final_multiple": float(best["final_multiple"]),
                "baseline_signal_window": None if baseline is None else int(baseline["signal_window"]),
                "baseline_drawdown_pct": None if baseline is None else float(baseline["below_entry_drawdown_pct"]),
                "baseline_cagr": None if baseline is None else float(baseline["cagr"]),
                "baseline_annualized_vol": None if baseline is None else float(baseline["annualized_vol"]),
                "baseline_max_drawdown": None if baseline is None else float(baseline["max_drawdown"]),
                "baseline_final_multiple": None if baseline is None else float(baseline["final_multiple"]),
                "m_min": args.m_min,
                "m_max": args.m_max,
                "m_step": args.m_step,
                "n_min": args.n_min,
                "n_max": args.n_max,
                "n_step": args.n_step,
            }
        ]
    )
    summary.to_csv(summary_path, index=False)

    save_heatmap(
        grid=grid,
        output_path=heatmap_path,
        title=(
            "Joint Optimization Of SMA Window And Drawdown Threshold"
            f" | signal={args.signal_source}"
            f" | below ref={args.below_entry_reference_source}"
        ),
    )

    print("Saved:")
    print(f"- {grid_path}")
    print(f"- {top10_path}")
    print(f"- {summary_path}")
    print(f"- {heatmap_path}")
    print()
    print("Best:")
    print(best.to_string())


if __name__ == "__main__":
    main()
