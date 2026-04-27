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
- [`soxl_backtest/`](./soxl_backtest/)
  - `SOXL` を semiconductor benchmark proxy から長期延長する workspace
  - `legacy SOX / modern SOXX / hybrid` を比較して canonical model を選びます
- [`tmf_backtest/`](./tmf_backtest/)
  - `TMF` を long-duration Treasury proxy から `1991` まで延長する workspace
  - `VUSTX -> TLT` benchmark proxy と `TMF` overlap calibration を含みます
- [`ugl_backtest/`](./ugl_backtest/)
  - `UGL` を `GLD` proxy で `2005-12-20` まで延長する workspace
  - overlap calibration と canonical stitched export を含みます
- [`robust_rsi_optimization/`](./robust_rsi_optimization/)
  - `UVIX` high-RSI leg の `entry/exit` を OOS fold と plateau smoothing で頑健化する workspace
  - annual validation folds, robust score, holdout comparison, figure outputs を含みます
- [`docs/letf_backtest_methodology.md`](./docs/letf_backtest_methodology.md)
  - testfol, GitHub research, official methodology, 現状ベストプラクティスをまとめたノート

## Current Focus

- canonical dataset: `stitched_uvix_longvol_2x`
- backtest window: `2005-12-20 .. 2026-04-17`
- signal source: `^GSPC`
- naive full-sample optimum: `entry = 69.4`, `exit = 65.4`
- robust OOS optimum: `entry = 67.9`, `exit = 65.5`
- robust validation split: `2006-01-03 .. 2022-12-30`, final holdout: `2023-01-03 .. 2026-04-17`

`TECL SMA160 Rotation` workspace の provisional canonical candidate:

- strategy name: `prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit`
- backtest window: `2010-02-12 .. 2026-04-17`
- base signal: previous `GSPC Close SMA160`, judged against current `GSPC Open`
- TQQQ re-entry: running drawdown from `TQQQ Open` peak, `alpha=54.5%`
- UVIX overlay: `GSPC open-implied RSI14`, entry `69.5`, exit `RSI <= 68.5` or `TQQQ Open <= entry-time TQQQ Open`
- low-RSI TQQQ override: entry `RSI < 30`, exit `RSI >= 32.5`
- result: CAGR `106.46%`, vol `64.03%`, max drawdown `-65.68%`
- note: provisional only; OOS / slippage / execution-cost checks are still pending

`TQQQ` workspace の current canonical result:

- benchmark: `^NDX`
- history window: `1991-01-02 .. 2026-04-17`
- live calibration anchor: `2010-02-11`
- calibrated financing multiplier: `0.9133907212`
- canonical export: `tqqq_backtest/output/tqqq_extension_1991.csv`

`SOXL` workspace の current canonical result:

- requested history start: `1993-01-01`
- actual reproducible history start: `1994-05-04`
- live calibration anchor: `2010-03-11`
- canonical model: `hybrid_sox_to_soxx`
- calibrated financing multiplier: `0.7849591928`
- canonical export: `soxl_backtest/output/soxl_extension.csv`

`TMF` workspace の current canonical result:

- requested history start: `1991-01-01`
- actual reproducible history start: `1991-01-02`
- live calibration anchor: `2009-04-16`
- canonical legacy proxy variant: `raw VUSTX`
- calibrated financing multiplier: `2.8684935350`
- canonical export: `tmf_backtest/output/tmf_extension_1991.csv`

`UGL` workspace の current canonical result:

- requested history start: `2005-12-20`
- actual reproducible history start: `2005-12-20`
- live calibration anchor: `2008-12-03`
- calibrated financing multiplier: `2.2053200000`
- canonical export: `ugl_backtest/output/ugl_extension_20051220.csv`

この状態で、`uvix_backtest/rsi_entry_exit_optimize.py` は sibling workspaces の stitched `TQQQ/SOXL/TMF/UGL` series を既定で読むので、`stitched_uvix_longvol_2x` を `2005-12-20 .. latest` で最適化できます。

詳細は [`uvix_backtest/README.md`](./uvix_backtest/README.md), [`tqqq_backtest/README.md`](./tqqq_backtest/README.md), [`soxl_backtest/README.md`](./soxl_backtest/README.md), [`tmf_backtest/README.md`](./tmf_backtest/README.md), [`ugl_backtest/README.md`](./ugl_backtest/README.md), [`robust_rsi_optimization/README.md`](./robust_rsi_optimization/README.md) を参照してください。
