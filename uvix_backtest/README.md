# UVIX Backtest Workspace

このフォルダは、`UVIX` を使う高RSIレジーム戦略の検証をまとめた canonical workspace です。
今後このテーマを触るときは、基本的にこのフォルダ配下を使う前提です。

既存の `/Users/harukishibuya/Documents` 直下や `/Users/harukishibuya/Documents/output` にも元ファイルは残していますが、そちらは後方互換用の作業痕跡です。

## Current Canonical Setup

- 戦略の元ネタは testfol.io の screenshot から読み取った条件分岐です。
- 高RSI側だけを最適化対象にし、低RSIとSMA系は固定です。
- 固定シグナル:
  - `^GSPC Low RSI`: 14-day RSI の hysteresis が `30.5 / 33.5`
  - `^GSPC OVER SMA`: `Price > 160d SMA * 1.04` で entry、`Price < 160d SMA * 0.96` で exit
- 配分の骨格:
  - 高RSI時: `UVIX`
  - 低RSI時: `SOXL`
  - 上昇トレンド時: `TQQQ`
  - それ以外: `UGL 50% / TMF 50%`

## UVIX Modeling History

この検証では、長期 `UVIX` 履歴が存在しないのが最大の論点でした。

1. 最初は `strict_uvix` として、実 `UVIX` だけをそのまま使いました。
   - 有効期間は `2022-03-30` 以降だけです。

2. 次に、長期検証のために `UVXY` proxy を使いました。
   - ただし `UVXY` は `UVIX` と別商品で、現在のレバレッジ仕様も違うため、最終形としては不採用です。

3. その後、`LONGVOL` から `2x` の `UVIX` 合成系列を作る形に切り替えました。
   - `synthetic_uvix_longvol_2x`
   - 日次リターンは `2.0 * LONGVOL daily return - 1.65%/252`

4. さらに、`LONGVOL` 系列と実 `UVIX` をつないだ `stitched_uvix_longvol_2x` を作りました。
   - ここが長期最適化の canonical dataset です。

## Why We Switched To Return-Space Stitching

途中までは、`LONGVOL` ベースの `UVIX` 合成を価格レベルでスケーリングしていました。
しかし `LONGVOL` は歴史的に指数レベルが非常に高く、2022年の `UVIX` レベルに合わせて比例スケールすると、過去の `UVIX` 仮想価格が極端に大きくなります。

例えば、旧レベル空間の scaled series では:

- `2011-01-03`: 約 `3.77e12`
- `2005-12-20`: 約 `9.92e14`
- 最大値: 約 `1.68e15`

これは見た目にも不自然で、精度面の懸念も生みます。

そこで現在は、**価格レベルはつながず、return 空間で直接 stitched** しています。

- `pre-2022`: `2x LONGVOL return - fee`
- `2022-03-31` 以降: actual `UVIX` return

この方式なら天文学的な price level を持ちません。
しかも、今回の最適化結果は旧方式とほぼ一致しており、最終的にこちらを canonical 実装としました。

## Latest Canonical Results

前提:

- dataset: `stitched_uvix_longvol_2x`
- backtest window: `2011-01-03 .. 2026-04-17`
- grid: `entry/exit = 0.1` 刻み

最適値:

- `entry = 69.4`
- `exit = 66.5`
- `CAGR = 110.6588%`
- `MDD = -72.9995%`
- `trade_count = 232`
- `vol_days = 411`

補足:

- `entry = 71.0 / exit = 68.0` の baseline は、`stitched_uvix_longvol_2x` で `CAGR = 94.4853%` です。

## Robustness Result

高RSIエピソードを full-sample optimum `70.1 / 68.9` で定義し、`leave-one-episode-out` を回しました。

- エピソード総数: `79`
- `62 / 79` で最適解はそのまま `69.4 / 66.5`
- leave-one-out optimum は合計 `5` パターン

最頻値は `69.4 / 66.5` ですが、`SPY` 版よりはやや分散しており、`^GSPC` 版では最適解の頑健性は少し弱まっています。

## File Map

Scripts:

- [rsi_entry_exit_optimize.py](./rsi_entry_exit_optimize.py)
  - メイン最適化
- [plot_rsi_entry_exit_surface.py](./plot_rsi_entry_exit_surface.py)
  - 3D surface / interactive HTML / 2D heatmap 生成
- [analyze_rsi_episode_robustness.py](./analyze_rsi_episode_robustness.py)
  - leave-one-episode-out の頑健性分析

Key outputs:

- [overview](./output/rsi_entry_exit_optimization_overview_from_20110101_entrystep_0p1_exitstep_0p1.csv)
- [baseline compare](./output/rsi_entry_exit_baseline_compare_from_20110101_entrystep_0p1_exitstep_0p1.csv)
- [UVIX proxy alignment](./output/uvix_proxy_alignment.csv)
- [stitched full grid](./output/stitched_uvix_longvol_2x_full_grid_from_20110101_entrystep_0p1_exitstep_0p1.csv)
- [stitched top10](./output/stitched_uvix_longvol_2x_top10_from_20110101_entrystep_0p1_exitstep_0p1.csv)
- [interactive 3D surface](./output/stitched_uvix_longvol_2x_full_grid_from_20110101_entrystep_0p1_exitstep_0p1_3d_surface_interactive.html)
- [2D heatmap](./output/stitched_uvix_longvol_2x_full_grid_from_20110101_entrystep_0p1_exitstep_0p1_2d_heatmap.png)
- [episode leave-one-out rows](./output/stitched_uvix_longvol_2x_episode_leave_one_out_from_20110101_entrystep_0p1_exitstep_0p1.csv)
- [episode xmarks plot](./output/stitched_uvix_longvol_2x_episode_leave_one_out_from_20110101_entrystep_0p1_exitstep_0p1_xmarks.png)

## Environment

- 依存パッケージは [requirements.txt](./requirements.txt) にまとめています。
- このフォルダでは macOS の `/usr/bin/python3` で動作確認しています。
- 自分の `python3` が別環境を向いていて `numpy` などが見つからない場合は、先に `python3 -m pip install -r requirements.txt` を実行してください。

## Commands

最適化を再実行:

```bash
/usr/bin/python3 rsi_entry_exit_optimize.py --backtest-start 2011-01-01 --entry-step 0.1 --exit-step 0.1
```

Surface / heatmap を再生成:

```bash
/usr/bin/python3 plot_rsi_entry_exit_surface.py
```

leave-one-episode-out を再実行:

```bash
/usr/bin/python3 analyze_rsi_episode_robustness.py
```

## Notes

- `interactive 3D surface` は Plotly CDN を読むので、表示時にネット接続が必要です。
- データ取得元は主に `yfinance` と Cboe の `LONGVOL` historical API です。
- `strict_uvix` はあくまで実 `UVIX` だけの短期チェック用です。長期の canonical 議論は `stitched_uvix_longvol_2x` を使ってください。
