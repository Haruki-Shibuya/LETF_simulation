# TECL SMA160 Rotation

この workspace は、次の戦略を検証するためのものです。

1. 通常時は `TECL` を保有
2. signal が `SMA160` を下回ったら `TECL` を売却
3. 一定条件まで待ってから、下側レジームでは `SOXL / TECL / TQQQ` の mix を保有
4. `SMA160` 復帰後は `TECL / TQQQ` の mix に戻る

今回の比較では、以下の signal 設定を扱えるようにしています。

- `underlier`
  - tech underlier proxy
- `tecl`
  - `TECL` 自身
- `gspc`
  - `^GSPC`

below-SMA entry mode は 2 種類です。

- `sma_drawdown`
  - `signal price <= SMA160 * (1 - n%)`
- `crossunder_price_drawdown`
  - `SMA160` を最初に下回った日の signal price を基準にして、その価格から `n%` 下落したら参入

今回の最新 run では、ユーザー指定に合わせて以下を使います。

- below-SMA mix (`SOXL:TECL:TQQQ`): `0:0:100` など任意
- above-SMA mix (`TECL:TQQQ`): `100:0`
- signal source: `gspc`
- below-SMA entry mode: `crossunder_price_drawdown`

`signal source = underlier` は、`TECL` 自体ではなく tech underlier proxy の価格と `SMA160` を使う設定です。
これは leveraged ETF 自身の price/SMA を signal に使うより、drag と volatility の影響を signal layer に入れにくいため、今回の default としています。

`n > 0` のときは、`SMA160` 割れ直後は cash wait とし、指定ルールで十分に下に来た時点で below-SMA bucket を買います。

## Provisional Canonical Strategy

現時点の暫定 canonical 候補は `prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit` とする。

これは単純な最大CAGRの組み合わせではなく、実運用で毎朝同じ手順を踏めるようにした暫定ルールである。

### Daily Operation Manual

毎営業日のOpen近辺で、以下を上から順に確認してポジションを決める。

Inputs:

- `GSPC Open`
- 前営業日までの `GSPC Close SMA160`
- `GSPC open-implied RSI14`
- `TQQQ Open`
- `TQQQ Open` のrunning peak
- UVIX保有中の場合は、UVIX entry日の `TQQQ Open`

`open-implied RSI14` は、当日 `GSPC Open` を「今日の仮Close」としてWilder RSI14を更新した値である。

Step 1: UVIX position management

- すでに `UVIX` を持っている場合、次のどちらかを満たしたら `UVIX` を売却する。
- `GSPC open-implied RSI14 <= 68.5`
- `TQQQ Open <= UVIX entry日のTQQQ Open`
- 上記exitに該当しない場合は、そのまま `UVIX` を持つ。

Step 2: UVIX entry

- `UVIX` を持っていない状態で `GSPC open-implied RSI14 >= 69.5` なら、Open近辺で `UVIX` を買う。
- このとき、後日のexit判定用に、その日の `TQQQ Open` を `UVIX entry TQQQ Open` として記録する。

Step 3: Low-RSI TQQQ override

- `UVIX` を持っておらず、base判定上のポジションが `TMF/GLD` 待機で、かつ `GSPC open-implied RSI14 < 30` なら、Open近辺で一時的に `TQQQ` を買う。
- low-RSI override中に `GSPC open-implied RSI14 >= 32.5` になったら、Open近辺で `TQQQ` を売り、base判定上の `TMF/GLD` 待機へ戻る。

Step 4: Base position

- 上記のUVIX/low-RSI overrideが発動していない日は、base判定に従う。
- baseのSMAは、前営業日までの `GSPC Close SMA160` を使う。
- 当日 `GSPC Open` がそのSMA以上なら `TQQQ` を持つ。
- 当日 `GSPC Open` がそのSMA未満なら、原則 `TMF 50% / GLD 50%` で待機する。
- ただし、`TQQQ Open` がrunning peakから `alpha=54.5%` 以上下落している場合は、底拾いルールとして `TQQQ` を持つ。
- この底拾いは、SMA cross-under価格からの下落率ではなく、`TQQQ Open` のrunning peakからの `alpha%` drawdownで判定する。

Return attribution:

- close-to-open return は前日から持っていた旧ポジションに帰属する。
- open-to-close return は当日Openで決めた新ポジションに帰属する。
- 終値確定後のsignalを同日close-to-close returnへ適用する `same_close` 型の処理は使わない。

2010年以降の結果:

| Strategy | CAGR | Vol | Max DD | Final multiple | Events | Overlay days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base only, running DD `alpha=54.5` | `53.54%` | `57.95%` | `-66.96%` | `1016.20x` | - | - |
| previous UVIX RSI-only exit | `99.42%` | `63.77%` | `-68.16%` | `69241.85x` | UVIX `91/90` | UVIX `9.24%` |
| current provisional canonical | `106.46%` | `64.03%` | `-65.68%` | `121187.47x` | UVIX `127/126`, low-RSI `11/11` | UVIX `8.87%`, low-RSI `0.59%` |

主な出力:

- `output/prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_summary.csv`
- `output/prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_top20.csv`
- `output/prev_close_sma_same_open_running_dd_alpha54p5_uvix_ohlc_open_implied_rsi14_fixed_entry69p5_exit_opt_from_20100212_exit45to68p5step0p1_daily_path.csv`
- `output/prev_close_sma_same_open_running_dd_alpha54p5_uvix_open_implied_rsi69p5_tqqq_drop_or_rsi68p5_exit_opt_from_20100212_drop0to80step0p5_summary.csv`
- `output/provisional_canonical_low_rsi_tqqq_override_rsi30_rsi_exit_opt_from_20100212_exit30to80step0p5_summary.csv`
- `output/canonical_prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212_summary.csv`
- `output/canonical_prev_close_sma_same_open_running_dd_uvix_or_tqqq_drop_low_rsi_tqqq_rsi_exit_from_20100212_daily_path.csv`

## Local Decision Dashboard

Open前後の実運用チェック用に、ローカルWebダッシュボードを用意している。

起動:

```bash
python3 tecl_sma160_rotation/dashboard_server.py
```

ブラウザ:

```text
http://127.0.0.1:8765
```

ボタンを押すと、`yfinance` から最新データを取得し、以下のシナリオで現在取るべきポジションを表示する。

- 前日Close据え置き: `GSPC` / `TQQQ` の前日Closeを仮Openとして使う
- SPY premarket/last示唆: `SPY` の最新値から `GSPC Open` を近似し、`TQQQ` は最新値を使う
- S&P futures示唆: `ES=F` から `GSPC Open` を近似する
- 市場Open後の実Open: 米国市場Open後に当日Openが取得できる場合だけ表示する

表示される判断は、このrepositoryの暫定canonical strategy出力であり、投資助言ではない。

## UVIX Episode Diagnostics

暫定canonicalの `UVIX` 保有区間を連続episodeに分解し、episodeごとの損益分布と、前回UVIX episode終了からの経過日数との関係を確認した。

主な出力:

- `output/uvix_episode_spacing_analysis.csv`
- `output/uvix_episode_spacing_summary.csv`
- `output/uvix_episode_return_quantiles.csv`
- `output/uvix_episode_spacing_vs_return.png`
- `output/uvix_episode_return_distribution.png`

集計:

| Metric | Value |
| --- | ---: |
| UVIX episodes | `97` |
| Win rate | `67.01%` |
| Average episode return | `+3.64%` |
| Median episode return | `+3.09%` |
| Average holding days | `3.72` |
| Median holding days | `2` |
| Correlation: days since previous UVIX exit vs return | `-0.066` |

Episode return quantiles:

| Quantile | Return |
| ---: | ---: |
| `1%` | `-19.65%` |
| `5%` | `-12.76%` |
| `10%` | `-9.18%` |
| `25%` | `-0.92%` |
| `50%` | `+3.09%` |
| `75%` | `+7.39%` |
| `90%` | `+11.66%` |
| `95%` | `+14.68%` |
| `99%` | `+34.77%` |

最大の `+82.63%` episode (`2020-08-24 .. 2020-09-03`) を除外すると、平均episode returnは `+3.64%` から `+2.81%` に下がる。一方で中央値は `+3.09%` から `+3.04%`、勝率は `67.01%` から `66.67%` で、大きくは変わらない。

解釈:

- 前回UVIX episode終了からの経過営業日数は、次のUVIX episode returnをほとんど説明していない。
- 平均は右尾の大勝ちepisodeにある程度引っ張られるが、中央値と勝率は比較的安定している。
- 分布は「小負けから一桁%勝ち」が中心だが、左尾では二桁%負けもある。

採用経緯:

1. `same_close` は終値確定後のsignalを同日close-to-close returnへ適用するため削除した。
2. Openで売買する方式では、SMAの価格基準・判定価格・約定価格を分ける必要があると分かった。
3. `prev_close_sma_same_open` を定義し、前日Close SMA160を当日Openで判定する方式にした。
4. TQQQ買い戻しは、cross-under価格基準 `N=13%` と running drawdown 基準を比較した。
5. running drawdown 基準はCAGR単体では少し劣るが、MDDが抑えられるため暫定canonical候補のbaseにした。
6. UVIX overlay では、`prev_close_rsi` ではなく、Open売買と時系列が合う `open-implied RSI` を使う候補を検証した。
7. `entry=exit` の unconstrained optimum は売買回数が多く過適合リスクが高いため、entry `69.5` 固定、exit最適化、toleranceありにした。
8. UVIX exit は `RSI <= 68.5` に加えて `TQQQ Open <= entry時TQQQ Open` を追加した。TQQQ下落率だけのexitはUVIXを持ちすぎて破綻したため不採用。
9. 低RSI局面では、`RSI < 30` で `TQQQ` に戻り、`RSI >= 32.5` で待機mixへ戻る補助overlayを追加した。価格反発exitよりCAGRは少し低いが、RSIでentry/exitが揃うため暫定canonicalにした。

未解決・注意点:

- 2010年以降の full-sample optimization であり、OOS / walk-forward は未実施。
- `alpha=54.5`, UVIX `exit=68.5`, low-RSI `exit=32.5` は同じ期間で最適化された値である。
- UVIX OHLC の `2005-12-20 .. 2011-10-03` は `^VIX` proxy、`2011-10-04 .. UVIX実在前` は `UVXY` proxy を使う。
- slippage / spread / market impact / tax は未反映。
- Open近辺での実約定は、理論上のOpen価格と完全一致しない。

## Proxies

- `TECL`
  - pre-`XLK`: `FSPTX` calibrated legacy tech proxy
  - `XLK` start 以降: `XLK`
  - actual overlap: `TECL`
- `SOXL`
  - pre-`^SOX`: `FSELX` calibrated legacy semiconductor proxy
  - `^SOX` history 以降: `^SOX`
  - `2021-08-25` 以降: `SOXX`
  - actual overlap: `SOXL`
- `TQQQ`
  - existing canonical output from `tqqq_backtest/output/tqqq_extension_1991.csv`

## Main Script

- `simulate_tecl_sma160_rotation.py`

## Outputs

- summary CSV
- daily equity / allocation path CSV
- log-scale equity PNG
- drawdown-threshold optimization CSV / PNG
- proxy diagnostics CSV
