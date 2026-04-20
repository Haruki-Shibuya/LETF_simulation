# Robust RSI Threshold Optimization

この workspace は、`UVIX` high-RSI leg の `entry/exit` を **sample-specific な尖った最大点** ではなく、**時系列 OOS で残りやすい点**として選ぶためのものです。

## Method

使っているデータと戦略本体は [`uvix_backtest/`](../uvix_backtest/) と同じです。

- dataset: `stitched_uvix_longvol_2x`
- signal source: `^GSPC`
- backtest start: `2005-12-20`
- compare legs:
  - high RSI: `UVIX`
  - low RSI: `SOXL`
  - trend: `TQQQ`
  - fallback: `UGL 50% / TMF 50%`

頑健化の流れは次です。

1. `2005-12-20 .. 2022-12-30` を validation、`2023-01-03 .. latest` を final holdout に分ける
2. validation は calendar-year ごとの annual OOS folds に分ける
3. 各 `entry/exit` について、各 fold の annualized CAGR を計算する
4. `median fold CAGR` と `p10 fold CAGR` を作る
5. さらに `entry/exit` 平面上で近傍平均を取り、plateau を見る
6. `robust score = 0.5 * plateau_median + 0.5 * plateau_p10` で最終選抜する

要するに、

- `median` で「普段どれくらい稼げるか」
- `p10` で「悪い fold でもどれくらい残るか」
- `plateau smoothing` で「一点だけの偶然の山」を避ける

という 3 点を同時に見ています。

## Files

- `compute_robust_rsi_optimum.py`
  - annual OOS fold 集計
  - plateau smoothing
  - robust optimum 選抜
  - summary CSV と figure 生成
- `output/validation_folds.csv`
  - validation fold 一覧
- `output/parameter_metrics.csv`
  - full grid の robust evaluation 指標
- `output/top20_by_robust_score.csv`
  - robust score 上位 20 点
- `output/selection_summary.csv`
  - `robust_optimum`, `validation_total_max`, `baseline_71_68` の比較
- `output/*.png`
  - heatmaps と比較図

## Current Result

現時点の既定 split は次です。

- validation: `2006-01-03 .. 2022-12-30`
- holdout: `2023-01-03 .. 2026-04-17`

この条件での主な結果:

- `robust_optimum`: `entry = 67.9`, `exit = 65.5`
  - validation median fold CAGR: `94.52%`
  - validation p10 fold CAGR: `9.02%`
  - holdout CAGR: `80.28%`
- `validation_total_max`: `entry = 69.0`, `exit = 68.2`
  - validation total CAGR: `94.78%`
  - validation p10 fold CAGR: `-11.35%`
  - holdout CAGR: `78.03%`

つまり、`69.0 / 68.2` は validation 全体では強いものの bad-fold 耐性が弱く、`67.9 / 65.5` の方が OOS の安定性を優先した pick になっています。

## Run

```bash
/usr/bin/python3 compute_robust_rsi_optimum.py \
  --backtest-start 2005-12-20 \
  --validation-start 2006-01-01 \
  --holdout-start 2023-01-01 \
  --entry-step 0.1 \
  --exit-step 0.1 \
  --plateau-radius 0.3
```

## Interpretation

`validation_total_max` は、validation 全期間を 1 ブロックとして見た単純最大点です。
これは依然として sample-specific な spike を拾いやすいので、採用値は基本的に `robust_optimum` を優先します。

最終判断では、少なくとも次を確認してください。

- `validation_median_fold_cagr_heatmap.png`
- `validation_p10_fold_cagr_heatmap.png`
- `plateau_robust_score_heatmap.png`
- `holdout_cagr_heatmap.png`
- `selection_summary.csv`
