# Safer but Good Approaches Exploration

## Current result

The current in-sample winner under the requested 0/1-day execution-delay test is:

- SPY SMA: 150 trading days
- Nasdaq-100 volatility lookback: 40 trading days
- Annualized volatility threshold: 32%
- SMA hysteresis tolerance: 3%
- Risk-on: 100% TQQQ canonical stitched return
- Risk-off: one third each KMLMSIM, gold, and VFITX
- Pretax CAGR from the beginning of 2008: 40.21% with normal execution; 40.87% with one additional trading-day delay

See the complete Japanese technical report, data inventory, methodology, charts, limitations, and reproduction steps in [STRATEGY_AND_SIMULATION.md](./STRATEGY_AND_SIMULATION.md).

The initial comparison of five methods intended to improve the recent 2025–2026 result is in [RECENT_PERFORMANCE_5_METHODS.md](./RECENT_PERFORMANCE_5_METHODS.md). Its former 10% TQQQ risk-off sleeve improved 2026 YTD only from roughly -7% to -5%, so it is no longer recommended as a solution to the stated problem.

The replacement study in [REENTRY_2026_5_METHODS.md](./REENTRY_2026_5_METHODS.md) makes positive 2026 YTD a hard requirement and tests five dynamic re-entry families. The current research candidate re-enters TQQQ when the Nasdaq-100 remains above its 3-day SMA for five trading days, provided SPY is no more than 8% below SMA150 and 40-day Nasdaq volatility remains below 32%. The worse result across normal and one-day-additional delays is 6.58% for 2026 YTD, 40.41% full-period CAGR, and -58.91% maximum drawdown. This is still an in-sample research candidate pending tax-aware and walk-forward validation.

The TECL-versus-TQQQ follow-up tests five ways to use TECL only during selected parts of the original risk-on regime. See [TECL_TQQQ_ROTATION_5_METHODS.md](./TECL_TQQQ_ROTATION_5_METHODS.md). The current balanced research candidate confirms risk-on for five trading days, then holds TECL until its reference level gains 20%, and returns to TQQQ. It improves the post-2008 and actual-overlap CAGRs in-sample, but does not beat the original strategy's full-period CAGR and is not yet a production replacement.

## Objective

Identify a TQQQ-based strategy that can compound aggressively over a long historical simulation while remaining implementable, tax-aware, robust to execution delays, and capable of surviving the complete dot-com collapse.

The primary research window should begin around 1996 and extend through the latest reproducible date.

## Principles

- Full-period pretax CAGR must be at least 30% after modeled expenses, financing, trading costs, and rebalancing drag.
- Pretax CAGR from the beginning of 2008 through the simulation end must be greater than 30%, measured as a continued subperiod with the pre-2008 signal state retained.
- Both CAGR requirements must hold under the 0-day and 1-day additional-delay cases.
- The strategy must survive the full dot-com collapse without a near wipeout.
- Strategy and buy-and-hold comparisons must use realized-gain taxation, cost basis, loss offsets and carryforwards, tax deferral, and final-liquidation tax.
- Parameter neighborhoods, subperiods, costs, financing assumptions, and execution timing must be tested to reduce overfitting risk.

## Hard Requirements

### 1. Pretax CAGR of at least 30%

The strategy must achieve a pretax compound annual growth rate of at least 30% over the full simulation period.

It must also achieve greater than 30% pretax CAGR from the beginning of 2008 through the end of the simulation. Both thresholds apply to the 0-day and 1-day additional-delay cases.

Pretax performance must be calculated after incorporating:

- ETF expense ratios
- Financing assumptions for leveraged exposure
- Trading costs and slippage assumptions
- Rebalancing drag
- The specified rebalance schedule

Gross or frictionless returns do not satisfy this requirement.

### 2. Execution robustness

The strategy must still satisfy, or remain close to, the return requirement when every signal is delayed by one trading day.

Every candidate is currently tested with the following signal delays:

- 0 trading days
- 1 trading day

A strategy is rejected if a one-day delay causes its performance to collapse. Performance should degrade gradually rather than depend on exact same-day execution.

### 3. Dot-com survival

The simulation must begin around 1996 and include the complete 2000–2003 dot-com collapse.

Near-wipeout results are rejected even if the strategy later recovers and produces a high full-period CAGR. Evaluation must explicitly report the drawdown, recovery behavior, and portfolio path during the dot-com period.

### 4. Tax-aware comparison

Compare the strategy and buy-and-hold TQQQ on the same after-tax basis.

The tax model must account for:

- Taxes on realized gains rather than mark-to-market gains
- Position-level or lot-level cost basis
- Realized loss offsets
- Loss carryforwards
- The tax-deferral advantage of buy-and-hold
- Tax due upon final liquidation at the end of the simulation

Report both pretax and after-tax results. Do not apply a flat annual tax haircut to unrealized portfolio returns.

### 5. Realistic implementation

The backtest must incorporate:

- Daily leveraged compounding
- TQQQ expense ratio
- Explicit financing assumptions for leveraged exposure
- Expense ratios for defensive assets
- Trading costs and slippage assumptions
- The requested rebalance schedule
- Signal timing that prevents look-ahead bias

All implementation assumptions must be stated clearly and applied consistently across the strategy and benchmark where applicable.

## Required Comparisons

At minimum, compare each candidate against:

- Buy-and-hold TQQQ
- Buy-and-hold QQQ or its long-history total-return proxy
- Buy-and-hold S&P 500 total return

Strategy and benchmark results must use the same start date, end date, initial capital, tax assumptions, and final-liquidation treatment.

## Required Results

Report the following for the pretax and after-tax portfolios where applicable:

- CAGR
- Ending value
- Annualized volatility
- Maximum drawdown
- Drawdown duration and recovery date
- Worst calendar year
- Turnover
- Number of trades
- Taxes paid by year
- Realized losses carried forward
- Percentage of time in risk-on and risk-off states
- Performance under 0- and 1-day signal delays

Include a logarithmic equity curve starting from the same initial capital for every compared portfolio, with risk-on and risk-off periods clearly identified.

## Robustness and Rejection Tests

Candidate strategies should also undergo:

- Parameter-neighborhood or plateau tests
- Small changes to thresholds and lookback windows
- Alternative rebalance days or execution timing
- Higher trading-cost and slippage scenarios
- Alternative financing-cost assumptions
- Subperiod analysis, including 1996–2003, 2003–2009, 2009–2020, and 2020–present
- Walk-forward or out-of-sample testing where feasible

Reject strategies whose results depend primarily on a small number of perfectly timed trades, a single narrow parameter setting, accidental avoidance of rare events, or assumptions that could not have been implemented at the time.

## Acceptance Standard

A candidate qualifies for further consideration only if it:

1. Achieves at least 30% full-period pretax CAGR after modeled costs and drag.
2. Achieves greater than 30% pretax CAGR from 2008 onward after modeled costs and drag.
3. Meets both CAGR thresholds under the 0-day and 1-day additional-delay cases.
4. Avoids a near wipeout during the 2000–2003 dot-com collapse.
5. Produces a credible after-tax advantage or clearly explains why its pretax advantage does not survive taxation.
6. Remains reasonably stable across delay, parameter, cost, financing, and subperiod robustness tests.

The final recommendation should favor reproducibility and robustness over the highest in-sample CAGR.
