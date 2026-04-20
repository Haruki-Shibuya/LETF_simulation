# LETF Simulation

この repository は、レバレッジETF系のシミュレーションや最適化をまとめるための親 repo です。
現時点では、`UVIX` を使う高RSIレジーム戦略の検証を [`uvix_backtest/`](./uvix_backtest/) に整理しています。

## Current Layout

- [`uvix_backtest/`](./uvix_backtest/)
  - `UVIX` high-RSI regime strategy の backtest / optimization / robustness analysis
  - README, scripts, CSV outputs, plot artifacts を含みます

## Current Focus

- canonical dataset: `stitched_uvix_longvol_2x`
- backtest window: `2011-01-03 .. 2026-04-17`
- signal source: `^GSPC`
- best high-RSI thresholds: `entry = 69.4`, `exit = 66.5`
- leave-one-episode-out robustness: `62 / 79` episodes で最適解不変

詳細は [`uvix_backtest/README.md`](./uvix_backtest/README.md) を参照してください。
