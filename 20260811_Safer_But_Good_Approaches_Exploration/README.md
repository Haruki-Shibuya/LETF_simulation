# Safer but Good Approaches Exploration

## Objective

Identify a TQQQ-based strategy that can compound aggressively over a long historical simulation while remaining implementable, tax-aware, robust to execution delays, and capable of surviving the complete dot-com collapse.

The primary research window should begin around 1996 and extend through the latest reproducible date.

## Hard Requirements

### 1. Pretax CAGR of at least 30%

The strategy must achieve a pretax compound annual growth rate of at least 30% over the full simulation period.

Pretax performance must be calculated after incorporating:

- ETF expense ratios
- Financing assumptions for leveraged exposure
- Trading costs and slippage assumptions
- Rebalancing drag
- The specified rebalance schedule

Gross or frictionless returns do not satisfy this requirement.

### 2. Execution robustness

The strategy must still satisfy, or remain close to, the return requirement when every signal is delayed by one trading day.

Every candidate must be tested with the following signal delays:

- 0 trading days
- 1 trading day
- 2 trading days
- 5 trading days

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
- Performance under 0-, 1-, 2-, and 5-day signal delays

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
2. Remains close to that return objective with a one-trading-day signal delay.
3. Avoids a near wipeout during the 2000–2003 dot-com collapse.
4. Produces a credible after-tax advantage or clearly explains why its pretax advantage does not survive taxation.
5. Remains reasonably stable across delay, parameter, cost, financing, and subperiod robustness tests.

The final recommendation should favor reproducibility and robustness over the highest in-sample CAGR.
