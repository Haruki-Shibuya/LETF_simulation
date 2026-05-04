# Valuation Data Source Review

Last checked: 2026-05-04 JST

## Objective

Canonical strategy robustness/improvement tests may use valuation inputs:

- S&P 500 trailing P/E
- S&P 500 forward P/E
- Nasdaq-100 trailing P/E
- Nasdaq-100 forward P/E

The first priority is to locate official or near-official historical data. If official historical values cannot be obtained, the next step is to decide whether to reconstruct the series from underlying earnings estimates and index prices.

## Current CSVs

Local monthly files currently available:

- `output/valuation_sp500_pe_multpl_monthly.csv`
- `output/valuation_sp500_forward_pe_trendonify_monthly.csv`
- `output/valuation_sp500_forward_pe_doinoff_monthly.csv`
- `output/valuation_nasdaq100_pe_trendonify_monthly.csv`
- `output/valuation_nasdaq100_forward_pe_trendonify_monthly.csv`
- `output/valuation_monthly_combined.csv`
- `output/valuation_monthly_master.csv`
- `output/valuation_forward_pe_2005_sim_monthly.csv`
- `output/valuation_forward_pe_2005_sim_daily_ffill.csv`
- `output/valuation_sp500_official_quarterly_actuals_pe.csv`
- `output/valuation_sp500_official_current_estimates_snapshot.csv`
- `output/valuation_sp500_factset_earnings_insight_forward_pe_daily.csv`
- `output/valuation_sp500_factset_earnings_insight_trailing_pe_daily.csv`
- `output/valuation_sp500_factset_pe_daily_master.csv`

These files are usable for exploratory testing, but not all are official-source data.

The S&P DJI workbook manually downloaded by the user is archived at:

- `output/source_official/sp-500-eps-est.xlsx`
- `output/source_official/factset_earnings_insight_extracted_estimates_public.csv`
- `output/source_official/factset_earnings_insight_extracted_estimates_confidence_public.csv`
- `output/source_official/doinoff_sp500_forward_pe_page.html`

## Source Review

| Series | Official-source status | Practical status | Notes |
|---|---|---|---|
| S&P 500 trailing P/E | S&P DJI official workbook is now available locally | Quarterly official actuals are saved from 2005-12 to 2025-09; Multpl monthly series remains available from 2005-01 to 2026-05 | Official quarterly actuals should be preferred for canonical-grade trailing P/E tests |
| S&P 500 forward P/E | S&P DJI workbook is available, but it is not a point-in-time historical forward P/E file | Doinoff embedded monthly series is saved from 1982-01 to 2025-12; Trendonify monthly series is saved from 2009-05 to 2026-04; FactSet Earnings Insight PDF/OCR point-in-time daily series is saved from 2016-12-09 to 2026-05-01 | For the 2005 simulation start, the practical full-coverage monthly series now uses Doinoff, then Trendonify for 2026 extension; FactSet PDF/OCR is retained as the higher-quality 2016+ cross-check |
| Nasdaq-100 trailing P/E | Nasdaq publishes research/factsheets using Nasdaq/FactSet/Bloomberg data, but raw historical valuation data is not publicly downloadable without GIW/GIDS access | Trendonify monthly series is saved locally from 2005-01 to 2026-04 | Starts before the 2005-12 canonical simulation start |
| Nasdaq-100 forward P/E | Nasdaq research references NDX next-12-month P/E, source FactSet, but raw monthly history appears not public | Trendonify monthly series is saved locally from 2005-01 to 2026-04 | Starts before the 2005-12 canonical simulation start |

## Official Locations Found

### S&P 500

S&P DJI S&P 500 page exposes an `Index Earnings` link. The linked workbook URL is:

`https://www.spglobal.com/spdji/en/documents/additional-material/sp-500-eps-est.xlsx`

Direct `curl`, browser-backed Playwright, and Jina text proxy all returned 403/security-control responses from this environment. The user manually downloaded the workbook and it has been copied locally.

The workbook is saved at:

`output/source_official/sp-500-eps-est.xlsx`

Extracted outputs:

- `output/valuation_sp500_official_quarterly_actuals_pe.csv`
  - 80 rows
  - 2005-12-31 to 2025-09-30
  - fields include S&P 500 price, quarterly operating EPS, quarterly as-reported EPS, TTM operating EPS, TTM as-reported EPS, operating P/E, as-reported P/E.
- `output/valuation_sp500_official_current_estimates_snapshot.csv`
  - Current estimate snapshot as of the workbook date, 2026-01-30.
  - This contains 2025 Q4 and 2026 quarter estimates as seen from 2026-01-30, not historical point-in-time estimates back to 2005.

Additional point-in-time estimate source obtained:

- Source: FactSet Earnings Insight public PDF archive, extracted by `eps-estimates-collector`.
- Local archived raw CSVs:
  - `output/source_official/factset_earnings_insight_extracted_estimates_public.csv`
  - `output/source_official/factset_earnings_insight_extracted_estimates_confidence_public.csv`
- Local calculated outputs:
  - `output/valuation_sp500_factset_earnings_insight_forward_pe_daily.csv`
    - 2,360 rows
    - 2016-12-09 to 2026-05-01
    - fields include report date, price date, S&P 500 price, next-four-quarter EPS sum, forward P/E.
  - `output/valuation_sp500_factset_earnings_insight_trailing_pe_daily.csv`
    - 2,360 rows
    - 2016-12-09 to 2026-05-01
    - fields include report date, price date, S&P 500 price, latest-four-quarter EPS sum, trailing P/E.
  - `output/valuation_sp500_factset_pe_daily_master.csv`
    - merged forward/trailing daily master.

This is not an S&P DJI official workbook, but it is materially better than using a current estimate snapshot for backtests because each estimate comes from the report date available at that time. It still does not solve 2005-12 to 2016-12 for S&P 500 point-in-time forward P/E.

Additional practical long-history source obtained:

- Source: Doinoff S&P 500 valuation visualizer embedded `PE_DATA`.
- Local archived HTML:
  - `output/source_official/doinoff_sp500_forward_pe_page.html`
- Local calculated output:
  - `output/valuation_sp500_forward_pe_doinoff_monthly.csv`
    - 528 rows
    - 1982-01-31 to 2025-12-31
    - fields include S&P 500 level, forward P/E, MPE, and monthly return.

This is not official, but it covers the 2005 canonical simulation start. For practical 2005-start valuation-filter experiments, this is the current S&P 500 forward P/E source with the broadest coverage.

### Nasdaq-100

Nasdaq official pages found:

- `https://indexes.nasdaq.com/Index/Overview/NDX`
- `https://indexes.nasdaq.com/docs/FS_NDX.pdf`
- `https://indexes.nasdaq.com/docs/NDX_Fundamentals.pdf`

The official fact sheet and research cite Nasdaq Index Research, Bloomberg, and FactSet. Public pages show that full month-end index files require login/subscription through Nasdaq Global Index Watch / Global Index Data Service. No public raw monthly trailing P/E or forward P/E download was found.

## Can S&P 500 Forward P/E Be Recalculated?

Yes, but not from this downloaded workbook alone.

Formula:

`S&P 500 forward P/E = S&P 500 index level / 12-month forward EPS`

The accepted methodology for 12-month forward EPS is to blend current-year and next-year consensus EPS by month:

- January: `12/12 * CY estimate + 0/12 * NY estimate`
- February: `11/12 * CY estimate + 1/12 * NY estimate`
- ...
- December: `1/12 * CY estimate + 11/12 * NY estimate`

This requires point-in-time monthly estimates for current year and next year. Reconstructing from today's final historical EPS would create look-ahead bias.

The downloaded S&P DJI workbook contains finalized historical EPS/P/E and a current estimate snapshot. It does not contain the monthly/quarterly point-in-time CY/FY estimate history needed to calculate true historical forward P/E from 2005 onward.

Using today's workbook estimates to backfill old dates would introduce look-ahead bias. Therefore:

- S&P 500 trailing P/E can now use official quarterly actuals.
- S&P 500 forward P/E can use FactSet Earnings Insight PDF/OCR point-in-time estimates from 2016-12 onward.
- S&P 500 forward P/E can use Doinoff monthly data from 1982-01 to 2025-12 for long-history exploratory tests, including 2005-start simulations.
- The existing Trendonify forward P/E series remains useful for exploratory testing from 2009-05 and for extending current 2026 months.

## Can Nasdaq-100 Forward P/E Be Recalculated?

In principle, yes:

`Nasdaq-100 forward P/E = NDX index level / NDX next-12-month EPS`

But reconstructing NDX next-12-month EPS correctly requires:

- point-in-time constituent weights,
- point-in-time analyst EPS estimates for each constituent,
- share/index divisor handling or an official index EPS aggregate,
- constituent changes over time,
- split and corporate-action adjustments.

Without FactSet/Bloomberg/Nasdaq GIW/GIDS-style data, a clean official reconstruction is not realistic.

## Backtest Usage Recommendation

For immediate exploratory testing:

- Use `output/valuation_forward_pe_2005_sim_monthly.csv` or `output/valuation_forward_pe_2005_sim_daily_ffill.csv`.
- Treat Trendonify-derived S&P/Nasdaq forward P/E as non-official exploratory data.
- Treat Doinoff-derived S&P forward P/E as non-official but practically useful for 2005-start coverage.
- Prefer the FactSet Earnings Insight PDF/OCR S&P 500 forward P/E from 2016-12 onward when testing look-ahead-safe valuation filters.
- For 2005 canonical, the current no-missing practical forward P/E file uses Doinoff for S&P 500 and Trendonify for the QQQ underlier/Nasdaq-100.

For canonical-grade testing:

- Use S&P DJI official workbook for S&P 500 if accessible.
- Use Nasdaq/FactSet/Bloomberg/GIW/GIDS data for Nasdaq-100 if accessible.
- If official Nasdaq data remains unavailable, prefer treating Nasdaq-100 valuation filters as exploratory only.
