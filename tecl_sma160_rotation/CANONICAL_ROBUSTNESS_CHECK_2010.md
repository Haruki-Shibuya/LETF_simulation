# Canonical Robustness Check 2010

Last updated: 2026-05-04

This note records the first robustness check for the current 2010-start canonical model.

The purpose is not to discover a new best model. The purpose is to test whether the current canonical candidate looks like an isolated overfit point.

## Tested Canonical

Current 2010-start canonical:

| Parameter | Value |
|---|---:|
| `alpha_drawdown_pct` | 40.5 |
| `gspc_exit_gamma_pct` | 0.1 |
| `uvix_entry_rsi` | 67.5 |
| `uvix_exit_rsi` | 66.0 |
| `bb_window_days` | 20 |
| `bb_z_threshold` | 1.6 |
| `low_rsi_entry` | 30.0 |
| `low_rsi_exit` | 32.5 |

Signal and execution assumption:

- Signal reference: current-day open.
- Execution: same current-day open.
- One transition per open.

## Candidate Set

The robustness check used a fixed local candidate set around the canonical parameters:

| Parameter | Values |
|---|---|
| `alpha_drawdown_pct` | 37.5, 40.5, 43.0 |
| `gspc_exit_gamma_pct` | 0.0, 0.1, 0.3 |
| `uvix_entry_rsi` | 67.0, 67.5, 68.0 |
| `uvix_exit_rsi` | 65.0, 66.0 |
| `bb_window_days` | 15, 20 |
| `bb_z_threshold` | 1.4, 1.6 |
| `low_rsi_entry` | 30.0 |
| `low_rsi_exit` | 32.5 |

Total candidates: 216.

This is intentionally a local robustness grid, not a new global optimization.

## Summary Results

| Check | Result |
|---|---:|
| Canonical full-period CAGR | 153.453% |
| Canonical max drawdown | -77.76% |
| Canonical UVIX episodes | 142 |
| Best candidate in local grid | Same as canonical |
| Anchored walk-forward OOS median yearly CAGR | 138.98% |
| Anchored walk-forward OOS positive-year share | 83.33% |
| Rolling 5-year walk-forward OOS median yearly CAGR | 133.13% |
| Rolling 5-year walk-forward OOS positive-year share | 75.00% |
| CSCV/PBO approximation | 6.65% |
| CSCV selected OOS loss probability | 0.00% |
| Median selected OOS CAGR in CSCV | 140.84% |
| UVIX episode mean return | 3.26% |
| UVIX episode median return | 2.08% |
| UVIX episode return volatility | 9.99% |
| UVIX episode win rate | 66.90% |
| Best UVIX episode | 65.16% |
| Worst UVIX episode | -28.22% |

Interpretation:

- Within the 216-candidate canonical-neighborhood grid, the current canonical is the best candidate. This is a positive sign for local parameter stability.
- Walk-forward OOS results are positive in most years, but not all years. The model had negative OOS years, especially 2022 and partial 2026.
- The CSCV/PBO approximation is low at 6.65%, meaning that within this local grid, the in-sample selected candidate usually remains above the OOS median.
- The UVIX overlay is not only one huge episode. Removing the best episodes hurts, but the CAGR remains high after removing the top 10 episodes.

## Walk-Forward Check

Anchored walk-forward:

- Train from 2010 through year `t-1`.
- Select the best candidate by train CAGR.
- Test on year `t`.

Results:

| Test setup | Mean OOS CAGR | Median OOS CAGR | Worst OOS CAGR | Best OOS CAGR | Positive year share |
|---|---:|---:|---:|---:|---:|
| Anchored | 195.46% | 138.98% | -74.79% | 897.46% | 83.33% |
| Rolling 5-year | 179.37% | 133.13% | -74.79% | 897.46% | 75.00% |

The negative OOS years show that the strategy is not uniformly robust year by year. The high positive median means the effect is not limited to one isolated test year.

## CSCV / PBO Approximation

Implementation:

- Years 2010-2025 were split into train/test halves.
- 2,000 random half-splits were sampled.
- For each split, the best train-CAGR candidate was selected.
- That selected candidate was ranked against all 216 candidates on the OOS half.

Results:

- PBO approximation: 6.65%.
- OOS loss probability: 0.00%.
- Median selected OOS CAGR: 140.84%.
- Mean selected OOS rank percentile: 12.29%.

Interpretation:

- In this local candidate set, the selected in-sample winner usually remains near the top out of sample.
- This is not proof of no overfitting. It says the current canonical neighborhood does not look like a fragile single point under this CSCV-style check.

## Leave-Top-Episodes-Out

| Removed top UVIX episodes | CAGR | Max drawdown |
|---:|---:|---:|
| 0 | 153.45% | -77.76% |
| 1 | 145.70% | -77.76% |
| 3 | 136.73% | -77.76% |
| 5 | 131.27% | -77.76% |
| 10 | 120.44% | -77.76% |

Interpretation:

- The strategy is helped by the best UVIX episodes, but it does not collapse when the best 1, 3, 5, or 10 UVIX episodes are neutralized.
- This is a useful check against the concern that the result is just one lucky UVIX spike.

## Execution Cost / Slippage Stress

This stress subtracts a fixed cost per transition day.

| Cost per transition | CAGR | Max drawdown |
|---:|---:|---:|
| 0 bps | 153.45% | -77.76% |
| 5 bps | 151.04% | -77.85% |
| 10 bps | 148.64% | -77.94% |
| 25 bps | 141.59% | -78.20% |
| 50 bps | 130.25% | -78.62% |
| 100 bps | 109.08% | -79.45% |

Interpretation:

- The strategy remains high-CAGR under moderate transition costs.
- The same-open execution assumption is still a strong assumption; this cost stress does not replace a true delayed-execution test.

## Start-Date Sensitivity

This check reruns the canonical from later start dates.

| Start | CAGR | Max drawdown | UVIX episodes |
|---|---:|---:|---:|
| 2010-02-12 | 153.45% | -77.76% | 142 |
| 2011-01-03 | 140.83% | -77.76% | 132 |
| 2012-01-03 | 140.14% | -77.76% | 123 |
| 2013-01-02 | 143.43% | -77.76% | 112 |
| 2014-01-02 | 125.14% | -77.76% | 103 |
| 2015-01-02 | 129.27% | -77.76% | 97 |

Interpretation:

- CAGR remains high across later starts.
- Later-start checks are not independent OOS tests, but they reduce the concern that the 2010 start date alone creates the result.

## Output Files

```text
output/canonical_robustness_2010_open_signal_summary.csv
output/canonical_robustness_2010_open_signal_candidate_grid.csv
output/canonical_robustness_2010_open_signal_walk_forward.csv
output/canonical_robustness_2010_open_signal_cscv_pbo_approx.csv
output/canonical_robustness_2010_open_signal_uvix_episodes.csv
output/canonical_robustness_2010_open_signal_leave_top_episodes.csv
output/canonical_robustness_2010_open_signal_slippage_stress.csv
output/canonical_robustness_2010_open_signal_start_date_sensitivity.csv
```

## Limitations

- The candidate set is local. A broader global parameter universe could produce a different PBO.
- The model still relies on same-open signal and same-open execution. That assumption needs a separate delayed-execution robustness test.
- The UVIX episode return distribution here uses the practical strategy-return contribution during UVIX-selected days, not a separate mark-to-market-only UVIX leg attribution.
- This check does not validate live data availability at the open.

## Current Assessment

The current 2010-start canonical passes this first robustness check better than expected:

- It is the best point inside the tested local grid.
- Walk-forward OOS is mostly positive.
- PBO approximation is low.
- Removing top UVIX episodes does not destroy the result.
- Slippage stress reduces CAGR but does not make the strategy fail.

The largest remaining robustness risk is not parameter overfitting inside this local neighborhood. The largest remaining risk is the same-open signal/execution assumption.
