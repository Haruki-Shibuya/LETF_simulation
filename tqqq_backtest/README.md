# TQQQ Backtest Workspace

このフォルダは、`TQQQ` を `1991` まで延長するための canonical workspace です。
目的は「実 `TQQQ` をそのまま過去に埋める」ことではなく、`Nasdaq-100` を benchmark にした daily-reset 3x model を組み、実 `TQQQ` の live overlap で drag を点検したうえで pre-inception を延長することです。

## Method

- benchmark: `^NDX`
- live LETF: `TQQQ`
- financing proxy: FRED `DGS3MO`
- model:
  - daily return = `3.0 * NDX daily return - annual fee / 252 - k * DGS3MO / 252`
- `k` は live `TQQQ` overlap で cumulative log return が一致するように校正
- canonical level series は return-space stitched:
  - pre-inception: calibrated synthetic returns
  - `2010-02-11` 以降: actual `TQQQ` adjusted close returns

## Current Canonical Result

- history window: `1991-01-02 .. 2026-04-17`
- actual `TQQQ` anchor: `2010-02-11`
- anchor price: `0.2060553133`
- calibrated financing multiplier: `0.9133907212`
- canonical pre-1991 start level on `1991-01-02`: `0.1364705586`
- canonical stitched end level on `2026-04-17`: `58.5900001526`

Overlap diagnostics (`2010-02-12 .. 2026-04-17`):

- fee-only model:
  - daily return corr `0.9985869`
  - MAE `14.3412 bps`
  - overlap growth multiple `353.64x` vs actual `284.34x`
- theoretical `fee + 2x cash` model:
  - daily return corr `0.9985958`
  - MAE `14.2485 bps`
  - overlap growth multiple `219.35x` vs actual `284.34x`
- calibrated canonical model:
  - daily return corr `0.9985928`
  - MAE `14.2694 bps`
  - overlap growth multiple `284.34x`, actual と一致

## Why This Shape

`TQQQ` は `UVIX` よりかなり扱いやすいです。
`UVIX` は VIX futures basket を再現しないと benchmark-faithful になりませんが、`TQQQ` は `Nasdaq-100` の daily-reset 3x をベースに考えるのが自然です。

一方で、実 `TQQQ` は単純な `3x * NDX` ではなく、fees / financing / tracking が入るので、pre-inception extension では live overlap calibration を入れています。

## Files

- [extend_tqqq_history.py](./extend_tqqq_history.py)
  - synthetic / stitched series の生成
- [output/tqqq_extension_1991.csv](./output/tqqq_extension_1991.csv)
  - 1991 以降の canonical data export
- [output/tqqq_extension_summary.csv](./output/tqqq_extension_summary.csv)
  - calibration summary
- [output/tqqq_model_diagnostics.csv](./output/tqqq_model_diagnostics.csv)
  - overlap diagnostics for fee-only / theoretical / calibrated models
- [output/tqqq_overlap_validation.png](./output/tqqq_overlap_validation.png)
  - inception 以降の normalized overlap plot
- [output/tqqq_1991_extension.png](./output/tqqq_1991_extension.png)
  - long history stitched plot

Main outputs:

- [output/tqqq_extension_1991.csv](./output/tqqq_extension_1991.csv)
- [output/tqqq_extension_summary.csv](./output/tqqq_extension_summary.csv)
- [output/tqqq_model_diagnostics.csv](./output/tqqq_model_diagnostics.csv)
- [output/tqqq_overlap_validation.png](./output/tqqq_overlap_validation.png)
- [output/tqqq_1991_extension.png](./output/tqqq_1991_extension.png)

## Command

```bash
/usr/bin/python3 extend_tqqq_history.py --history-start 1991-01-01
```
