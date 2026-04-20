# UGL Backtest Workspace

このフォルダは、`UGL` を `2005-12-20` まで延長するための canonical workspace です。

`UGL` は `2x gold` の LETF ですが、今回は `2005-12-20` 起点で十分なので、underlier proxy は `GLD` をそのまま使います。`GLD` は `UGL` より前からあるため、追加の legacy proxy は不要です。

## Method

- live LETF: `UGL`
- benchmark proxy: `GLD`
- financing proxy: FRED `DGS3MO`
- model:
  - `daily return = 2.0 * GLD daily return - annual fee / 252 - k * DGS3MO / 252`
- `k` は live `UGL` overlap で cumulative log return が一致するように校正
- canonical level series は return-space stitched:
  - pre-inception: calibrated synthetic returns
  - `UGL` inception 以降: actual `UGL` adjusted close returns

## Files

- [extend_ugl_history.py](./extend_ugl_history.py)
  - canonical UGL series 生成
- [output/ugl_extension_20051220.csv](./output/ugl_extension_20051220.csv)
  - `2005-12-20` 以降の canonical export
- [output/ugl_extension_summary.csv](./output/ugl_extension_summary.csv)
  - summary
- [output/ugl_model_diagnostics.csv](./output/ugl_model_diagnostics.csv)
  - overlap diagnostics
- [output/ugl_overlap_validation.png](./output/ugl_overlap_validation.png)
  - overlap validation plot
- [output/ugl_extension.png](./output/ugl_extension.png)
  - long-history plot

## Current Canonical Result

- requested history start: `2005-12-20`
- actual reproducible history start: `2005-12-20`
- history end: `2026-04-17`
- actual `UGL` anchor: `2008-12-03`
- anchor price: `6.2050004005`
- calibrated financing multiplier: `2.2053200000`
- canonical stitched start level on `2005-12-20`: `3.980364`
- canonical stitched end level on `2026-04-17`: `65.650002`

UGL overlap diagnostics (`2008-12-04 .. 2026-04-17`):

- fee-only
  - daily return corr `0.9965920`
  - MAE `10.5350 bps`
- theoretical `fee + 1x cash`
  - daily return corr `0.9965981`
  - MAE `10.4774 bps`
- calibrated canonical model
  - daily return corr `0.9965905`
  - MAE `10.5072 bps`
  - overlap log-return gap はほぼ `0`

## Command

```bash
/usr/bin/python3 extend_ugl_history.py --history-start 2005-12-20
```
