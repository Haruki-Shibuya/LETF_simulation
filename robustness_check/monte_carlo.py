"""
Monte Carlo Robustness Check – Canonical LETF Strategy
=======================================================

Method A: Stationary Block Bootstrap (ARCH)
  - Resample daily returns in variable-length blocks (~10 days mean)
  - Preserves autocorrelation / volatility clustering
  - 2000 simulations per canonical period

Method B: Regime-Aware Bootstrap (custom)
  - Split history into contiguous Bull / Bear episodes (GSPC vs SMA160)
  - Resample episodes with replacement, alternating regime type
  - Preserves within-regime return structure and episode-length distribution

Outputs (all in robustness_check/output/):
  mc_methodA_2005_fan.png   mc_methodA_2010_fan.png
  mc_methodB_2005_fan.png   mc_methodB_2010_fan.png
  mc_distributions_2005.png mc_distributions_2010.png
  mc_summary.csv
  MONTE_CARLO_REPORT.md
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from arch.bootstrap import StationaryBootstrap

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_DIR   = Path(__file__).resolve().parent.parent
CANON_DIR  = REPO_DIR / "tecl_sma160_rotation" / "output"
OUT_DIR    = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CANONICAL_PATHS = {
    "from_20051220": CANON_DIR / (
        "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
        "_low_rsi_tqqq_from_20051220_daily_path.csv"
    ),
    "from_20100212": CANON_DIR / (
        "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
        "_low_rsi_tqqq_from_20100212_daily_path.csv"
    ),
}

N_SIM          = 2000
BLOCK_SIZE_A   = 10     # mean block length for Method A (days)
TRADING_DAYS   = 252
RNG_SEED       = 42
PCT_BANDS      = [1, 5, 25, 50, 75, 95, 99]   # percentiles to track


# ── metrics ────────────────────────────────────────────────────────────────────

def compute_metrics(returns: np.ndarray) -> dict[str, float]:
    r = np.clip(returns, -0.999999, None)
    eq = np.cumprod(1.0 + r)
    n  = len(r)
    years  = n / TRADING_DAYS
    cagr   = float(eq[-1] ** (1.0 / years) - 1.0)
    vol    = float(np.std(r, ddof=0) * np.sqrt(TRADING_DAYS))
    peak   = np.maximum.accumulate(eq)
    mdd    = float(np.min(eq / peak - 1.0))
    calmar = cagr / abs(mdd) if mdd != 0 else np.nan
    sharpe = cagr / vol if vol else np.nan
    return {
        "cagr":   cagr,
        "vol":    vol,
        "mdd":    mdd,
        "sharpe": sharpe,
        "calmar": calmar,
        "final_eq": float(eq[-1]),
    }


def equity_curve(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + np.clip(returns, -0.999999, None))


# ── Method A: Stationary Block Bootstrap ─────────────────────────────────────

def method_a(returns: np.ndarray, n_sim: int = N_SIM,
             block_size: int = BLOCK_SIZE_A) -> tuple[list[dict], np.ndarray]:
    """
    Returns (list of metric dicts, equity_matrix [n_sim × n_days]).
    """
    bs      = StationaryBootstrap(block_size, returns, seed=RNG_SEED)
    metrics = []
    eq_mat  = np.empty((n_sim, len(returns)))

    for i, (pos_data, _) in enumerate(bs.bootstrap(n_sim)):
        sim_r = pos_data[0].flatten()[:len(returns)]
        eq_mat[i] = equity_curve(sim_r)
        metrics.append(compute_metrics(sim_r))

    return metrics, eq_mat


# ── Method B: Regime-Aware Bootstrap ──────────────────────────────────────────

def extract_regime_episodes(
    returns: np.ndarray,
    is_bear: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Split return array into contiguous Bull and Bear episodes."""
    bull_eps: list[np.ndarray] = []
    bear_eps: list[np.ndarray] = []

    n = len(returns)
    i = 0
    while i < n:
        regime = is_bear[i]
        j = i
        while j < n and is_bear[j] == regime:
            j += 1
        block = returns[i:j]
        if len(block) > 0:
            (bear_eps if regime else bull_eps).append(block)
        i = j

    return bull_eps, bear_eps


def regime_bootstrap_path(
    bull_eps: list[np.ndarray],
    bear_eps: list[np.ndarray],
    target_len: int,
    rng: np.random.Generator,
    start_bear: bool = False,
) -> np.ndarray:
    """Alternately sample episodes, preserving regime sequence structure."""
    path: list[float] = []
    current_bear = start_bear
    # guard: if one side is empty, fall back to other
    if not bull_eps:
        bull_eps = bear_eps
    if not bear_eps:
        bear_eps = bull_eps

    while len(path) < target_len:
        eps = bear_eps if current_bear else bull_eps
        ep  = eps[rng.integers(len(eps))]
        remaining = target_len - len(path)
        path.extend(ep[:remaining].tolist())
        current_bear = not current_bear

    return np.array(path[:target_len])


def method_b(
    returns: np.ndarray,
    is_bear: np.ndarray,
    n_sim: int = N_SIM,
) -> tuple[list[dict], np.ndarray]:
    """
    Returns (list of metric dicts, equity_matrix [n_sim × n_days]).
    """
    bull_eps, bear_eps = extract_regime_episodes(returns, is_bear)
    rng    = np.random.default_rng(RNG_SEED)
    n_days = len(returns)
    start_bear = bool(is_bear[0])

    metrics = []
    eq_mat  = np.empty((n_sim, n_days))

    for i in range(n_sim):
        sim_r     = regime_bootstrap_path(bull_eps, bear_eps, n_days, rng, start_bear)
        eq_mat[i] = equity_curve(sim_r)
        metrics.append(compute_metrics(sim_r))

    return metrics, eq_mat


# ── plotting ───────────────────────────────────────────────────────────────────

BAND_COLORS = {
    (1, 99):  ("#D5E8F5", 0.5),
    (5, 95):  ("#93C9E8", 0.5),
    (25, 75): ("#3498DB", 0.4),
}


def plot_fan(
    eq_mat: np.ndarray,
    actual_eq: np.ndarray,
    title: str,
    out_path: Path,
    method_label: str,
    metrics_list: list[dict],
    actual_metrics: dict[str, float],
) -> None:
    """Fan chart + metric distribution panels."""
    n_days = eq_mat.shape[1]
    x      = np.arange(n_days)
    pcts   = {p: np.percentile(eq_mat, p, axis=0) for p in PCT_BANDS}

    fig = plt.figure(figsize=(18, 12))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32)

    # ── Fan chart ─────────────────────────────────────────────────────────────
    ax_fan = fig.add_subplot(gs[0, :])
    for (lo, hi), (color, alpha) in BAND_COLORS.items():
        ax_fan.fill_between(x, pcts[lo], pcts[hi], color=color, alpha=alpha,
                            label=f"P{lo}–P{hi}")
    ax_fan.semilogy(x, pcts[50],    color="#1A5276", lw=1.4, linestyle="--",
                    label="Median (simulated)")
    ax_fan.semilogy(x, actual_eq,   color="#E74C3C", lw=2.0,
                    label=f"Actual backtest")
    ax_fan.semilogy(x, pcts[5],     color="#7F8C8D", lw=0.7, linestyle=":")
    ax_fan.semilogy(x, pcts[95],    color="#7F8C8D", lw=0.7, linestyle=":")

    loss_prob = float(np.mean(eq_mat[:, -1] < 1.0)) * 100
    cvar5     = float(np.mean([m["cagr"] for m in metrics_list
                               if m["cagr"] <= np.percentile(
                                   [mm["cagr"] for mm in metrics_list], 5)]))
    ax_fan.set_title(
        f"{title}\n"
        f"N={len(metrics_list):,} sims  |  Loss prob={loss_prob:.1f}%  |  "
        f"CVaR(5%) CAGR={cvar5*100:.1f}%  |  Actual CAGR={actual_metrics['cagr']*100:.1f}%",
        fontsize=11,
    )
    ax_fan.set_xlabel("Trading days", fontsize=10)
    ax_fan.set_ylabel("Equity (log scale)", fontsize=10)
    ax_fan.legend(fontsize=9, loc="upper left", ncol=4)
    ax_fan.grid(axis="y", alpha=0.25)

    # ── Distribution subplots ─────────────────────────────────────────────────
    metric_specs = [
        ("cagr",   "CAGR",           100,  "%",    actual_metrics["cagr"]),
        ("vol",    "Ann. Vol",        100,  "%",    actual_metrics["vol"]),
        ("mdd",    "Max Drawdown",    100,  "%",    actual_metrics["mdd"]),
    ]
    for col_i, (key, label, scale, unit, actual_val) in enumerate(metric_specs):
        ax = fig.add_subplot(gs[1, col_i])
        vals = np.array([m[key] for m in metrics_list]) * scale
        ax.hist(vals, bins=60, color="#3498DB", alpha=0.65, edgecolor="none", density=True)
        ax.axvline(actual_val * scale, color="#E74C3C", lw=2.0, label=f"Actual {actual_val*scale:.1f}{unit}")
        ax.axvline(np.percentile(vals, 5),  color="#E67E22", lw=1.2, linestyle="--",
                   label=f"P5={np.percentile(vals,5):.1f}{unit}")
        ax.axvline(np.percentile(vals, 50), color="#1A5276", lw=1.2, linestyle="--",
                   label=f"P50={np.percentile(vals,50):.1f}{unit}")
        ax.axvline(np.percentile(vals, 95), color="#27AE60", lw=1.2, linestyle="--",
                   label=f"P95={np.percentile(vals,95):.1f}{unit}")
        pct_rank = float(np.mean(vals <= actual_val * scale)) * 100
        ax.set_title(f"{label}  (actual={actual_val*scale:.1f}{unit}, rank={pct_rank:.0f}th pct)", fontsize=9)
        ax.set_xlabel(f"{label} ({unit})", fontsize=9)
        ax.legend(fontsize=7.5)
        ax.grid(alpha=0.2)

    fig.suptitle(f"{method_label}  –  {title}", fontsize=13, y=0.995)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


# ── summary stats builder ──────────────────────────────────────────────────────

def summarise(
    metrics_list: list[dict],
    actual: dict[str, float],
    period: str,
    method: str,
) -> dict:
    cagrs = np.array([m["cagr"]   for m in metrics_list]) * 100
    vols  = np.array([m["vol"]    for m in metrics_list]) * 100
    mdds  = np.array([m["mdd"]    for m in metrics_list]) * 100
    sharpes = np.array([m["sharpe"] for m in metrics_list])

    pct_rank_cagr = float(np.mean(cagrs <= actual["cagr"] * 100)) * 100

    def pct(arr, p): return float(np.percentile(arr, p))

    return {
        "period":          period,
        "method":          method,
        "n_sim":           len(metrics_list),
        "actual_cagr%":    round(actual["cagr"]  * 100, 2),
        "actual_vol%":     round(actual["vol"]   * 100, 2),
        "actual_mdd%":     round(actual["mdd"]   * 100, 2),
        "actual_sharpe":   round(actual["sharpe"], 3),
        "cagr_p1%":        round(pct(cagrs,  1), 2),
        "cagr_p5%":        round(pct(cagrs,  5), 2),
        "cagr_p25%":       round(pct(cagrs, 25), 2),
        "cagr_p50%":       round(pct(cagrs, 50), 2),
        "cagr_p75%":       round(pct(cagrs, 75), 2),
        "cagr_p95%":       round(pct(cagrs, 95), 2),
        "cagr_p99%":       round(pct(cagrs, 99), 2),
        "vol_p5%":         round(pct(vols,   5), 2),
        "vol_p50%":        round(pct(vols,  50), 2),
        "vol_p95%":        round(pct(vols,  95), 2),
        "mdd_p5%":         round(pct(mdds,   5), 2),
        "mdd_p50%":        round(pct(mdds,  50), 2),
        "mdd_p95%":        round(pct(mdds,  95), 2),
        "loss_prob%":      round(float(np.mean([m["final_eq"] < 1.0 for m in metrics_list])) * 100, 2),
        "cvar5_cagr%":     round(float(np.mean(cagrs[cagrs <= pct(cagrs, 5)])), 2),
        "actual_pct_rank": round(pct_rank_cagr, 1),
        "sharpe_p5":       round(pct(sharpes,  5), 3),
        "sharpe_p50":      round(pct(sharpes, 50), 3),
        "sharpe_p95":      round(pct(sharpes, 95), 3),
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    all_summary: list[dict] = []

    for period_label, canon_path in CANONICAL_PATHS.items():
        print(f"\n{'='*65}")
        print(f"  Period: {period_label}")
        print(f"{'='*65}")

        df = pd.read_csv(canon_path, parse_dates=["Date"]).set_index("Date").sort_index()
        returns    = df["strategy_return"].values.astype(float)
        actual_eq  = np.cumprod(1.0 + np.clip(returns, -0.999999, None))
        actual_met = compute_metrics(returns)
        is_bear    = df["signal_below_sma"].fillna(False).values.astype(bool)

        # regime stats
        n_bull = int((~is_bear).sum())
        n_bear = int(is_bear.sum())
        bull_eps, bear_eps = extract_regime_episodes(returns, is_bear)
        print(f"  Bull days={n_bull} ({n_bull/len(returns)*100:.1f}%)  "
              f"Bear days={n_bear} ({n_bear/len(returns)*100:.1f}%)")
        print(f"  Bull episodes={len(bull_eps)}  Bear episodes={len(bear_eps)}")
        print(f"  Actual: CAGR={actual_met['cagr']*100:.2f}%  "
              f"Vol={actual_met['vol']*100:.2f}%  "
              f"MDD={actual_met['mdd']*100:.2f}%  "
              f"Sharpe={actual_met['sharpe']:.3f}")

        # ── Method A ─────────────────────────────────────────────────────────
        print(f"\n  Method A (Stationary Block Bootstrap, block={BLOCK_SIZE_A}d) ...")
        met_a, eq_a = method_a(returns)
        cagrs_a = [m["cagr"] * 100 for m in met_a]
        print(f"  CAGR  P5={np.percentile(cagrs_a,5):.1f}%  "
              f"P50={np.percentile(cagrs_a,50):.1f}%  "
              f"P95={np.percentile(cagrs_a,95):.1f}%  "
              f"loss_prob={np.mean([m['final_eq']<1 for m in met_a])*100:.1f}%")
        sum_a = summarise(met_a, actual_met, period_label, "A_stationary_block")
        all_summary.append(sum_a)

        plot_fan(
            eq_a, actual_eq,
            f"Canonical {period_label.replace('from_','from ')}",
            OUT_DIR / f"mc_methodA_{period_label}_fan.png",
            "Method A: Stationary Block Bootstrap",
            met_a, actual_met,
        )

        # ── Method B ─────────────────────────────────────────────────────────
        print(f"\n  Method B (Regime-Aware Bootstrap) ...")
        met_b, eq_b = method_b(returns, is_bear)
        cagrs_b = [m["cagr"] * 100 for m in met_b]
        print(f"  CAGR  P5={np.percentile(cagrs_b,5):.1f}%  "
              f"P50={np.percentile(cagrs_b,50):.1f}%  "
              f"P95={np.percentile(cagrs_b,95):.1f}%  "
              f"loss_prob={np.mean([m['final_eq']<1 for m in met_b])*100:.1f}%")
        sum_b = summarise(met_b, actual_met, period_label, "B_regime_aware")
        all_summary.append(sum_b)

        plot_fan(
            eq_b, actual_eq,
            f"Canonical {period_label.replace('from_','from ')}",
            OUT_DIR / f"mc_methodB_{period_label}_fan.png",
            "Method B: Regime-Aware Bootstrap",
            met_b, actual_met,
        )

        # ── Method A vs B comparison overlay ─────────────────────────────────
        _plot_comparison(eq_a, eq_b, actual_eq, period_label, actual_met)

    # ── Save summary CSV ──────────────────────────────────────────────────────
    summary_df = pd.DataFrame(all_summary)
    csv_path   = OUT_DIR / "mc_summary.csv"
    summary_df.to_csv(csv_path, index=False)
    print(f"\nSaved summary → {csv_path}")

    # ── Generate markdown report ──────────────────────────────────────────────
    _write_report(summary_df)


def _plot_comparison(eq_a, eq_b, actual_eq, period_label, actual_met):
    """Overlay fan bands from Method A and B for quick visual comparison."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 6), sharey=True)
    for ax, eq_mat, label, color in [
        (axes[0], eq_a, "Method A: Stationary Block Bootstrap", "#3498DB"),
        (axes[1], eq_b, "Method B: Regime-Aware Bootstrap",     "#E74C3C"),
    ]:
        pcts = {p: np.percentile(eq_mat, p, axis=0) for p in [5, 25, 50, 75, 95]}
        x    = np.arange(eq_mat.shape[1])
        ax.fill_between(x, pcts[5],  pcts[95], color=color, alpha=0.15, label="P5–P95")
        ax.fill_between(x, pcts[25], pcts[75], color=color, alpha=0.30, label="P25–P75")
        ax.semilogy(x, pcts[50],    color=color, lw=1.3, linestyle="--", label="Median")
        ax.semilogy(x, actual_eq,   color="#2C3E50", lw=2.0, label="Actual")
        loss = float(np.mean(eq_mat[:, -1] < 1.0)) * 100
        ax.set_title(f"{label}\nPeriod: {period_label}  Loss prob={loss:.1f}%", fontsize=10)
        ax.set_xlabel("Trading days", fontsize=9)
        ax.set_ylabel("Equity (log)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"Monte Carlo Comparison – {period_label}", fontsize=12)
    plt.tight_layout()
    out = OUT_DIR / f"mc_comparison_{period_label}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out.name}")


def _write_report(df: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("# Monte Carlo Robustness Report – Canonical LETF Strategy")
    lines.append(f"\nGenerated: 2026-05-06  |  N simulations per method: {N_SIM:,}\n")

    lines.append("## 手法概要\n")
    lines.append("| 手法 | 説明 | ブロック長 |")
    lines.append("|------|------|-----------|")
    lines.append(f"| **A: Stationary Block Bootstrap** | 日次リターンを可変長ブロック単位でリサンプリング（ARCH ライブラリ）。自己相関・ボラティリティクラスタリングを保持 | 平均 {BLOCK_SIZE_A}日（可変）|")
    lines.append("| **B: Regime-Aware Bootstrap** | GSPC SMA160 でBull/Bearエピソードを分離し、エピソード単位で交互にリサンプリング。レジーム内の返回構造を保持 | エピソード単位（可変）|")
    lines.append("")

    for period in df["period"].unique():
        sub = df[df["period"] == period]
        pretty = period.replace("from_", "from ")
        lines.append(f"---\n\n## 期間: {pretty}\n")

        for _, row in sub.iterrows():
            method_name = ("Method A: Stationary Block Bootstrap"
                           if "A_" in row["method"] else "Method B: Regime-Aware Bootstrap")
            lines.append(f"### {method_name}\n")

            lines.append("#### 実績値（Historical）\n")
            lines.append("| CAGR | Vol | MDD | Sharpe |")
            lines.append("|-----:|----:|----:|-------:|")
            lines.append(f"| {row['actual_cagr%']:.2f}% | {row['actual_vol%']:.2f}% "
                         f"| {row['actual_mdd%']:.2f}% | {row['actual_sharpe']:.3f} |")
            lines.append("")

            lines.append("#### シミュレーション分布（2,000パス）\n")
            lines.append("| 指標 | P1 | P5 | P25 | P50（中央） | P75 | P95 | P99 |")
            lines.append("|------|---:|---:|----:|------------:|----:|----:|----:|")
            lines.append(f"| CAGR (%) | {row['cagr_p1%']} | {row['cagr_p5%']} | "
                         f"{row['cagr_p25%']} | {row['cagr_p50%']} | "
                         f"{row['cagr_p75%']} | {row['cagr_p95%']} | {row['cagr_p99%']} |")
            lines.append(f"| Vol (%)  | – | {row['vol_p5%']} | – | {row['vol_p50%']} "
                         f"| – | {row['vol_p95%']} | – |")
            lines.append(f"| MDD (%)  | – | {row['mdd_p5%']} | – | {row['mdd_p50%']} "
                         f"| – | {row['mdd_p95%']} | – |")
            lines.append(f"| Sharpe   | – | {row['sharpe_p5']} | – | {row['sharpe_p50']} "
                         f"| – | {row['sharpe_p95']} | – |")
            lines.append("")

            lines.append("#### テールリスク指標\n")
            lines.append("| 指標 | 値 | 意味 |")
            lines.append("|------|--:|------|")
            lines.append(f"| 損失確率（final_eq < 1.0） | **{row['loss_prob%']:.2f}%** | "
                         "全シム期間通じて元本割れするパスの割合 |")
            lines.append(f"| CVaR 5% CAGR | **{row['cvar5_cagr%']:.2f}%** | "
                         "下位5%シナリオの平均CAGR |")
            lines.append(f"| 実績のパーセンタイル順位 | **{row['actual_pct_rank']:.0f}th** | "
                         "実績CAGRが何%ileに位置するか（高いほど実績が運に依存）|")
            lines.append("")

    lines.append("---\n\n## 解釈ガイド\n")
    lines.append("""
- **損失確率が低い（< 5%）**: 多くのリサンプリングパスで元本を維持 → 戦略の頑健性が高い
- **実績のパーセンタイル順位が高い（> 80th）**: 実績は「運が良いシナリオ」に近い。過去の順番・タイミングが現在の成績に寄与している可能性
- **実績のパーセンタイル順位が中程度（40–70th）**: 再現性が高く、タイミング依存度が低い = より頑健
- **CVaR 5%**: 最悪シナリオ群の平均CAGR。戦略のテールリスクを表す
- **Method A vs B の乖離が大きい場合**: レジーム構造（Bull/Bear の順序）が成績に大きく寄与している可能性
""")

    lines.append("## 出力ファイル\n")
    lines.append("| ファイル | 内容 |")
    lines.append("|---------|------|")
    for f in sorted(OUT_DIR.glob("mc_*.png")):
        lines.append(f"| `{f.name}` | チャート |")
    lines.append("| `mc_summary.csv` | 全数値サマリー |")

    report_path = Path(__file__).resolve().parent / "MONTE_CARLO_REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved report → {report_path.name}")


if __name__ == "__main__":
    main()
