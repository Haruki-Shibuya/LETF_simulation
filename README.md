# LETF Simulation

この repository は、レバレッジETF系のシミュレーションや最適化をまとめるための親 repo です。
現時点では、`UVIX` を使う高RSIレジーム戦略の検証と、`TQQQ` を `1991` まで延長した canonical proxy をそれぞれ独立 workspace に整理しています。

## Current Layout

- [`uvix_backtest/`](./uvix_backtest/)
  - `UVIX` high-RSI regime strategy の backtest / optimization / robustness analysis
  - README, scripts, CSV outputs, plot artifacts を含みます
- [`tqqq_backtest/`](./tqqq_backtest/)
  - `TQQQ` を `^NDX` から `1991` まで延長する synthetic / stitched workspace
  - calibration summary, overlap diagnostics, long-history export を含みます

## Current Focus

- canonical dataset: `stitched_uvix_longvol_2x`
- backtest window: `2011-01-03 .. 2026-04-17`
- signal source: `^GSPC`
- best high-RSI thresholds: `entry = 69.4`, `exit = 66.5`
- leave-one-episode-out robustness: `62 / 79` episodes で最適解不変

`TQQQ` workspace の current canonical result:

- benchmark: `^NDX`
- history window: `1991-01-02 .. 2026-04-17`
- live calibration anchor: `2010-02-11`
- calibrated financing multiplier: `0.9133907212`
- canonical export: `tqqq_backtest/output/tqqq_extension_1991.csv`

詳細は [`uvix_backtest/README.md`](./uvix_backtest/README.md) と [`tqqq_backtest/README.md`](./tqqq_backtest/README.md) を参照してください。
