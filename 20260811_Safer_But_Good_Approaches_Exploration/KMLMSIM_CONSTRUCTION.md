# KMLMSIM日次系列の構築

## 採用した定義

Testfolioの公式ヘルプが示すKMLMSIM/KMLMXの定義をそのまま採用する。

- 1988〜2020年: KFA MLM Indexから年率0.9%を控除したシミュレーション
- 2020年以降: 実ETFのKMLM
- 収益系列: 配当・分配を再投資したトータルリターン

独自のマネージド・フューチャーズ代理系列やT-Billでは置き換えない。

公式定義: <https://testfol.io/help>

## 取得方法

`download_testfolio_kmlmsim.py`がTestfolioのバックテストAPIへ100% KMLMSIMの最小ポートフォリオをPOSTし、レスポンスの`daily_returns`を保存する。

```bash
python download_testfolio_kmlmsim.py
```

出力:

- `output/data/testfolio_kmlmsim_daily.csv`
- `output/data/testfolio_kmlmsim_metadata.json`

CSVには`Date`、小数表記の`KMLMSIM_Return`、APIが返す`NAV_10000`を保存する。取得期間は1988-01-04〜2026-08-10、9,723取引日である。

## 一致検査

APIの日次リターンは0.001パーセントポイント単位に丸められる。この丸め済み系列をローカルで再複利し、Testfolioが同じレスポンスで返す精密統計と照合する。

| 指標 | ローカル再構築 | Testfolio精密統計 | 差 |
|---|---:|---:|---:|
| CAGR | 7.5140% | 7.5126% | +0.0014pp |
| 最大ドローダウン | -32.0063% | -31.9963% | -0.0100pp |
| 年率ボラティリティ | 14.0643% | 14.0636% | +0.0007pp |
| $10,000最終額 | $163,877.74 | $163,915.71 | -$37.97 |

取得スクリプトは上記の差を毎回自動検査する。CAGR・ボラの差が0.01pp、最大DDの差が0.05pp、最終額の差が$100を超えた場合は、API仕様または系列の変化とみなして停止する。

## 戦略への統合

`validate_parameters.py`は保存済み日次系列を分析日へ日付結合し、リスクオフ時の3資産を以下の比率で日次均等リバランスする。

- KMLMSIM: 1/3
- 金: 1/3
- VFITX: 1/3

したがって、現在の検証でT-BillはKMLMSIMの代替ではない。なお、金と債券はまだTestfolioのGLDSIM・IEISIMそのものではなく、それぞれローカル代理系列である。
