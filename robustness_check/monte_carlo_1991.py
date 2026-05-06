"""
Monte Carlo Robustness Check – Full Stitched Series 1991–2026
=============================================================

Series construction
  1991-01-01 – 2005-12-19  : Synthetic canonical
      - Full canonical logic (SMA160 + BB20z/RSI signals + drawdown alpha=100)
      - UVIX replaced by Cash (^IRX, annualised rate / 252)
      - wait_mix replaced by Cash (^IRX)
      - TQQQ returns: TQQQ_CC_RETURN_REBUILT (synthetic_calibrated)
  2005-12-20 – latest      : Actual canonical CSV

Monte Carlo methods
  A: Stationary Block Bootstrap (ARCH, mean block = 10 days)
  B: Regime-Aware Bootstrap (Bull/Bear episodes via GSPC SMA160)

All outputs → robustness_check/output/
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import yfinance as yf
from arch.bootstrap import StationaryBootstrap

# ── paths ──────────────────────────────────────────────────────────────────────
HERE       = Path(__file__).resolve().parent
REPO_DIR   = HERE.parent
CANON_DIR  = REPO_DIR / "tecl_sma160_rotation" / "output"
OUT_DIR    = HERE / "output"
OUT_DIR.mkdir(exist_ok=True)

CANON_2005_PATH = CANON_DIR / (
    "canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1"
    "_low_rsi_tqqq_from_20051220_daily_path.csv"
)
OHLC_PATH = CANON_DIR / "next_open_ohlc_series_tqqq_tmf_gld.csv"

# ── constants ──────────────────────────────────────────────────────────────────
SIM_START           = "1991-01-01"
CANON_START         = "2005-12-20"
GSPC_DL_START       = "1987-01-01"
IRX_DL_START        = "1988-01-01"
SMA_WINDOW          = 160
ALPHA_DRAWDOWN_PCT  = 100.0   # effectively disabled (dot-com crash = 99.9% dd)
UVIX_ENTRY_RSI      = 67.5
UVIX_ENTRY_MIN_BB_Z = 1.6
UVIX_EXIT_RSI       = 66.0
UVIX_GSPC_PROFIT    = 0.1     # % drop from UVIX-entry GSPC → exit
LOW_RSI_ENTRY       = 30.0
LOW_RSI_EXIT        = 32.5
RSI_PERIOD          = 14
BB_WINDOW           = 20
TRADING_DAYS        = 252
N_SIM               = 2000
BLOCK_SIZE          = 10
RNG_SEED            = 42
PCT_BANDS           = [1, 5, 25, 50, 75, 95, 99]


# ── data download ──────────────────────────────────────────────────────────────

def _dl(ticker: str, start: str) -> pd.Series:
    raw = yf.download(ticker, start=start, end="2026-05-05",
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw.squeeze()


# ── canonical indicators ──────────────────────────────────────────────────────

def rsi_wilder(closes: list[float], open_price: float) -> float | None:
    values = closes + [open_price]
    if len(values) <= RSI_PERIOD:
        return None
    gains, losses = [], []
    for p, c in zip(values, values[1:]):
        d = c - p
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
    ag = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    al = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    for g, l in zip(gains[RSI_PERIOD:], losses[RSI_PERIOD:]):
        ag = (ag * (RSI_PERIOD - 1) + g) / RSI_PERIOD
        al = (al * (RSI_PERIOD - 1) + l) / RSI_PERIOD
    return 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)


def bb20z(prev_closes: list[float], open_price: float) -> float | None:
    window = prev_closes[-BB_WINDOW:]
    if len(window) < BB_WINDOW:
        return None
    mean = sum(window) / len(window)
    std  = math.sqrt(sum((v - mean) ** 2 for v in window) / len(window))
    return None if std == 0 else (open_price - mean) / std


# ── pre-2005 synthetic canonical ───────────────────────────────────────────────

def simulate_pre2005(
    gspc: pd.Series,
    tqqq_cc: pd.Series,
    irx: pd.Series,
) -> pd.DataFrame:
    """
    Returns DataFrame with columns:
      strategy_return, selected_leg, is_bear
    for SIM_START to (CANON_START exclusive).
    """
    ohlc = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    tqqq_open = ohlc["TQQQ_OPEN"]

    # common index
    idx = (
        gspc.index[gspc.index >= SIM_START]
        .intersection(tqqq_cc.dropna().index)
    )
    idx = idx[idx < CANON_START]

    sma160_lag = gspc.rolling(SMA_WINDOW).mean().shift(1)

    # seed TQQQ peak from history before SIM_START
    pre = tqqq_open.dropna()
    pre = pre[pre.index < SIM_START]
    tqqq_peak = float(pre.max()) if not pre.empty else 0.0

    # pre-populate GSPC close history
    pre_gspc = gspc.dropna()
    gspc_closes: list[float] = list(pre_gspc[pre_gspc.index < SIM_START].values)

    legs, rets, is_bear_list = [], [], []
    in_reentry       = False
    active_cash_uvix = False
    active_low_rsi   = False
    uvix_entry_gspc  = None

    irx_ff = irx.reindex(idx).ffill()

    for d in idx:
        gspc_open  = float(gspc.loc[d])
        sma_prev   = sma160_lag.loc[d]
        tqqq_r     = float(tqqq_cc.loc[d])
        cash_r     = float(irx_ff.loc[d]) if not np.isnan(irx_ff.loc[d]) else 0.0
        to         = tqqq_open.get(d, np.nan)

        if not (isinstance(to, float) and np.isnan(to)):
            tqqq_peak = max(tqqq_peak, float(to))

        drawdown_pct = (
            (1 - float(to) / tqqq_peak) * 100
            if (tqqq_peak > 0 and not (isinstance(to, float) and np.isnan(to)))
            else 0.0
        )

        rsi_v = rsi_wilder(gspc_closes, gspc_open)
        z_v   = bb20z(gspc_closes, gspc_open)

        # base signal
        below_sma = (not np.isnan(sma_prev)) and (gspc_open < sma_prev)
        triggered = below_sma and (drawdown_pct >= ALPHA_DRAWDOWN_PCT)

        if not below_sma:
            in_reentry = False; base = "TQQQ"
        elif in_reentry or triggered:
            in_reentry = True; base = "TQQQ"
        else:
            base = "wait_mix"

        # overlays
        if active_cash_uvix:
            rsi_exit  = (rsi_v is not None) and rsi_v <= UVIX_EXIT_RSI
            gspc_exit = (uvix_entry_gspc is not None) and (
                gspc_open <= uvix_entry_gspc * (1 + UVIX_GSPC_PROFIT / 100))
            if rsi_exit or gspc_exit:
                active_cash_uvix = False; uvix_entry_gspc = None; selected = base
            else:
                selected = "cash_uvix"
        elif active_low_rsi:
            if (rsi_v is not None) and rsi_v >= LOW_RSI_EXIT:
                active_low_rsi = False; selected = base
            else:
                selected = "low_rsi_tqqq"
        else:
            if (rsi_v is not None) and rsi_v >= UVIX_ENTRY_RSI:
                if (z_v is not None) and z_v >= UVIX_ENTRY_MIN_BB_Z:
                    active_cash_uvix = True; uvix_entry_gspc = gspc_open
                    selected = "cash_uvix"
                else:
                    selected = base
            elif (rsi_v is not None) and rsi_v < LOW_RSI_ENTRY and base == "wait_mix":
                active_low_rsi = True; selected = "low_rsi_tqqq"
            else:
                selected = base

        is_tqqq = selected in {"TQQQ", "low_rsi_tqqq"}
        legs.append(selected)
        rets.append(tqqq_r if is_tqqq else cash_r)
        is_bear_list.append(below_sma)
        gspc_closes.append(gspc_open)

    return pd.DataFrame({
        "strategy_return": rets,
        "selected_leg":    legs,
        "is_bear":         is_bear_list,
    }, index=idx)


# ── metrics ────────────────────────────────────────────────────────────────────

def compute_metrics(returns: np.ndarray) -> dict[str, float]:
    r    = np.clip(returns, -0.999999, None)
    eq   = np.cumprod(1.0 + r)
    yrs  = len(r) / TRADING_DAYS
    cagr = float(eq[-1] ** (1.0 / yrs) - 1.0)
    vol  = float(np.std(r, ddof=0) * np.sqrt(TRADING_DAYS))
    mdd  = float(np.min(eq / np.maximum.accumulate(eq) - 1.0))
    return {
        "cagr": cagr, "vol": vol, "mdd": mdd,
        "sharpe": cagr / vol if vol else np.nan,
        "calmar": cagr / abs(mdd) if mdd else np.nan,
        "final_eq": float(eq[-1]),
    }


def equity_curve(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + np.clip(returns, -0.999999, None))


# ── Monte Carlo methods ────────────────────────────────────────────────────────

def method_a(returns: np.ndarray) -> tuple[list[dict], np.ndarray]:
    bs     = StationaryBootstrap(BLOCK_SIZE, returns, seed=RNG_SEED)
    n      = len(returns)
    mets   = []
    eq_mat = np.empty((N_SIM, n))
    for i, (pos_data, _) in enumerate(bs.bootstrap(N_SIM)):
        sim_r      = pos_data[0].flatten()[:n]
        eq_mat[i]  = equity_curve(sim_r)
        mets.append(compute_metrics(sim_r))
    return mets, eq_mat


def extract_episodes(
    returns: np.ndarray, is_bear: np.ndarray
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    bull, bear = [], []
    n = len(returns)
    i = 0
    while i < n:
        reg = is_bear[i]
        j   = i
        while j < n and is_bear[j] == reg:
            j += 1
        blk = returns[i:j]
        (bear if reg else bull).append(blk)
        i = j
    return bull, bear


def method_b(
    returns: np.ndarray, is_bear: np.ndarray
) -> tuple[list[dict], np.ndarray]:
    bull_eps, bear_eps = extract_episodes(returns, is_bear)
    if not bull_eps: bull_eps = bear_eps
    if not bear_eps: bear_eps = bull_eps

    rng        = np.random.default_rng(RNG_SEED)
    n          = len(returns)
    start_bear = bool(is_bear[0])
    mets       = []
    eq_mat     = np.empty((N_SIM, n))

    for i in range(N_SIM):
        path: list[float] = []
        cur  = start_bear
        while len(path) < n:
            eps = bear_eps if cur else bull_eps
            ep  = eps[rng.integers(len(eps))]
            rem = n - len(path)
            path.extend(ep[:rem].tolist())
            cur = not cur
        sim_r     = np.array(path[:n])
        eq_mat[i] = equity_curve(sim_r)
        mets.append(compute_metrics(sim_r))

    return mets, eq_mat


# ── plotting ───────────────────────────────────────────────────────────────────

BAND_CFG = {(1, 99): ("#D5E8F5", 0.5), (5, 95): ("#93C9E8", 0.5), (25, 75): ("#3498DB", 0.4)}


def plot_fan(
    eq_mat: np.ndarray,
    actual_eq: np.ndarray,
    mets: list[dict],
    actual_met: dict,
    title: str,
    method_label: str,
    out_path: Path,
    date_index: pd.DatetimeIndex,
) -> None:
    pcts   = {p: np.percentile(eq_mat, p, axis=0) for p in PCT_BANDS}
    x      = np.arange(len(actual_eq))

    fig = plt.figure(figsize=(18, 12))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32)

    ax_fan = fig.add_subplot(gs[0, :])
    for (lo, hi), (color, alpha) in BAND_CFG.items():
        ax_fan.fill_between(x, pcts[lo], pcts[hi], color=color, alpha=alpha,
                            label=f"P{lo}–P{hi}")
    ax_fan.semilogy(x, pcts[50],   color="#1A5276", lw=1.4, linestyle="--", label="Median sim")
    ax_fan.semilogy(x, actual_eq,  color="#E74C3C", lw=2.0, label="Actual (stitched)")
    ax_fan.semilogy(x, pcts[5],    color="#95A5A6", lw=0.7, linestyle=":")
    ax_fan.semilogy(x, pcts[95],   color="#95A5A6", lw=0.7, linestyle=":")

    loss_prob = float(np.mean(eq_mat[:, -1] < 1.0)) * 100
    cvar5_arr = [m["cagr"] for m in mets]
    cvar5     = float(np.mean([v for v in cvar5_arr
                               if v <= np.percentile(cvar5_arr, 5)])) * 100

    # add pre/post divider
    n_pre = int((date_index < CANON_START).sum())
    if 0 < n_pre < len(x):
        ax_fan.axvline(n_pre, color="#2ECC71", lw=1.2, linestyle="--", alpha=0.7,
                       label=f"← Synthetic | Actual →  (split day {n_pre})")

    ax_fan.set_title(
        f"{title}\n"
        f"N={N_SIM:,} sims  Loss prob={loss_prob:.1f}%  "
        f"CVaR5%={cvar5:.1f}%  Actual CAGR={actual_met['cagr']*100:.1f}%  "
        f"Actual MDD={actual_met['mdd']*100:.1f}%",
        fontsize=10,
    )
    ax_fan.set_xlabel("Trading days from 1991-01-01", fontsize=9)
    ax_fan.set_ylabel("Equity (log scale)", fontsize=9)
    ax_fan.legend(fontsize=8.5, loc="upper left", ncol=3)
    ax_fan.grid(axis="y", alpha=0.25)

    for col_i, (key, label, scale, unit) in enumerate([
        ("cagr", "CAGR",        100, "%"),
        ("vol",  "Ann. Vol",    100, "%"),
        ("mdd",  "Max Drawdown",100, "%"),
    ]):
        ax = fig.add_subplot(gs[1, col_i])
        vals     = np.array([m[key] for m in mets]) * scale
        actual_v = actual_met[key] * scale
        ax.hist(vals, bins=60, color="#3498DB", alpha=0.65, edgecolor="none", density=True)
        ax.axvline(actual_v,              color="#E74C3C", lw=2.0,
                   label=f"Actual {actual_v:.1f}{unit}")
        ax.axvline(np.percentile(vals, 5), color="#E67E22", lw=1.2, linestyle="--",
                   label=f"P5={np.percentile(vals,5):.1f}{unit}")
        ax.axvline(np.percentile(vals, 50),color="#1A5276", lw=1.2, linestyle="--",
                   label=f"P50={np.percentile(vals,50):.1f}{unit}")
        ax.axvline(np.percentile(vals, 95),color="#27AE60", lw=1.2, linestyle="--",
                   label=f"P95={np.percentile(vals,95):.1f}{unit}")
        rank = float(np.mean(vals <= actual_v)) * 100
        ax.set_title(f"{label}  actual={actual_v:.1f}{unit}  rank={rank:.0f}th%ile", fontsize=9)
        ax.legend(fontsize=7.5)
        ax.grid(alpha=0.2)

    fig.suptitle(f"{method_label}  –  {title}", fontsize=12, y=0.995)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


def plot_comparison(eq_a, eq_b, actual_eq, actual_met, date_index):
    fig, axes = plt.subplots(1, 2, figsize=(18, 6), sharey=True)
    n_pre = int((date_index < CANON_START).sum())
    for ax, eq_mat, label, color in [
        (axes[0], eq_a, "Method A: Stationary Block Bootstrap", "#3498DB"),
        (axes[1], eq_b, "Method B: Regime-Aware Bootstrap",     "#E74C3C"),
    ]:
        pcts = {p: np.percentile(eq_mat, p, axis=0) for p in [5, 25, 50, 75, 95]}
        x    = np.arange(eq_mat.shape[1])
        ax.fill_between(x, pcts[5],  pcts[95], color=color, alpha=0.15, label="P5–P95")
        ax.fill_between(x, pcts[25], pcts[75], color=color, alpha=0.30, label="P25–P75")
        ax.semilogy(x, pcts[50],   color=color,    lw=1.3, linestyle="--", label="Median")
        ax.semilogy(x, actual_eq,  color="#2C3E50", lw=2.0, label="Actual (stitched)")
        if 0 < n_pre < len(x):
            ax.axvline(n_pre, color="#2ECC71", lw=1.2, linestyle="--", alpha=0.8,
                       label="Synthetic|Actual split")
        loss = float(np.mean(eq_mat[:, -1] < 1.0)) * 100
        ax.set_title(
            f"{label}\n1991–2026 stitched  |  "
            f"Loss prob={loss:.1f}%  Actual CAGR={actual_met['cagr']*100:.1f}%",
            fontsize=9,
        )
        ax.set_xlabel("Trading days from 1991-01-01", fontsize=9)
        ax.set_ylabel("Equity (log)", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Monte Carlo – 1991–2026 Stitched Series", fontsize=12)
    plt.tight_layout()
    out = OUT_DIR / "mc_1991_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out.name}")


# ── report ─────────────────────────────────────────────────────────────────────

def write_report(rows: list[dict], n_pre: int, n_post: int) -> None:
    lines = [
        "# Monte Carlo Report – 1991–2026 Stitched Series",
        "",
        f"Generated: 2026-05-06  |  N simulations: {N_SIM:,}",
        "",
        "## 系列構成",
        "",
        f"| 期間 | 日数 | 手法 |",
        "|------|-----:|------|",
        f"| 1991-01-01 – 2005-12-19 | {n_pre:,} | 合成カノニカル（UVIX/wait_mix → ^IRX Cash） |",
        f"| 2005-12-20 – 2026-04-17 | {n_post:,} | 実カノニカルCSV |",
        f"| **合計** | **{n_pre+n_post:,}** | |",
        "",
        "### 合成カノニカル（pre-2005）の代替ルール",
        "",
        "| 元のポジション | 代替 | 理由 |",
        "|--------------|------|------|",
        "| UVIX | Cash（^IRX / 252） | UVIX は2005年以前に存在しない |",
        "| wait_mix（50%TMF+50%GLD） | Cash（^IRX / 252） | TMF(2009年)・GLD(2004年)とも期間前半は未上場 |",
        "| TQQQ | TQQQ_CC_RETURN_REBUILT | 合成キャリブレーション済み |",
        "",
    ]

    for row in rows:
        m = row["method"]
        label = "Method A: Stationary Block Bootstrap" if "A" in m else "Method B: Regime-Aware Bootstrap"
        lines += [
            f"---",
            f"",
            f"## {label}",
            "",
            "### 実績値",
            "| CAGR | Vol | MDD | Sharpe |",
            "|-----:|----:|----:|-------:|",
            f"| {row['actual_cagr%']:.2f}% | {row['actual_vol%']:.2f}% "
            f"| {row['actual_mdd%']:.2f}% | {row['actual_sharpe']:.3f} |",
            "",
            "### シミュレーション分布（2,000パス）",
            "| 指標 | P1 | P5 | P25 | P50 | P75 | P95 | P99 |",
            "|------|---:|---:|----:|----:|----:|----:|----:|",
            f"| CAGR% | {row['cagr_p1%']} | {row['cagr_p5%']} | {row['cagr_p25%']} "
            f"| {row['cagr_p50%']} | {row['cagr_p75%']} | {row['cagr_p95%']} | {row['cagr_p99%']} |",
            f"| Vol%  | – | {row['vol_p5%']} | – | {row['vol_p50%']} | – | {row['vol_p95%']} | – |",
            f"| MDD%  | – | {row['mdd_p5%']} | – | {row['mdd_p50%']} | – | {row['mdd_p95%']} | – |",
            f"| Sharpe | – | {row['sharpe_p5']} | – | {row['sharpe_p50']} | – | {row['sharpe_p95']} | – |",
            "",
            "### テールリスク",
            "| 指標 | 値 | 解釈 |",
            "|------|--:|------|",
            f"| 損失確率 | **{row['loss_prob%']:.2f}%** | 全期間で元本割れするパスの割合 |",
            f"| CVaR 5% CAGR | **{row['cvar5_cagr%']:.2f}%** | 下位5%シナリオの平均CAGR |",
            f"| 実績パーセンタイル順位 | **{row['actual_pct_rank']:.0f}th** | 高いほど運依存の可能性 |",
            "",
        ]

    lines += [
        "---",
        "",
        "## 解釈",
        "",
        "- **実績順位が50th付近**: 実績は「ランダムな順序でも再現できる標準的な結果」に相当 → 高い再現性",
        "- **実績順位が80th超**: タイミング・順序への依存度が高く注意が必要",
        "- **Method A ≈ B**: レジーム順序の入れ替えで結果が変わらない → 戦略はレジーム構造に依存しない",
        "- **損失確率 = 0%**: どのリサンプリングパスでも元本を維持 → 長期安定性が高い",
        "- **CVaR 5%**: 最悪5%シナリオ平均でもプラス → テールリスク管理ができている",
        "",
        "## 出力ファイル",
        "",
        "| ファイル | 内容 |",
        "|---------|------|",
        "| `mc_1991_methodA_fan.png` | Method A ファンチャート＋分布 |",
        "| `mc_1991_methodB_fan.png` | Method B ファンチャート＋分布 |",
        "| `mc_1991_comparison.png` | Method A vs B 比較 |",
        "| `mc_1991_summary.csv` | 全数値サマリー |",
    ]

    path = HERE / "MONTE_CARLO_1991_REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved report → {path.name}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Downloading market data ...")
    gspc    = _dl("^GSPC", GSPC_DL_START).rename("GSPC")
    irx     = (_dl("^IRX", IRX_DL_START) / 100.0 / TRADING_DAYS).rename("cash")
    ohlc    = pd.read_csv(OHLC_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    tqqq_cc = ohlc["TQQQ_CC_RETURN_REBUILT"].rename("tqqq_cc")

    # ── Build pre-2005 synthetic canonical ────────────────────────────────────
    print("Simulating pre-2005 synthetic canonical ...")
    pre = simulate_pre2005(gspc, tqqq_cc, irx)
    print(f"  pre-2005: {pre.index[0].date()} – {pre.index[-1].date()}  "
          f"({len(pre)} days)")
    pre_m = compute_metrics(pre["strategy_return"].values)
    print(f"  pre-2005 CAGR={pre_m['cagr']*100:.2f}%  "
          f"Vol={pre_m['vol']*100:.2f}%  MDD={pre_m['mdd']*100:.2f}%")

    # ── Load post-2005 actual canonical ───────────────────────────────────────
    print("Loading post-2005 actual canonical ...")
    post = pd.read_csv(CANON_2005_PATH, parse_dates=["Date"]).set_index("Date").sort_index()
    post = post[["strategy_return", "signal_below_sma"]].rename(
        columns={"signal_below_sma": "is_bear"}
    )
    post["is_bear"] = post["is_bear"].fillna(False).astype(bool)
    print(f"  post-2005: {post.index[0].date()} – {post.index[-1].date()}  "
          f"({len(post)} days)")
    post_m = compute_metrics(post["strategy_return"].values)
    print(f"  post-2005 CAGR={post_m['cagr']*100:.2f}%  "
          f"Vol={post_m['vol']*100:.2f}%  MDD={post_m['mdd']*100:.2f}%")

    # ── Stitch ────────────────────────────────────────────────────────────────
    full = pd.concat([
        pre[["strategy_return", "is_bear"]],
        post[["strategy_return", "is_bear"]],
    ]).sort_index()
    full = full[~full.index.duplicated(keep="last")]

    returns = full["strategy_return"].values.astype(float)
    is_bear = full["is_bear"].values.astype(bool)
    date_idx = full.index
    actual_eq  = np.cumprod(1.0 + np.clip(returns, -0.999999, None))
    actual_met = compute_metrics(returns)

    n_pre  = len(pre)
    n_post = len(post)

    print(f"\nFull stitched: {full.index[0].date()} – {full.index[-1].date()}  "
          f"({len(full)} days)")
    print(f"  CAGR={actual_met['cagr']*100:.2f}%  "
          f"Vol={actual_met['vol']*100:.2f}%  "
          f"MDD={actual_met['mdd']*100:.2f}%  "
          f"Sharpe={actual_met['sharpe']:.3f}")
    bull_eps, bear_eps = extract_episodes(returns, is_bear)
    print(f"  Bull episodes={len(bull_eps)}  Bear episodes={len(bear_eps)}")
    print(f"  Bull days={int((~is_bear).sum())} ({(~is_bear).mean()*100:.1f}%)  "
          f"Bear days={int(is_bear.sum())} ({is_bear.mean()*100:.1f}%)")

    # ── Method A ──────────────────────────────────────────────────────────────
    print(f"\nMethod A (Stationary Block Bootstrap, block={BLOCK_SIZE}d, N={N_SIM}) ...")
    mets_a, eq_a = method_a(returns)
    cagrs_a = [m["cagr"] * 100 for m in mets_a]
    pct_rank_a = float(np.mean(np.array(cagrs_a) <= actual_met["cagr"] * 100)) * 100
    print(f"  P5={np.percentile(cagrs_a,5):.1f}%  P50={np.percentile(cagrs_a,50):.1f}%  "
          f"P95={np.percentile(cagrs_a,95):.1f}%  loss={np.mean([m['final_eq']<1 for m in mets_a])*100:.1f}%  "
          f"actual_rank={pct_rank_a:.0f}th")

    plot_fan(eq_a, actual_eq, mets_a, actual_met,
             "Stitched 1991–2026 (synthetic pre-2005 + actual post-2005)",
             "Method A: Stationary Block Bootstrap",
             OUT_DIR / "mc_1991_methodA_fan.png", date_idx)

    # ── Method B ──────────────────────────────────────────────────────────────
    print(f"\nMethod B (Regime-Aware Bootstrap, N={N_SIM}) ...")
    mets_b, eq_b = method_b(returns, is_bear)
    cagrs_b = [m["cagr"] * 100 for m in mets_b]
    pct_rank_b = float(np.mean(np.array(cagrs_b) <= actual_met["cagr"] * 100)) * 100
    print(f"  P5={np.percentile(cagrs_b,5):.1f}%  P50={np.percentile(cagrs_b,50):.1f}%  "
          f"P95={np.percentile(cagrs_b,95):.1f}%  loss={np.mean([m['final_eq']<1 for m in mets_b])*100:.1f}%  "
          f"actual_rank={pct_rank_b:.0f}th")

    plot_fan(eq_b, actual_eq, mets_b, actual_met,
             "Stitched 1991–2026 (synthetic pre-2005 + actual post-2005)",
             "Method B: Regime-Aware Bootstrap",
             OUT_DIR / "mc_1991_methodB_fan.png", date_idx)

    plot_comparison(eq_a, eq_b, actual_eq, actual_met, date_idx)

    # ── Summary CSV ───────────────────────────────────────────────────────────
    def summarise(mets, method_name):
        cagrs = np.array([m["cagr"]   for m in mets]) * 100
        vols  = np.array([m["vol"]    for m in mets]) * 100
        mdds  = np.array([m["mdd"]    for m in mets]) * 100
        sharps = np.array([m["sharpe"] for m in mets])
        def p(arr, pct): return round(float(np.percentile(arr, pct)), 2)
        return {
            "period": "1991_stitched", "method": method_name,
            "n_sim": len(mets),
            "actual_cagr%":  round(actual_met["cagr"]  * 100, 2),
            "actual_vol%":   round(actual_met["vol"]   * 100, 2),
            "actual_mdd%":   round(actual_met["mdd"]   * 100, 2),
            "actual_sharpe": round(actual_met["sharpe"], 3),
            "cagr_p1%": p(cagrs,1), "cagr_p5%": p(cagrs,5),
            "cagr_p25%": p(cagrs,25), "cagr_p50%": p(cagrs,50),
            "cagr_p75%": p(cagrs,75), "cagr_p95%": p(cagrs,95),
            "cagr_p99%": p(cagrs,99),
            "vol_p5%": p(vols,5), "vol_p50%": p(vols,50), "vol_p95%": p(vols,95),
            "mdd_p5%": p(mdds,5), "mdd_p50%": p(mdds,50), "mdd_p95%": p(mdds,95),
            "loss_prob%": round(float(np.mean([m["final_eq"]<1 for m in mets]))*100, 2),
            "cvar5_cagr%": round(float(np.mean(cagrs[cagrs <= p(cagrs,5)])), 2),
            "actual_pct_rank": round(float(np.mean(cagrs <= actual_met["cagr"]*100))*100, 1),
            "sharpe_p5":  p(sharps,5), "sharpe_p50": p(sharps,50), "sharpe_p95": p(sharps,95),
        }

    rows = [summarise(mets_a, "A_stationary_block"), summarise(mets_b, "B_regime_aware")]
    csv_path = OUT_DIR / "mc_1991_summary.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f"\nSaved → {csv_path.name}")

    write_report(rows, n_pre, n_post)


if __name__ == "__main__":
    main()
