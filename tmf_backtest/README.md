# TMF Backtest Workspace

このフォルダは、`TMF` を long-duration Treasury proxy から `1991` まで延長するための canonical workspace です。

`TMF` は `SOXL` より素直で、modern underlier proxy として `TLT` を使えます。ただし `TLT` の inception は `2002-07-30` なので、pre-2002 を埋めるためにここでは `VUSTX` を legacy proxy に使い、`TLT` overlap で beta を校正してから benchmark-like series を作ります。

## Method

- live LETF: `TMF`
- modern benchmark proxy: `TLT`
- legacy benchmark proxy: `VUSTX`
- financing proxy: FRED `DGS3MO`
- benchmark-like series:
  - `pre-TLT`: raw `VUSTX` return
  - `TLT inception` 以降: actual `TLT` return
- TMF model:
  - `daily return = 3.0 * long_treasury_proxy_return - annual fee / 252 - k * DGS3MO / 252`
- `k` は live `TMF` overlap で cumulative log return が一致するように校正
- canonical level series は return-space stitched:
  - pre-inception: calibrated synthetic returns
  - `2009-04-16` 以降: actual `TMF` adjusted close returns

`VUSTX` については raw と beta-scaled の両方を `TLT` overlap で点検しますが、canonical は **raw `VUSTX`** を使います。理由は、scaled 版は daily MAE は少し良くなる一方で、長期 cumulative growth を `TLT` より上に持ち上げすぎるためです。

## Files

- [extend_tmf_history.py](./extend_tmf_history.py)
  - benchmark proxy calibration と canonical TMF series 生成
- [output/tmf_extension_1991.csv](./output/tmf_extension_1991.csv)
  - 1991 以降の canonical export
- [output/tmf_extension_summary.csv](./output/tmf_extension_summary.csv)
  - summary
- [output/tlt_proxy_diagnostics.csv](./output/tlt_proxy_diagnostics.csv)
  - `VUSTX -> TLT` proxy diagnostics
- [output/tmf_model_diagnostics.csv](./output/tmf_model_diagnostics.csv)
  - `TMF` overlap diagnostics
- [output/tlt_proxy_validation.png](./output/tlt_proxy_validation.png)
  - `TLT` proxy validation plot
- [output/tmf_overlap_validation.png](./output/tmf_overlap_validation.png)
  - `TMF` overlap validation plot
- [output/tmf_1991_extension.png](./output/tmf_1991_extension.png)
  - long-history plot

## Current Canonical Result

- requested history start: `1991-01-01`
- actual reproducible history start: `1991-01-02`
- history end: `2026-04-17`
- actual `TMF` anchor: `2009-04-16`
- anchor price: `99.5227127075`
- canonical legacy proxy variant: `raw VUSTX`
- legacy proxy beta diagnostics value: `1.0709125623`
- calibrated financing multiplier: `2.8684935350`
- canonical stitched start level on `1991-01-02`: `10.0859087003`
- canonical stitched end level on `2026-04-17`: `36.6899986267`

Proxy diagnostics (`TLT` vs `VUSTX`, `2002-07-30 .. 2026-04-17`):

- raw `VUSTX`
  - daily return corr `0.9644139`
  - MAE `13.3216 bps`
  - overlap log-return gap `0.4070`
- scaled `VUSTX`
  - daily return corr `0.9644139`
  - MAE `11.6847 bps`
  - overlap log-return gap `0.4831`

`scaled VUSTX` の方が daily MAE は低いですが、長期 cumulative growth をより強く持ち上げるので、canonical では raw `VUSTX` を採っています。

TMF overlap diagnostics (`2009-04-17 .. 2026-04-17`):

- fee-only
  - daily return corr `0.9967298`
  - MAE `14.5861 bps`
- theoretical `fee + 2x cash`
  - daily return corr `0.9967445`
  - MAE `14.4923 bps`
- calibrated canonical model
  - daily return corr `0.9967425`
  - MAE `14.5025 bps`
  - overlap growth multiple `0.3565x` vs actual `0.3687x`

## Command

```bash
/usr/bin/python3 extend_tmf_history.py --history-start 1991-01-01
```
