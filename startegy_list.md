# Strategy List

このファイルは、これまで試した dynamic allocation / regime rotation 系の戦略と、その保存用の仮名をまとめた一覧です。

## 1. Strategy Family

### `testfol_original_spy_uvix`
- 元画像の testfol 系。
- signal source は `SPY`。
- high RSI は `UVIX`。
- low RSI は `SOXL`。
- trend は `TQQQ`。
- fallback は `GLD/TLT` 系。

### `uvix_rotation_canonical`
- 現在の repo の正系。
- signal source は canonical 実装上 `^GSPC`。
- high RSI は stitched `UVIX`。
- low RSI は canonical `SOXL`。
- trend は canonical `TQQQ`。
- fallback は canonical `UGL 50% + TMF 50%`。

### `legacy_spy_signal_uvix_rotation`
- canonical 化前の `SPY` signal 版。
- 構造は `UVIX / SOXL / TQQQ / UGL + TMF`。
- signal source が `SPY` のまま。

### `cashx_highrsi_rotation`
- high RSI leg だけ `UVIX` の代わりに `CASHX` を使う版。

### `xlk_highrsi_source_rotation`
- high RSI 判定 source だけ `XLK` に差し替えた版。
- low RSI と SMA は `SPY` 固定。

### `xlk_all_signal_rotation`
- high RSI / low RSI / SMA の signal source を全部 `XLK` にした版。
- 実験色が強い。

### `uvix_engine_variants`
- これは戦略というより volatility leg の backtest engine 差分。
- `strict_uvix`
- `synthetic_uvix_longvol_2x`
- `stitched_uvix_longvol_2x`
- `proxy_uvxy`

## 2. Run Variant

### `testfol_original_spy_uvix__literal`
- 元画像の literal 読み。
- high RSI 表記は `69.5`。

### `testfol_original_spy_uvix__effective`
- tolerance を含めた実効読み。
- high RSI は実質 `71.0 / 68.0`。

### `uvix_rotation_canonical__2005__naive`
- 期間: `2005-12-20 .. latest`
- full-sample 最大化。
- 代表値: `entry = 69.4`, `exit = 65.4`

### `uvix_rotation_canonical__2005__robust`
- `2005` 起点の robust 選抜。
- 代表値: `entry = 67.9`, `exit = 65.5`

### `uvix_rotation_canonical__2011__naive`
- 期間: `2011-01-03 .. latest`
- full-sample 最大化。
- 代表値: `entry = 69.4`, `exit = 66.5`

### `uvix_rotation_canonical__2011__robust`
- `2011` 起点の robust 選抜。
- 代表値: `entry = 68.0`, `exit = 65.5`

### `legacy_spy_signal_uvix_rotation__2011__naive`
- `SPY` signal の旧版。
- 代表値: `entry = 70.1`, `exit = 68.9`

### `cashx_highrsi_rotation__2005__naive`
- `CASHX` 版の full-sample 最大。
- 代表値: `entry = 66.1`, `exit = 61.0`

### `cashx_highrsi_rotation__2011__naive`
- `CASHX` 版の full-sample 最大。
- 代表値: `entry = 66.1`, `exit = 61.4`

### `cashx_highrsi_rotation__entry71_fixed__2005__naive`
- entry を `71` 固定。
- 最適 exit は `69.9`。

### `cashx_highrsi_rotation__entry71_fixed__2005__robust`
- entry を `71` 固定した robust。
- 最適 exit は `54.0`。

### `cashx_highrsi_rotation__entry71_fixed__2011__naive`
- entry を `71` 固定。
- 最適 exit は `68.4`。

### `cashx_highrsi_rotation__entry71_fixed__2011__robust`
- entry を `71` 固定した robust。
- 最適 exit は `65.5`。

### `xlk_highrsi_source_rotation__2005__naive`
- high RSI source だけ `XLK`。
- 代表値: `entry = 73.3`, `exit = 71.9`

### `xlk_highrsi_source_rotation__2005__robust`
- high RSI source だけ `XLK` の robust。
- 代表値: `entry = 75.0`, `exit = 75.0`

### `xlk_highrsi_source_rotation__2011__naive`
- high RSI source だけ `XLK`。
- 代表値: `entry = 73.5`, `exit = 71.9`

### `xlk_highrsi_source_rotation__2011__robust`
- high RSI source だけ `XLK` の robust。
- 代表値: `entry = 73.2`, `exit = 73.2`

### `xlk_all_signal_rotation__2011__naive`
- signal source 全部 `XLK`。
- 代表値: `entry = 73.5`, `exit = 71.9`

### `xlk_all_signal_rotation__2011__robust`
- signal source 全部 `XLK` の robust。
- 代表値: `entry = 74.2`, `exit = 59.1`

## 3. Analysis Only

### `episode_leave_one_out`
- high RSI episode を 1 本ずつ抜く頑健性分析。
- 戦略そのものではなく sensitivity analysis。

### `spy_vs_gspc_decomposition`
- `SPY` と `^GSPC` の差分要因分析。

### `spy_vs_xlk_comparison`
- `SPY RSI` と `XLK RSI` の比較分析。

### `tqqq_backtest`
- `TQQQ` の canonical history extension workspace。
- 戦略そのものではなく leg engine。

### `soxl_backtest`
- `SOXL` の canonical history extension workspace。
- 戦略そのものではなく leg engine。

### `tmf_backtest`
- `TMF` の canonical history extension workspace。
- 戦略そのものではなく leg engine。

### `ugl_backtest`
- `UGL` の canonical history extension workspace。
- 戦略そのものではなく leg engine。

## 4. Not Yet Run

### `gold_highrsi_rotation`
- 一度候補に出たが、実際には `CASHX` に切り替えたため未計算。

## 5. Notes

- この一覧は「今まで試したものを保存名付きで並べる」ことを主目的にしている。
- `canonical` と `legacy` は signal source や leg engine が異なるので、同名扱いにしない。
- `naive` は full-sample 最大化、`robust` は annual folds と plateau smoothing を使った選抜を指す。
- 一部の `XLK` 系は ad hoc analysis として計算しており、まだ専用 script / output naming には落としていない。
