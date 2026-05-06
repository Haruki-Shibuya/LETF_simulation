# Forward P/E Filter Test Results

Last run: 2026-05-04 JST

## Inputs

- Forward P/E data:
  - `output/valuation_forward_pe_2005_sim_daily_ffill.csv`
  - S&P 500 forward P/E: Doinoff monthly, extended with Trendonify for 2026.
  - QQQ underlier forward P/E: Nasdaq-100 Trendonify monthly.
- 2005 canonical path:
  - `output/canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220_daily_path.csv`
- 2010 canonical path:
  - `output/canonical_prev_close_signal_same_open_exec_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_daily_path.csv`

The test keeps the existing canonical trading logic fixed, then applies valuation filters on top of the selected leg.

## Tested Filter Families

1. Hard filters:
   - High S&P 500 forward P/E: replace TQQQ with safety assets.
   - High Nasdaq-100 forward P/E: replace TQQQ with safety assets.
   - Low forward P/E: replace safety assets with TQQQ.
   - Forward P/E condition for allowing or blocking UVIX.
   - Two-variable S&P 500 + Nasdaq-100 thresholds.

2. Weighted filters:
   - At high forward P/E, reduce TQQQ exposure to 75%, 50%, 25%, or 0%, with the rest in safety assets.
   - At low forward P/E, add partial TQQQ exposure on safety-asset days.
   - Two-variable S&P 500 + Nasdaq-100 versions.

## Baselines

| Period | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| 2005-12-20 to 2026-04-17 | 113.02% | 56.58% | -69.63% | 2.00 |
| 2010-02-12 to 2026-04-17 | 108.40% | 64.53% | -77.84% | 1.68 |

## Main Result

Forward P/E filters did not produce a material CAGR improvement over canonical.

- 2005 start:
  - No tested non-trivial filter improved both CAGR and vol.
  - The best CAGR result is the baseline itself.
- 2010 start:
  - One tiny UVIX gating case improved both metrics, but it changed only 0.07% of days and is not meaningful enough to treat as robust.
  - Rule: block UVIX when S&P 500 forward P/E is below 12.5.
  - Result: CAGR 108.97%, vol 64.43%, max DD unchanged at -77.84%.

## Useful Risk-Control Results

Forward P/E is more useful as a risk-control knob than as a CAGR booster.

### 2005 Start

Best CAGR/vol style result:

| Rule | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.5, hold 75% TQQQ + 25% safety assets instead of 100% TQQQ | 103.22% | 50.44% | -63.77% | 2.05 |

This lowers CAGR by about 9.8 percentage points, but improves vol by about 6.1 percentage points and max drawdown by about 5.9 percentage points.

More defensive examples:

| Rule | CAGR | Vol | Max DD |
|---|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.0, hold 75% TQQQ + 25% safety assets | 101.60% | 50.04% | -64.14% |
| If Nasdaq-100 forward P/E > 19.0, hold 50% TQQQ + 50% safety assets | 92.63% | 46.89% | -57.63% |
| If Nasdaq-100 forward P/E > 19.0, hold 25% TQQQ + 75% safety assets | 80.20% | 44.84% | -53.47% |

### 2010 Start

Best CAGR/vol style result:

| Rule | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.5, hold 75% TQQQ + 25% safety assets instead of 100% TQQQ | 95.59% | 55.95% | -72.35% | 1.71 |

This lowers CAGR by about 12.8 percentage points, but improves vol by about 8.6 percentage points and max drawdown by about 5.5 percentage points.

More defensive examples:

| Rule | CAGR | Vol | Max DD |
|---|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.0, hold 75% TQQQ + 25% safety assets | 94.40% | 55.53% | -70.62% |
| If S&P 500 forward P/E > 15.5, hold 75% TQQQ + 25% safety assets | 96.94% | 57.36% | -70.01% |
| If S&P 500 forward P/E > 20.5, hold 75% TQQQ + 25% safety assets | 100.70% | 62.14% | -78.11% |

## Interpretation

The current canonical strategy already uses tactical trend, drawdown, RSI, BB, and UVIX logic. Simple forward P/E overlays mostly remove profitable TQQQ exposure and therefore tend to reduce CAGR.

The useful pattern is not "valuation improves CAGR." The useful pattern is:

- Nasdaq-100 forward P/E can reduce realized vol and drawdown if it is used to partially reduce TQQQ exposure.
- The tradeoff is a clear CAGR reduction.
- Full de-risking is usually too aggressive.
- 75% TQQQ / 25% safety assets at high Nasdaq-100 forward P/E is the least destructive risk-control version among the tested rules.

---

## Z-Score Approach: SP500 fwd P/E rolling z-score > +2σ → Safe Assets

Last updated: 2026-05-06

### 概要

絶対値しきい値ではなく、SP500フォワードPERの**月次ローリングzスコア**が+2σを超えたタイミングでTQQQをwait_mix（またはCash）に切り替える手法。

- zスコア計算: `z_W(M) = (PE_M − mean(PE_{M-W:M})) / std(PE_{M-W:M})`、ウィンドウW = 18・24・36ヶ月
- ルック・アヘッドバイアス対策: 月次EPS/PEを1ヶ月ラグしてから日次にforward-fill
- 発動条件: `z > +2.0 AND selected_leg == TQQQ` → wait_mix に切り替え

### 期間別比較（z-score > +2σ → 切り替え）

#### Post-2005（2005-12-20〜、実カノニカル）

| Variant | CAGR% | Δ | Vol% | Δ | MDD% | CAGR/Vol |
|---------|------:|---|-----:|---|-----:|---------:|
| Baseline（実カノニカル） | 113.02% | — | 56.58% | — | -69.63% | 1.998 |
| z18m > 2.0σ → wait_mix | 114.98% | **+1.96** | 55.95% | -0.63 | -69.63% | 2.055 |
| z24m > 2.0σ → wait_mix | **115.71%** | **+2.69** | **55.94%** | **-0.64** | **-69.63%** | **2.068** |
| z36m > 2.0σ → wait_mix | 111.22% | -1.80 | 55.69% | -0.89 | -69.63% | 1.997 |

→ **z18m・z24mはCAGR・Vol両方を改善**。z36mは逆効果。

#### Pre-2005（1991-01-01〜2005-12-19、UVIX→Cashの合成カノニカル）

| Variant | CAGR% | Δ | Vol% | Δ | MDD% | CAGR/Vol |
|---------|------:|---|-----:|---|-----:|---------:|
| Baseline（合成カノニカル） | 22.89% | — | 65.16% | — | -81.13% | 0.351 |
| z18m > 2.0σ → Cash | 21.68% | -1.21 | 62.72% | -2.44 | -81.13% | 0.346 |
| z24m > 2.0σ → Cash | 20.99% | -1.90 | 62.81% | -2.35 | -81.13% | 0.334 |
| z36m > 2.0σ → Cash | 17.98% | -4.91 | 61.44% | -3.72 | -81.13% | 0.293 |

→ **Pre-2005は全ウィンドウでCAGR悪化**。1990年代バブル膨張フェーズで何度も発動するが市場はその後も上昇し続けたため。

#### Full Period（1991〜2026、スティッチ）

| Variant | CAGR% | Δ | Vol% | Δ | CAGR/Vol |
|---------|------:|---|-----:|---|----------:|
| Baseline（スティッチ） | 68.63% | — | 60.39% | — | 1.136 |
| z18m → Cash/wait_mix | 68.81% | +0.18 | 58.94% | **-1.45** | 1.167 |
| z24m → Cash/wait_mix | 68.73% | +0.10 | 58.98% | -1.41 | 1.165 |
| z36m → Cash/wait_mix | 64.92% | -3.71 | 58.23% | -2.16 | 1.115 |

→ 全期間ではz18m/z24mがCAGRほぼ中立・Volわずか改善。

### エピソード分析（2005-12-20〜、z24m）

発動エピソードは20年間でわずか**約8件**（取引日の2.5%）。実質的な勝敗は**4勝3敗1分け**程度。

- 過去の暴落直前・高バリュエーション局面（2007・2018・2020等）でのみ発動するため、サンプル数は構造的に少ない
- エピソードが少ないため、統計的信頼性は限定的
- 3勝分が同一GFCクラスターに集中しており、独立サンプルとしてはさらに少ない

### 評価・位置づけ

- **現時点ではカノニカルに組み込まない**
- ただし「バリュエーション高騰時の逃避」という発想は有効性を示しており、**候補シグナルとして保留**
- Post-2005限定では CAGRとVolの両方が改善（特にz24m: CAGR +2.69pp, Vol -0.64pp）
- Pre-2005まで拡張すると効果が消失・逆転する点に注意（バブル膨張期フォールスアラーム問題）
- より長期のサンプルが蓄積されるか、次の高バリュエーション局面での検証を待って再評価する

### 関連スクリプト・出力ファイル

- `test_pe_zscore_reentry.py` — zスコア再参入（低z→TQQQ買戻し）の最適化
- `plot_pe_override_periods.py` — 2005年起点のオーバーライド期間可視化
- `plot_pe_override_1991.py` — 1991年起点の拡張シミュレーション
- `compare_pe_filter_periods.py` — 期間別比較表生成
- `output/pe_filter_period_comparison.csv` — 上記比較表のCSV
- `output/pe_zscore_reentry_results.csv` — 再参入最適化結果
- `output/plot_pe_override_periods_2005.png` — オーバーライド期間チャート
- `output/plot_pe_override_1991.png` — 1991年起点チャート
- `output/forward_pe_plot.png` — SP500/NASDAQ-100 フォワードPER推移図

---

## Output Files

- `output/forward_pe_filter_tests_summary.csv`
- `output/forward_pe_filter_tests_from_20051220.csv`
- `output/forward_pe_filter_tests_from_20100212.csv`
- `output/forward_pe_weighted_allocation_tests_summary.csv`
- `output/forward_pe_weighted_allocation_tests_from_20051220.csv`
- `output/forward_pe_weighted_allocation_tests_from_20100212.csv`
- `test_forward_pe_filters.py`
