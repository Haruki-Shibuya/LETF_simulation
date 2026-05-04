# Forward P/E Filter Test Results

Last run: 2026-05-04 JST

## Inputs

- Forward P/E data:
  - `output/valuation_forward_pe_2005_sim_daily_ffill.csv`
  - S&P 500 forward P/E: Doinoff monthly, extended with Trendonify for 2026.
  - QQQ underlier forward P/E: Nasdaq-100 Trendonify monthly.
- 2005 canonical path:
  - `output/canonical_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20051220_daily_path.csv`
- 2010 canonical path:
  - `output/canonical_prev_close_signal_same_open_exec_direct_peak_dd_bb20z_gspc_profit_entry67p5_exit66p0_gamma0p1_low_rsi_tqqq_from_20100212_daily_path.csv`

The test keeps the existing canonical trading logic fixed, then applies valuation filters on top of the selected leg.

## Tested Filter Families

1. Hard filters:
   - High S&P 500 forward P/E: replace TQQQ with safety assets.
   - High Nasdaq-100 forward P/E: replace TQQQ with safety assets.
   - Low forward P/E: replace safety assets with TQQQ.
   - Forward P/E condition for allowing or blocking UVIX.
   - Two-variable S&P 500 + Nasdaq-100 thresholds.

2. Weighted filters:
   - At high forward P/E, reduce TQQQ exposure to 75%, 50%, 25%, or 0%, with the rest in safety assets.
   - At low forward P/E, add partial TQQQ exposure on safety-asset days.
   - Two-variable S&P 500 + Nasdaq-100 versions.

## Baselines

| Period | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| 2005-12-20 to 2026-04-17 | 113.02% | 56.58% | -69.63% | 2.00 |
| 2010-02-12 to 2026-04-17 | 108.40% | 64.53% | -77.84% | 1.68 |

## Main Result

Forward P/E filters did not produce a material CAGR improvement over canonical.

- 2005 start:
  - No tested non-trivial filter improved both CAGR and vol.
  - The best CAGR result is the baseline itself.
- 2010 start:
  - One tiny UVIX gating case improved both metrics, but it changed only 0.07% of days and is not meaningful enough to treat as robust.
  - Rule: block UVIX when S&P 500 forward P/E is below 12.5.
  - Result: CAGR 108.97%, vol 64.43%, max DD unchanged at -77.84%.

## Useful Risk-Control Results

Forward P/E is more useful as a risk-control knob than as a CAGR booster.

### 2005 Start

Best CAGR/vol style result:

| Rule | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.5, hold 75% TQQQ + 25% safety assets instead of 100% TQQQ | 103.22% | 50.44% | -63.77% | 2.05 |

This lowers CAGR by about 9.8 percentage points, but improves vol by about 6.1 percentage points and max drawdown by about 5.9 percentage points.

More defensive examples:

| Rule | CAGR | Vol | Max DD |
|---|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.0, hold 75% TQQQ + 25% safety assets | 101.60% | 50.04% | -64.14% |
| If Nasdaq-100 forward P/E > 19.0, hold 50% TQQQ + 50% safety assets | 92.63% | 46.89% | -57.63% |
| If Nasdaq-100 forward P/E > 19.0, hold 25% TQQQ + 75% safety assets | 80.20% | 44.84% | -53.47% |

### 2010 Start

Best CAGR/vol style result:

| Rule | CAGR | Vol | Max DD | CAGR / Vol |
|---|---:|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.5, hold 75% TQQQ + 25% safety assets instead of 100% TQQQ | 95.59% | 55.95% | -72.35% | 1.71 |

This lowers CAGR by about 12.8 percentage points, but improves vol by about 8.6 percentage points and max drawdown by about 5.5 percentage points.

More defensive examples:

| Rule | CAGR | Vol | Max DD |
|---|---:|---:|---:|
| If Nasdaq-100 forward P/E > 18.0, hold 75% TQQQ + 25% safety assets | 94.40% | 55.53% | -70.62% |
| If S&P 500 forward P/E > 15.5, hold 75% TQQQ + 25% safety assets | 96.94% | 57.36% | -70.01% |
| If S&P 500 forward P/E > 20.5, hold 75% TQQQ + 25% safety assets | 100.70% | 62.14% | -78.11% |

## Interpretation

The current canonical strategy already uses tactical trend, drawdown, RSI, BB, and UVIX logic. Simple forward P/E overlays mostly remove profitable TQQQ exposure and therefore tend to reduce CAGR.

The useful pattern is not "valuation improves CAGR." The useful pattern is:

- Nasdaq-100 forward P/E can reduce realized vol and drawdown if it is used to partially reduce TQQQ exposure.
- The tradeoff is a clear CAGR reduction.
- Full de-risking is usually too aggressive.
- 75% TQQQ / 25% safety assets at high Nasdaq-100 forward P/E is the least destructive risk-control version among the tested rules.

## Output Files

- `output/forward_pe_filter_tests_summary.csv`
- `output/forward_pe_filter_tests_from_20051220.csv`
- `output/forward_pe_filter_tests_from_20100212.csv`
- `output/forward_pe_weighted_allocation_tests_summary.csv`
- `output/forward_pe_weighted_allocation_tests_from_20051220.csv`
- `output/forward_pe_weighted_allocation_tests_from_20100212.csv`
- `test_forward_pe_filters.py`
