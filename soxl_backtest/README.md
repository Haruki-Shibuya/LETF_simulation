# SOXL Backtest Workspace

このフォルダは、`SOXL` を semiconductor benchmark proxy から長期延長するための canonical workspace です。

`SOXL` は `TQQQ` より benchmark history が扱いにくく、さらに `2021-08-25` 前後で benchmark が `PHLX Semiconductor Sector Index` から `ICE Semiconductor Index` に切り替わっています。そこでここでは、1 本の underlier を前提にせず、複数の benchmark candidate を live `SOXL` overlap で比較してから canonical model を選びます。

## Method

- live LETF: `SOXL`
- legacy benchmark proxy: `^SOX`
- modern benchmark proxy: `SOXX`
- financing proxy: FRED `DGS3MO`
- switch date: `2021-08-25`
- base model:
  - `daily return = 3.0 * benchmark daily return - annual fee / 252 - k * DGS3MO / 252`
- candidate benchmarks:
  - `legacy_sox`
  - `modern_soxx_proxy`
  - `hybrid_sox_to_soxx`
- `k` は各 candidate ごとに live `SOXL` overlap の cumulative log return が一致するように校正
- canonical は live overlap の `daily_return_mae_bps` が最小の model
- canonical level series は return-space stitched:
  - pre-inception: calibrated synthetic returns
  - `2010-03-11` 以降: actual `SOXL` adjusted close returns

## Current Canonical Result

現状の canonical selection は `hybrid_sox_to_soxx` です。

ポイント:

- requested history start: `1993-01-01`
- actual reproducible history start: `1994-05-04`
- history end: `2026-04-17`
- actual `SOXL` anchor: `2010-03-11`
- anchor price: `0.6008639336`
- canonical model: `hybrid_sox_to_soxx`
- calibrated financing multiplier: `0.7849591928`
- canonical stitched start level on `1994-05-04`: `343.0368036297`
- canonical stitched end level on `2026-04-17`: `94.6800003052`

Candidate overlap diagnostics (`2010-03-12 .. 2026-04-17`):

- `hybrid_sox_to_soxx`
  - daily return corr `0.9971484`
  - MAE `18.0398 bps`
- `modern_soxx_proxy`
  - daily return corr `0.9969780`
  - MAE `22.5837 bps`
- `legacy_sox`
  - daily return corr `0.9964214`
  - MAE `22.5884 bps`

つまり、current benchmark の proxy を全期間に当てるより、`legacy SOX -> modern SOXX` の hybrid が live `SOXL` に一番近いです。

## Files

- [extend_soxl_history.py](./extend_soxl_history.py)
  - candidate benchmark 比較と canonical series 生成
- [output/soxl_extension.csv](./output/soxl_extension.csv)
  - 長期 export
- [output/soxl_extension_summary.csv](./output/soxl_extension_summary.csv)
  - canonical model summary
- [output/soxl_model_diagnostics.csv](./output/soxl_model_diagnostics.csv)
  - candidate benchmark diagnostics
- [output/soxl_overlap_validation.png](./output/soxl_overlap_validation.png)
  - overlap comparison plot
- [output/soxl_extension.png](./output/soxl_extension.png)
  - canonical long-history plot

Main outputs:

- [output/soxl_extension.csv](./output/soxl_extension.csv)
- [output/soxl_extension_summary.csv](./output/soxl_extension_summary.csv)
- [output/soxl_model_diagnostics.csv](./output/soxl_model_diagnostics.csv)
- [output/soxl_overlap_validation.png](./output/soxl_overlap_validation.png)
- [output/soxl_extension.png](./output/soxl_extension.png)

## Command

```bash
/usr/bin/python3 extend_soxl_history.py --history-start 1993-01-01
```
