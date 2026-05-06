# Canonical UVIX Strategy Notes

Last updated: 2026-05-05

This document records the working definition, calculation history, and current canonical candidate for the high-RSI UVIX episode strategy. The purpose is to avoid losing track of which rule set produced which CAGR.

## Do Not Mix These Results

The file below is an old mixed base-strategy result and must not be treated as the current TQQQ re-entry rule:

```text
tecl_sma160_gspc_above_tecl100_tqqq0_wait_tmf50_gld50_below_soxl0_tecl0_tqqq100_crossunder_price_drawdown_ref_tecl_enterdown_41p5_from_20020101_daily_path.csv
```

It uses a TECL price recorded around the GSPC SMA160 crossunder as the drawdown reference, then uses that base path inside the high-RSI UVIX priority rule. This is not the same as:

- `α`: TQQQ drawdown from the immediate prior peak
- `n`: TQQQ drawdown from the TQQQ open recorded when GSPC fell below SMA160

Therefore the 2005-start CAGR `177.54%` produced by this old TECL-reference path should be treated as a separate historical experiment, not as the answer to the current TQQQ `n%` question.

## Current Recommendation

Use the following as the current canonical candidate:

- Signal reference and execution timing:
  - use the current trading day's open as the signal input
  - execute the transition at that same open
  - the position held from the previous day receives the previous close to current open return
  - the post-transition position receives the current open to current close return
- Base portfolio rule: keep the existing SMA160 / drawdown rotation logic for the non-UVIX state.
- High-RSI UVIX priority rule:
  - enter UVIX at the open when `GSPC open-implied RSI14 >= 67.5`
  - require `GSPC BB20 Z >= 1.6`
- High-RSI UVIX exit:
  - exit when `GSPC open-implied RSI14 <= 66.0`
  - also exit when `GSPC open / GSPC entry open - 1 <= +0.1%`
- Transition policy:
  - exactly one open transition per trading day
  - if already in UVIX, exit checks have priority over new UVIX entry checks
  - no same-open exit and re-entry loop
- Low-RSI TQQQ priority rule:
  - keep the existing low-RSI priority rule as previously used
  - enter TQQQ priority position around `RSI < 30.0`
  - exit around `RSI >= 32.5`

The `+0.1%` GSPC exit should be read as a near-flat / failed-continuation exit, not as a deep drop trigger. It says: if GSPC has not continued upward from the UVIX entry open, stop waiting for the RSI-only exit and close UVIX early.

## Signal Reference and Execution Timing

The current canonical is an **open-referenced / open-executed** simulation.

This means the strategy uses the current day's open as the decision input and also assumes the portfolio can transition at that same open. This is a stronger assumption than deciding from the previous close and trading at the next open, so the distinction must be recorded whenever CAGR is compared.

For the 2010-start canonical parameters:

- `α = 40.5%`
- `entry RSI = 67.5`
- `exit RSI = 66.0`
- `BB20 Z >= 1.6`
- `GSPC gamma = +0.1%`
- low-RSI TQQQ priority retained

the aligned comparison through `2026-04-17` is:

| Signal reference | Execution timing | CAGR | Max drawdown | UVIX entries | Low-RSI TQQQ entries | Status |
|---|---|---:|---:|---:|---:|---|
| Current-day open | Same current-day open | 153.453% | -77.76% | 142 | 16 | Current canonical |
| Previous close | Next trading-day open | 108.400% | -77.84% | 155 | 21 | Comparison branch |

Interpretation:

- The current-day-open signal version materially outperformed the previous-close signal version by about `+45.05` CAGR percentage points in this fixed-parameter 2010-start check.
- Max drawdown was almost unchanged, so the difference came mainly from entry/exit timing and episode selection, not from a lower drawdown profile.
- The website should therefore state clearly that current canonical results are based on current-day open signal inputs and same-open transitions.

Recorded comparison files:

```text
output/canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_summary.csv
output/canonical_prev_close_signal_same_open_exec_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_summary.csv
```

## Why TQQQ Drop Exit Is No Longer Canonical

The previous dashboard and simulations used a rule equivalent to:

- while in UVIX, exit if `TQQQ open <= TQQQ entry open`

That produced strong results, but the rule is conceptually weak. The UVIX episode is entered from GSPC RSI / GSPC Bollinger conditions, and the intended explanatory variable is broad market stress / reversal. Using TQQQ as the exit reference is an indirect leveraged proxy and makes the rule harder to defend.

The revised exit source should be GSPC itself:

- while in UVIX, compare current `GSPC_OPEN` against the UVIX episode's entry `GSPC_OPEN`

This keeps entry and exit signals on the same underlying index.

## Key Calculation Results

Important naming note:

- Use `α` only for the strategy that re-enters TQQQ based on the drawdown from the immediate prior peak of TQQQ open.
- Use `n` for the separate strategy that records the TQQQ open when GSPC first falls below SMA160 and re-enters TQQQ after TQQQ has fallen `n%` from that recorded price.
- Do not compare CAGR numbers unless the start date, base re-entry rule, UVIX exit rule, and low-RSI rule are identical.

All figures below use:

- daily open-only transition model
- one transition per open
- `entry RSI = 67.5`
- `exit RSI = 66.0`
- `BB20 Z >= 1.6`
- low-RSI TQQQ priority rule retained
- backtest start selectable on the dashboard:
  - `2005-12-20` — actual canonical (CAGR-maximized α = 94.0%)
  - `2010-02-12` — actual canonical (CAGR-maximized α = 40.5%)
  - `1991-01-02` — stitched canonical (see below for construction notes)

| Start | α | CAGR | Max drawdown | UVIX entries | Low-RSI TQQQ entries | Notes |
|---|---:|---:|---:|---:|---:|---|
| 2005-12-20 | 94.0% | 113.017% | -69.63% | 160 | 32 | Direct prior-peak α version |
| 2010-02-12 | 40.5% | 153.453% | -77.76% | 142 | 16 | Direct prior-peak α version |
| 1991-01-02 | 100.0% (全期間統一) | 68.78% | -81.13% | 160 (post-2005 only) | 32+ | Stitched series, α=100%全期間一貫 |

Current choice: keep `GSPC gamma = +0.1%` without the GSPC stop-loss for canonical simplicity. The dashboard can switch between the 2005-start, 2010-start, and 1991-start versions.

## Overfitting Checks Performed

See also:

```text
CANONICAL_ROBUSTNESS_CHECK_2010.md
```

Latest 2010-start robustness check, using a 216-candidate local canonical-neighborhood grid, found:

- current canonical was the best candidate in the local grid
- anchored walk-forward OOS median yearly CAGR: `138.98%`
- rolling 5-year walk-forward OOS median yearly CAGR: `133.13%`
- CSCV/PBO approximation: `6.65%`
- selected OOS loss probability in CSCV approximation: `0.00%`
- removing top 10 UVIX episodes still left CAGR at `120.44%`
- 100 bps per-transition stress still left CAGR at `109.08%`

Current interpretation: the largest remaining robustness risk is less about local parameter overfitting and more about the same-open signal/execution assumption.

The low-entry RSI region was tested because entry values below the original `69.5` looked surprisingly strong. For the no-drop / BB strategy, the best low-entry candidate was:

- `entry RSI = 66.3`
- `exit RSI = 66.1`
- CAGR `126.353%`
- episodes `130`
- median UVIX episode return `+4.679%`
- mean UVIX episode return `+4.707%`
- episode return standard deviation `12.171%`
- win rate `72.3%`
- best episode `+56.473%`
- worst episode `-23.387%`
- removing top 1 episode: CAGR `120.404%`
- removing top 5 episodes: CAGR `104.865%`

Interpretation:

- The low-entry result was not purely one huge episode.
- It still depends meaningfully on the best handful of episodes.
- Median and win-rate were acceptable, so low entry was not dismissed as obviously fake.
- But because the canonical rule now includes BB20Z and an early GSPC exit, the current candidate is better recorded as a separate rule family rather than a continuation of the old `69.5 / 68.5` RSI-only idea.

For the current BB + GSPC-exit direction, the fixed `67.5 / 66.0 / gamma +0.1%` result had:

- median UVIX episode return `+3.48%`
- win rate `74.5%`
- episode return standard deviation `10.42%`
- UVIX exits: `141`
- exits triggered by pure GSPC profit: `71`
- exits where RSI and GSPC profit were both true: `54`
- exits triggered by RSI only: `16`

This is not just an RSI-exit strategy anymore. The early GSPC exit is the dominant high-RSI UVIX exit mechanism.

## UVIX-Based Profit / Stop Rules

A natural alternative is to exit based on UVIX itself:

- profit-take when `UVIX open / UVIX entry open - 1 >= p%`
- stop-loss when `UVIX open / UVIX entry open - 1 <= -s%`

This is intuitive because it directly controls trade P/L. However, it is also more vulnerable to overfitting because the rule optimizes directly on the asset being traded.

Grid check, using 0.5% increments:

| Rule set | Best threshold | CAGR | Max drawdown | Entries | Median episode return | Win rate |
|---|---:|---:|---:|---:|---:|---:|
| UVIX profit only | `p = 5.5%` | 126.479% | -56.54% | 124 | 6.63% | 80.5% |
| UVIX stop only | `s = 17.5%` | 125.945% | -56.54% | 109 | 5.79% | 77.8% |
| UVIX profit + stop | `p = 5.5%`, `s = 3.5%` | 139.211% | -56.54% | 168 | 5.75% | 65.3% |
| GSPC `gamma +0.1%` + UVIX profit/stop | `p = 9.5%`, no stop | 149.011% | -65.35% | 150 | 3.96% | 75.2% |

Interpretation:

- UVIX-only profit/stop rules do not beat the GSPC `gamma +0.1%` exit.
- Adding a UVIX profit threshold to the GSPC exit can raise CAGR in the coarse grid, but that adds a second direct P/L threshold and likely increases overfitting risk.
- UVIX stop-loss did not appear structurally useful in this coarse test.

Current decision: do not make UVIX profit/stop part of the canonical rule yet. Keep it as a research branch.

## Naming Convention Going Forward

Use explicit names so results are not confused:

- `direct_peak_dd_alpha`: TQQQ re-entry after drawdown `α%` from the immediate prior peak of TQQQ open
- `sma160_break_anchor_n`: TQQQ re-entry after drawdown `n%` from the TQQQ open recorded when GSPC fell below SMA160
- `bb20z_rsi_only`: BB entry plus RSI-only exit
- `bb20z_tqqq_drop`: old TQQQ proxy exit; not canonical
- `bb20z_gspc_profit`: GSPC-based early profit exit
- `bb20z_gspc_profit_uvix_profit`: experimental branch with additional UVIX profit-taking
- `bb20z_gspc_profit_gspc_stop`: experimental branch with GSPC stop-loss

Recommended canonical stem:

```text
canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220
canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212
canonical_stitched_1991
```

## 1991 Stitched Canonical

Added: 2026-05-05

The 1991 stitched canonical extends the backtest window to 1991-01-02 by prepending a synthetic pre-2005 series.

### Construction

- **1991-01-02 to 2005-12-19** — Synthetic canonical:
  - Full canonical logic: SMA160 base signal + BB20z/RSI overlays + drawdown re-entry + low-RSI TQQQ override
  - UVIX → Cash (`^IRX` daily rate, annualised / 252). UVIX did not exist pre-2005.
  - wait_mix (TMF 50% / GLD 50%) → Cash (`^IRX`). TMF/GLD data is limited pre-2005.
  - TQQQ → `TQQQ_CC_RETURN_REBUILT` (synthetic calibrated returns from `next_open_ohlc_series_tqqq_tmf_gld.csv`)
  - `ALPHA_DRAWDOWN_PCT = 100.0` (effectively disabled). The dot-com crash caused TQQQ to fall ~99.9% from its 2000 peak, so using the canonical α = 94.0% would erroneously trigger re-entry mid-crash.
- **2005-12-20 onward** — Actual canonical CSV (`from_20051220`), columns copied directly. Equity is re-based to continue from the pre-2005 terminal value.

### Output files

- `output/canonical_stitched_1991_daily_path.csv` — full 8,887-day stitched daily path
- `output/canonical_stitched_1991_summary.csv` — aggregate stats for the full 1991–2026 period

### Key metrics (1991-01-02 to 2026-04-17)

| Metric | Value |
|--------|------:|
| CAGR | 68.78% |
| Annualized Vol | 60.28% |
| Max Drawdown | -81.13% |
| CAGR/Vol | 1.141 |
| Final Multiple | ~104 million× |

The CAGR is lower than the 2005/2010 starts because the pre-2005 period (1991–2005) had much lower compound returns (~22.9% CAGR) due to dot-com crash exposure and the absence of real UVIX.

### なぜα=100%（再参入ルール無効）が全期間に適用されているか

`α=94%`は2005-start・2010-startカノニカルの最適化値。この数値はドットコムバブル崩壊（2000–2002）を含まない期間で最適化されている。

1991起点でα=94%を適用すると、2000–2002年のドットコム崩壊でTQQQの合成リターンが約99.9%下落し、α=94%の閾値が発動してバブル崩壊中にTQQQを再購入してしまう。これは「歴史を見た上で都合のよいパラメータを選んだ」のと同じことになる。

α=100%（再参入なし）は事前に決定できる保守的なルールである。post-2005でα=94%が実際に発動したのは2009年3月の5日間のみで、その5日間もα=100%（wait_mix継続）の方がわずかに成績が良かった（CAGR差 +0.11pp）。したがってα=100%全期間統一版は整合的かつ保守的な定義として成立する。

### Generator script

```text
tecl_sma160_rotation/build_canonical_1991_stitched.py
```

Re-run this script whenever the post-2005 canonical CSV is updated, then re-run the two build scripts to refresh embedded dashboard data:

```bash
python3 build_canonical_1991_stitched.py
python3 build_position_dashboard_html_embedded.py
python3 build_canonical_chart_html_embedded.py
```

## Dashboard Status

As of 2026-05-04, the canonical dashboard uses the direct prior-peak α drawdown base strategy plus the GSPC profit-exit high-RSI UVIX priority rule:

- HTML: `tecl_sma160_rotation/dashboard/canonical-chart.html`
- JS: `tecl_sma160_rotation/dashboard/canonical-chart.js`
- Payload source selector: `tecl_sma160_rotation/canonical_chart_data.py`
- Current stems:
  - `canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220`
  - `canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212`
- Embedded dashboard metadata:
  - `uvix_entry_rsi = 67.5`
  - `uvix_exit_rsi = 66.0`
  - `uvix_entry_min_bb_z = 1.6`
  - `uvix_gspc_profit_exit_pct = 0.1`
  - `uvix_tqqq_drop_exit_pct = null`
  - 2005-start: `cagr = 113.017%`, `max_drawdown = -69.63%`, `uvix_entries = 160`
  - 2010-start: `cagr = 153.453%`, `max_drawdown = -77.76%`, `uvix_entries = 142`

## Open Questions

- Whether the `+0.1%` GSPC threshold is too close to zero and should be rounded conceptually to `0.0%` for robustness.
- Whether the prior TQQQ exit's higher CAGR is an acceptable proxy artifact or should be rejected entirely.
- Whether GSPC stop-loss should be included despite minimal CAGR improvement.
- Whether UVIX profit-taking should be tested out-of-sample before being considered.
- Whether the dashboard should show multiple canonical candidates side-by-side instead of overwriting one canonical file.
