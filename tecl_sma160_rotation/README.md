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
