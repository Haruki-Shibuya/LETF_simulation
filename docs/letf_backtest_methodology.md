# LETF Backtest Methodology Notes

このノートは、今回の `UVIX` / `TQQQ` 検証で使った方法論、`testfol.io` から得た示唆、GitHub 調査で見た実装、そして現時点での「一番筋が良い」と判断している進め方をまとめたものです。

## Executive Summary

結論だけ先に書くと、`LETF` の長期バックテストで一番大事なのは「実 ETF を無理やりそのまま過去に延長しない」ことです。

- equity LETF (`TQQQ`, `UPRO`, `SOXL` など):
  - 基本は **benchmark-faithful synthetic series**
  - つまり、公式 benchmark の **daily return** に daily leverage、fee、financing drag を入れて、日次で複利計算する
  - 実 ETF が存在する期間は **live overlap** で calibration / validation する
- volatility ETP / LETF (`UVIX`, `UVXY`, `VXX` 系):
  - 基本は **VIX spot ではなく、VIX futures index-faithful model**
  - つまり、front two months の VIX futures を daily roll する benchmark をまず正しく押さえる
  - 実 ETP はその上に leverage / fee / product-level tracking を重ねて扱う

repo 実装もこの方針に寄せています。

## What We Learned From testfol

`testfol.io` は portfolio backtester として非常に便利ですが、canonical source of truth としてそのまま採用するより、**良い UI を持つ synthetic modeling tool** として使うのが妥当だと判断しています。

### 公開サイトから読み取れること

- `testfolio` は portfolio backtester / asset allocation backtester として公開されている
- tactical / portfolio / calculator など、strategy design と historical simulation をブラウザ上で素早く回せる

### 実際に今回見えていた構文

今回の tactical screenshot では、以下のような ticker syntax が使われていました。

- `QQQSIM?L=3&E=0.82`
- `GLDSIM?L=2&E=0.95`
- `TLTSIM?L=3&E=0.91`
- `UVIXSIM?L=1&E=1.65`

ここから読み取れるのは、testfol 側が

1. extended-history 用の base ticker (`QQQSIM`, `GLDSIM`, `TLTSIM`, `UVIXSIM` など)
2. leverage parameter (`L`)
3. expense ratio (`E`)

のような synthetic ticker overlay を使っている、という点です。

### testfol をどう位置づけるべきか

testfol の長所:

- idea generation が速い
- if/else tactical logic を UI で素早く組める
- synthetic LETF を雑に作るにはかなり便利

testfol の弱点:

- product family ごとの内部モデルがブラックボックス寄り
- equity LETF と vol ETP をどの程度同じ abstraction で扱っているかが見えにくい
- financing / borrow / futures roll の扱いを research artifact として厳密管理しにくい

そのため、**testfol は戦略の発想源 / UI プロトタイプとしては優秀だが、repo 内で残す canonical dataset は自前の explicit model で作る**、という整理にしています。

## Main Questions / Evaluation Criteria

LETF backtest を評価するとき、今回の論点は主に以下でした。

### 1. benchmark-faithful か fund-faithful か

- benchmark-faithful:
  - 公式 benchmark の return を忠実に再現する
  - その上に leverage / fee / financing を乗せる
- fund-faithful:
  - 実 fund の swap, futures, cash, rebalance friction まで寄せる

実務では、まず **benchmark-faithful** を作るのが正しいです。
fund-faithful は次の段階で、しかも product ごとに難しさが大きく違います。

### 2. return space で作るか level space で作るか

これは `UVIX` で強く効いた論点でした。

- level space で無理に過去価格を合わせると、古い水準が極端に大きくなることがある
- 特に decay の大きい products では、reverse split 調整済み価格をそのまま昔に延長すると、見た目も数値レンジも歪みやすい

そのため、**canonical series は return space で作って、必要なら最後に level を再構築する**方が安全です。

### 3. spot を使うか futures/index methodology を使うか

これは `UVIX` 側の最大論点でした。

- `TQQQ` なら `NDX` daily return が主 benchmark
- `UVIX` なら `VIX spot` ではなく、short-term VIX futures index が主 benchmark

spot と futures index を混同すると、backtest の意味が変わります。

### 4. live overlap で calibration しているか

pre-inception extension をやるなら、実 ETF が存在する期間を使って

- daily return correlation
- mean absolute error
- cumulative growth gap
- drawdown shape

を点検するべきです。

今回の `TQQQ` extension でも、ここを入れて canonical model を決めています。

### 5. 時変コストを固定 cost に丸めていないか

実 LETF には

- fee
- financing cost
- swap/futures implementation cost
- roll cost

があり、しかも多くは時変です。

ただし、全部を毎日 exact に入れるのは難しいので、実務上は

- まず固定 cost proxy で benchmark-faithful model を作る
- その後 live overlap の residual で calibration する

の順番が自然です。

## GitHub Research

GitHub 上で「そのまま正解」と言える repo は見つかりませんでした。
ただし、役割ごとに参考になるものはありました。

### 1. `dougransom/vix_utils`

repo:

- <https://github.com/dougransom/vix_utils>

良い点:

- VIX cash / futures term structure を扱っている
- front two months と 30-day continuous maturity weighting を明示している
- `UVIX`, `UVXY`, `VXX` 系の underlier を考える上で一番本質に近い

限界:

- ETP backtester 完成品ではない
- leverage / fee / stitch / tactical layer は自分で上に載せる必要がある

評価:

- **volatility product の benchmark engine を作る際の最有力参考 repo**

### 2. `pchuck/etf-leverage-comparator`

repo:

- <https://github.com/pchuck/etf-leverage-comparator>

良い点:

- theoretical simulated vs actual leveraged ETF という整理が良い
- daily leverage compounding と actual ETF の差を分けて考えている
- equity LETF を benchmark-faithful synthetic として扱う発想が明快

限界:

- reusable engine というより analysis notebook / write-up 寄り
- financing / borrow / implementation cost の explicit model は薄い

評価:

- **equity LETF の考え方を整理するのに一番参考になる repo**

### 3. `nateGeorge/simulate_leveraged_ETFs`

repo:

- <https://github.com/nateGeorge/simulate_leveraged_ETFs>

良い点:

- 「ETF inception より前の history を作りたい」という問題意識は同じ
- 実データを見ながら経験的に延長しようとしている

弱い点:

- latest ETF price から過去を back-calculate する色が強い
- correlation fit / empirical fit に寄りすぎている
- benchmark methodology よりも observational fit に依存している

評価:

- **面白いが canonical method にはしない**

### 4. `BadWolf1023/leveraged-etf-simulation`

repo:

- <https://github.com/BadWolf1023/leveraged-etf-simulation>

良い点:

- leverage と decay の関係を直感的に見るには悪くない

弱い点:

- ETF replication engine より leverage thought experiment に近い
- actual product validation の枠組みとしては弱い
- README から見ても reusable canonical implementation には向かない

評価:

- **長期 canonical backtest engine の参考にはしない**

## Current Best Method By Product Family

### A. Equity LETF (`TQQQ`, `SOXL`, `UPRO` など)

現時点のベストプラクティスはこれです。

1. **公式 benchmark** を決める
   - `TQQQ` なら `Nasdaq-100`
2. benchmark の **daily return** を使う
3. **daily leverage** を掛ける
4. fee と financing drag を入れる
5. 実 ETF の live overlap で calibration / validation
6. pre-inception は synthetic, inception 後は actual return で stitched

この方式の良い点:

- LETF の daily reset という本質と整合的
- pre-inception extension が素直
- overlap で誤差確認できる

この方式の限界:

- fee history を fixed proxy に丸めることが多い
- 実際の swap book / collateral / tax / intraday friction までは入っていない

### B. Volatility ETP / LETF (`UVIX`, `UVXY`, `VXX` など)

現時点のベストプラクティスはこれです。

1. **VIX spot ではなく short-term VIX futures index** を benchmark にする
2. front two months の futures roll methodology を押さえる
3. leverage / fee をその上に乗せる
4. 実 ETP と overlap validation をする
5. canonical series はできるだけ return-space stitched にする

この方式の良い点:

- product の underlier と整合する
- spot VIX proxy より意味がある

この方式の限界:

- pre-futures era の exact reconstruction は不可能
- 2004/2005 より前は proxy 依存が強くなる

## Why We Implemented TQQQ The Way We Did

今回の repo 実装では、`TQQQ` を以下の形で延長しました。

- benchmark: `^NDX`
- financing proxy: `DGS3MO`
- base model:
  - `daily return = 3.0 * NDX daily return - fee / 252 - k * DGS3MO / 252`
- `k` は live `TQQQ` overlap で cumulative log return が一致するように校正
- canonical export は:
  - pre-inception: calibrated synthetic return
  - inception 後: actual `TQQQ` adjusted-close return

これを採った理由:

- `TQQQ` は daily 3x product なので、price-level backfill より daily-return model が自然
- financing を完全に無視すると actual を上に外しやすい
- `2x cash financing` をそのまま入れると逆に下に外しやすい
- そのため、**fixed fee + calibrated financing multiplier** が現時点では一番実務的

## Why We Did Not Adopt Some Other Approaches

### 1. 実 ETF の価格をそのまま比例スケールして過去に延長

不採用理由:

- mechanics が説明しづらい
- decay product では水準が極端になりやすい
- return の構造ではなく level の見た目に引っ張られる

### 2. `spot VIX * leverage` で `UVIX` を作る

不採用理由:

- underlier が違う
- `UVIX` は VIX futures basket 系であって VIX spot そのものではない

### 3. empirical fit を最優先して benchmark を後回しにする

不採用理由:

- regime が変わると外れやすい
- out-of-sample の説明力が弱い
- 「なぜその series なのか」が残りにくい

## What We Consider Canonical Right Now

現時点で canonical と考えているのは次です。

- `TQQQ` 系:
  - **benchmark-faithful daily-reset synthetic + live overlap calibration + return-space stitching**
- `UVIX` 系:
  - **VIX futures index-faithful synthetic + actual overlap validation + return-space stitching**

つまり、

- equity LETF は **index daily return を主語にする**
- vol LETF は **futures-index methodology を主語にする**

が、今の最良方針です。

## Files In This Repo

このノートに関連する実装・出力:

- [`tqqq_backtest/README.md`](../tqqq_backtest/README.md)
- [`tqqq_backtest/extend_tqqq_history.py`](../tqqq_backtest/extend_tqqq_history.py)
- [`uvix_backtest/README.md`](../uvix_backtest/README.md)
- [`uvix_backtest/rsi_entry_exit_optimize.py`](../uvix_backtest/rsi_entry_exit_optimize.py)

## External References

Official / product / methodology sources:

- [testfol.io](https://testfol.io/)
- [ProShares UltraPro QQQ summary prospectus](https://prod.proshares.com/globalassets/proshares/prospectuses/tqqq_summary_prospectus.pdf)
- [ProShares TQQQ fund page](https://www.proshares.com/our-etfs/leveraged-and-inverse/tqqq)
- [Nasdaq-100 history note](https://www.nasdaq.com/newsroom/celebrating-40-year-rise-nasdaq-100-index)
- [S&P 500 VIX Short-Term Futures Index](https://www.spglobal.com/spdji/en/indices/indicators/sp-500-vix-short-term-index-mcap)
- [S&P VIX short-term family overview](https://www.spglobal.com/spdji/en/index-family/indicators/vix/short-term/)
- [Cboe VIX historical data](https://www.cboe.com/en/tradable-products/vix/vix-historical-data/)
- [Cboe VIX futures overview](https://www.cboe.com/en/tradable-products/vix/vix-futures//)

GitHub research targets:

- [dougransom/vix_utils](https://github.com/dougransom/vix_utils)
- [pchuck/etf-leverage-comparator](https://github.com/pchuck/etf-leverage-comparator)
- [nateGeorge/simulate_leveraged_ETFs](https://github.com/nateGeorge/simulate_leveraged_ETFs)
- [BadWolf1023/leveraged-etf-simulation](https://github.com/BadWolf1023/leveraged-etf-simulation)
