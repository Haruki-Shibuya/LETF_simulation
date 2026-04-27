# testfolio Help Extract

Source: https://testfol.io/help#tactical
Extracted: 2026-04-26
Method: Playwright browser automation; all `.q-expansion-item` accordions expanded before extracting `document.body.innerText`.

```text
testfolio
Create Free Account
Tools
My Workspace
Docs
Pricing
Sign in
Help

This page is the methodology and references hub for testfolio. It explains how the portfolio backtester, analyzers, optimizers, tactical tools, calculators, and custom tickers work so you can interpret results consistently and move between tools with a clearer view of the assumptions.

If you landed here from a specific workflow, jump directly to the relevant tool section below. For hands-on use, you can return to the Portfolio Backtester, Asset Analyzer, Portfolio Optimizer, start with the Portfolio Backtester guide, browse the full guide library, or Pricing at any time.

Jump to a topic
Portfolio Backtester
Asset Analyzer
Monte Carlo Portfolio Simulator
Portfolio Optimizer
Backtest Optimizer
Efficient Frontier
Tactical Allocation
Grid Search
Signal Analyzer
Dual Signal Analyzer
Multi Signal Analyzer
Factor Regression
Principal Component Analysis
LETF Analysis
Lump Sum vs DCA
Calculator Suite
Time Value of Money
Custom Tickers
Custom Bond Tickers
Tickers
Tickers
Base Tickers:
Portfolios consist of ticker symbols, usually an ETF, mutual fund, or stock. Tickers cannot have spaces in their names.
Due to data licensing constraints, only US stocks/funds/ETFs are currently available.

Special Tickers:
There are a number of preset tickers that represent assets which aren't actual ETFs/mutual funds. With the exception of TBILL/CASHX, and EFFRX, all preset tickers track total return, i.e. there will be no difference with or without dividends reinvested.

TBILL/CASHX: These are equivalent and represent the performance of a continuous investment in 3-month Treasury Bills. Use this as a substitute for any cash allocation.
EFFRX: An alternative cash allocation that represents the performance of a continuous investment at the Effective Federal Funds Rate.
SPYSIM/SPYTR: A simulated total return SPY ETF with a 0% ER going back to 1885.
OEFSIM: A simulated total return OEF ETF with a 0% ER going back to 1989.
MDYSIM: A simulated total return MDY ETF with a 0% ER going back to 1991.
IJRSIM: A simulated total return IJR ETF with a 0% ER going back to 1994.
IWMSIM: A simulated total return IWM ETF with a 0% ER going back to 1978.
USMVSIM: A simulated total return USMV ETF with a 0.15% ER going back to 1988.
KMLMSIM/KMLMX: A simulated total return KMLM ETF with a 0.9% ER going back to 1988.
GLDSIM/GOLDX: A simulated gold ETF with a 0% ER going back to 1968.
SLVSIM: A simulated silver ETF with a 0% ER going back to 1968.
SVIXSIM/SVIXX: A simulated SVIX ETF with a 1.35% ER going back to 2005.
UVIXSIM: A simulated UVIX ETF with a 1.35% ER going back to 2005.
ZVOLSIM/ZIVBX: A simulated ZVOL ETF with a 1.35% ER going back to 2004.
TLTSIM/TLTTR: A simulated total return TLT ETF with a 0.15% ER going back to 1962. This uses B!YL=DGS20&YH=DGS30&ML=20&M=26&MH=30&E=0.15 to backfill TLT before 2002. See Custom Bond Tickers for more information.
ZROZSIM/ZROZX: A simulated total return ZROZ ETF with a 0.15% ER going back to 1962. This uses B!YL=DGS20&YH=DGS30&ML=20&M=28&MH=30&C=Z&E=0.15 to backfill ZROZ before 2009. See Custom Bond Tickers for more information.
VXUSSIM/VXUSX: A simulated total return VXUS ETF with a 0% ER going back to 1970.
EFASIM: A simulated total return EFA ETF with a 0% ER going back to 1970.
VEASIM: A simulated total return VEA ETF with a 0% ER going back to 1970.
VWOSIM: A simulated total return VWO ETF.
VSSSIM: A simulated total return VSS ETF.
EFVSIM: A simulated total return EFV ETF.
VTISIM/VTITR: A simulated total return VTI ETF with a 0% ER going back to 1926.
VTSIM: A simulated total return VT ETF with a 0% ER going back to 1970.
URTHSIM: A simulated total return URTH ETF with a 0% ER going back to 1970.
DBMFSIM/DBMFX: A simulated total return DBMF ETF with a 0.85% ER going back to 2000.
VIXSIM/VOLIX: Represents the VIX going back to 1990.
ZEROX: A ticker that has a 0% nominal return going back to 1885.
GSGSIM/GSGTR: A simulated total return GSG ETF with a 0.75% ER going back to 1979.
IEFSIM/IEFTR: A simulated total return IEF ETF with a 0.15% ER going back to 1962. This uses B!YL=DGS7&YH=DGS10&ML=7&M=8.42&MH=10&E=0.15 to backfill IEF before 2002. See Custom Bond Tickers for more information.
IEISIM/IEITR: A simulated total return IEI ETF with a 0.15% ER going back to 1962. This uses B!YL=DGS3&YH=DGS7&ML=3&M=4.8&MH=7&E=0.15 to backfill IEI before 2007. See Custom Bond Tickers for more information.
SHYSIM/SHYTR: A simulated total return SHY ETF with a 0.15% ER going back to 1962. This uses B!YL=DGS1&YH=DGS3&ML=1&M=2&MH=3&E=0.15 to backfill SHY before 2002. See Custom Bond Tickers for more information.
TIPSIM: A simulated total return TIP ETF.
STIPSIM: A simulated total return STIP ETF.
LTPZSIM: A simulated total return LTPZ ETF.
VCITSIM: A simulated total return VCIT ETF.
BTCSIM/BTCTR: A simulated bitcoin ETF with a 0% ER going back to 2010.
ETHSIM/ETHTR: A simulated ethereum ETF with a 0% ER going back to 2016.
MTUMSIM: A simulated total return MTUM ETF with a 0.15% ER.
XLBSIM/XLBTR: A simulated total return XLB ETF with a 0.09% ER going back to 1926.
XLCSIM/XLCTR: A simulated total return XLC ETF with a 0.09% ER going back to 1926.
XLESIM/XLETR: A simulated total return XLE ETF with a 0.09% ER going back to 1926.
XLFSIM/XLFTR: A simulated total return XLF ETF with a 0.09% ER going back to 1926.
XLISIM/XLITR: A simulated total return XLI ETF with a 0.09% ER going back to 1926.
XLKSIM/XLKTR: A simulated total return XLK ETF with a 0.09% ER going back to 1926.
XLPSIM/XLPTR: A simulated total return XLP ETF with a 0.09% ER going back to 1926.
XLUSIM/XLUTR: A simulated total return XLU ETF with a 0.09% ER going back to 1926.
XLVSIM/XLVTR: A simulated total return XLV ETF with a 0.09% ER going back to 1926.
XLYSIM/XLYTR: A simulated total return XLY ETF with a 0.09% ER going back to 1926.
QQQSIM/QQQTR: A simulated total return QQQ ETF with a 0.2% ER going back to 1986.
INFLATION: The US Consumer Price Index going back to 1885.
CAOSSIM: A simulated total return CAOS ETF going back to 2013.
FNGUSIM: A simulated total return FNGU ETN going back to 2018.
MCISIM: A simulated total return MCI going back to 1980.
GDESIM: A simulated total return GDE going back to 1968.
RSSBSIM: A simulated total return RSSB going back to 1969.
NTSDSIM: A simulated total return NTSD going back to 1969.
UUPSIM: A simulated total return UUP with 0.7% ERgoing back to 1971.
VVSIM/VOOSIM: A simulated total return VOO (US Large Cap) ETF with a 0% ER going back to 1926.
VTVSIM: A simulated total return VTV (US Large Cap Value) ETF with a 0% ER going back to 1926.
VUGSIM: A simulated total return VUG (US Large Cap Growth) ETF with a 0% ER going back to 1926.
VOSIM: A simulated total return VO (US Mid Cap) ETF with a 0% ER going back to 1926.
VOESIM: A simulated total return VOE (US Mid Cap Value) ETF with a 0% ER going back to 1926.
VOTSIM: A simulated total return VOT (US Mid Cap Growth) ETF with a 0% ER going back to 1926.
VBSIM: A simulated total return VB (US Small Cap) ETF with a 0% ER going back to 1926.
VBRSIM: A simulated total return VBR (US Small Cap Value) ETF with a 0% ER going back to 1926.
VBKSIM: A simulated total return VBK (US Small Cap Growth) ETF with a 0% ER going back to 1926.
IWCSIM: A simulated total return IWC (US Micro Cap) ETF with a 0% ER going back to 1926.
BNDSIM: A simulated total return BND ETF with a 0.03% ER.
REITSIM: A simulated total return VNQ going back to 1993.
FF3*: Fama-French 3 Factor Model factors (MKT, SMB, HML) going back to 1926. Those are not directly investable portfolios.
FF5*: Fama-French 5 Factor Model factors (MKT, SMB, HML, RMW, CMA) going back to 1963. Those are not directly investable portfolios.
Ticker Modifiers
You can create a custom ticker out of any underlying ticker using ticker modifiers with the following format: [underlying ticker]?[param1]=[val1]&[param2]=[val2]&....

Parameters:
Possible parameters include UE, UR, UV, UC, DB, DBREF, FB, FBE, L, SW, SP, E, SD, BK, BL, BH, BR, BREF, CU, and CL.
UE: This adds UE% annually to the underlying return series. Since almost all ETFs and mutual funds have an expense ratio that causes them to lag their target index, specifying this parameter lets you adjust for that. This is useful for simulating LETFs, since most track an index rather than a specific ETF. By default, UE is 0%.
UR, UV: These smoothly adjust the CAGR and volatility (respectively) of the underlying return series across the backtest period while still maintaining a nearly identical daily return profile. By default, UR and UV are the same as those of the underlying, resulting in no change.
L, SW, SP: These specify the parameters for simulating a daily-resetting leveraged ETF out of the underlying return series, as described here. In short, L is the daily rebalanced leverage, SW is the swap exposure per unit of leverage, and SP is the spread paid on top of the FFR. By default, L is 1 (resulting in no change), SW is 1.1, and SP is sgn(L) * 0.4%. The total annual cost of leverage is then calculated as SW * (L-1) * (FFR%+SP).
The default values for SW and SP are based on a holdings analysis of several popular LETFs. The best SW and SP values may differ depending on the specific LETF you are trying to simulate.
E: This subtracts E% annually from the final return series. By default, E is 0%, but adds an extra 0.333% for every point of negative leverage, or 0.5% for every point of positive leverage above 1.
The default value for E assumes a typical 1% expense ratio for -3x and 3x LETFs, and assumes you will scale down leverage by holding the base 1x ETF (for positive leverage) or cash (for negative leverage). The best E value may differ depending on the expense ratio of the LETF you are trying to simulate.
SD: integer seed used for reproducibility when randomness is involved. The tools auto‑inject an SD when any of UC/BK/BL/BH/BR is present but no seed is provided.
UC: target correlation in [-1, 1]. Adjusts the daily return series to have correlation UC relative to the underlying series. Requires randomness and therefore uses SD.
DB, DBREF: de-beta modifiers. DB is a flag: either Y or N (default); when set to Y, the custom series is de-beta'd (strip out beta and enforce target beta = 0) versus a reference ticker. DBREF selects the reference ticker and defaults to SPYSIM when omitted.
FB, FBE: fill-backward modifiers. FB selects a ticker whose returns are spliced in before the main ticker to extend its history. FBE is an optional adjustment in percent applied only to the FB leg: positive values add return (e.g. to undo a higher mutual-fund ER), while negative values subtract return. For example, to backfill TLT with VUSTX before TLT existed, and compensate for a higher historical fee, you could use TLT?FB=VUSTX&FBE=0.05, which splices in VUSTX history before TLT and adds roughly 0.05% per year to the VUSTX leg.
CU, CL: daily return caps in percent units. CU caps the daily return from above (e.g. CU=1.2 caps each day at +1.2%), and CL caps from below (e.g. CL=-0.7 caps each day at -0.7%). Caps are applied after UR/UV/UC/DB but before leverage and costs.
Shuffle blocks: BK, BL, BH, BR (This feature could be used to test sequence of return risk, but use with caution. Setting the same seed SD in different tickers produces the same blocks and shuffles for both tickers)
The shuffle feature reorders contiguous blocks of the daily return series while preserving the overall terminal return. This changes the sequence of returns without changing the final value.
BK: target number of blocks (segments). When used alone, we sample a composition of the series into BK random-length parts (each ≥ 1 day), then randomly permute those parts.
BL: minimum block length in trading days (defaults to 1 if omitted). With BK present, all BK parts are at least BL days long. With BH present, we use the bounded mode below.
BH: maximum block length in trading days (optional). If provided (with or without BK), we ignore BK and choose a feasible number of blocks K uniformly from [ceil(N/BH), floor(N/BL)], then sample lengths so each block is within [BL, BH] and concatenate after a random permutation.
BR: per-block reversal probability in [0, 1]. After shuffling blocks, each block is independently reversed with probability BR.
BO: block order after segmentation. Defaults to R (random permutation). Set to I to order blocks by increasing annualized return, or D for decreasing order.
BREF: reference base ticker (no custom params allowed) used to derive the block order when BO is I or D. Ignored when BO=R. This modifier allows you to order blocks based on the annualized block returns of another ticker.
Shuffle triggers if any of the following are set: BK>0, BL>1, or BH present. Otherwise the series is left unchanged.
Notes: The shuffling operates on trading days only (weekends/market holidays are not treated in any special way).
Examples:
SPY?BK=8&SD=123 → 8 random blocks, shuffled.
QQQ?BK=8&BL=21&SD=42 → 8 blocks, each at least 21 days.
TLT?BL=21&BH=60&SD=7 → random bounded blocks in [21, 60] days; number of blocks chosen from the feasible range.
SPY?BK=10&BR=0.3&SD=9 → 10 shuffled blocks; each block has a 30% chance to be reversed.
TLT?BL=21&BH=60&BO=I&BREF=SPY&SD=123 → bounded blocks ordered by SPY's per-block annualized performance (increasing).
SPY?BL=21&BH=60&BO=I&SD=5 → bounded blocks (21-60 days) ordered by increasing annualized return.
SPY?BK=8&BO=D&SD=11 → 8 blocks ordered by decreasing annualized return.
The order in which the parameters are applied to the underlying are as follows: FB/FBE → UE → BK/BL/BH/BR/BO → UC → UR/UV → DB/DBREF → CU/CL → L/SW/SP → E. Parameters in the ticker itself can be specified in any order.
For modifiers that take a ticker parameter (such as FB, DBREF, and BREF), you can also pass a full custom ticker expression wrapped in parentheses, for example: TQQQ?FB=(QQQSIM?L=3).
Values for percentages are specified in percentages without the percent sign. For example, for 0.95%, you would use 0.95.
All percentages are nominal. UE, UR, and E only adjust the nominal return of their targets.
The maximum single-day loss for a leveraged ticker is capped at -100%.
Examples: To create a simulated UPRO (3x S&P 500), you could use SPYSIM?L=3. If you wanted to adjust its swap exposure to 1.2 and its expense ratio to 0.9%, you could use SPYSIM?L=3&SW=1.2&E=0.9. If you wanted to see how 3x SPYSIM would have performed if its CAGR/volatility had been 9%/20%, you could use SPYSIM?L=3&UR=9&UV=20.
Custom Bond Tickers
You can create a simulated constant-maturity bond fund out of a FRED daily yield series using the following format: B![param1]=[val1]&[param2]=[val2]&.... The method for simulating bond ETF returns is adapted from here.

Parameters:
Possible parameters are Y, M, W, C, SY, EY(simple, flat assumption) or YL, YH, ML, MH, M, C, W, SY, EY(more accurate, curve aware).
Y (flat only): FRED daily yield series used as the base history (e.g., DGS30).
YL, YH (curve-aware only): Lower and higher FRED daily yield series (e.g., DGS7, DGS10).
M: Target maturity in years (non-negative float; mandatory).
ML, MH (curve-aware only): Maturity anchors for YL and YH (years) with ML < M < MH. If omitted, they are inferred from the FRED codes of YL/YH (e.g., DGS7 → 7y, DGS3MO → 0.25y).
W: Coupon lookback window in years. For TLT-like behavior (buy 30Y/sell after 10Y), use W=10. Default is 1 day.
C: Coupon type C = coupon paying bonds or Z = zero-coupon bonds. For zero coupon, W is ignored. By default, C is C.
SY, EY: These linearly adjust the underlying yield history across the backtest period such that the starting yield is SY% and the ending yield is EY%. By default, SY% and EY% are the same as the original, resulting in no change.In curve-aware mode, the tilt is applied to the high tenor and an equal daily offset is added to the low tenor to preserve the slope.
Formatting of parameters is the same as with custom tickers.
For backtesting purposes, the [DGS30] FRED data series is spliced with [DGS20] before 1977, back to 1962. If for some reason you don't want the spliced 20Y data, set your start date to 1977.
Currently supported FRED yield series include: DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS3, DGS5, DGS7, DGS10, DGS20, DGS30.
Simulated bond tickers can be used as the underlying ticker for custom tickers.
Examples (flat-curve method):
TLT: B!Y=DGS30&M=26&W=10&E=0.15
ZROZ: B!Y=DGS30&M=28&E=0.15&C=Z
TLT with yields 5% → 4%: B!Y=DGS30&M=26&E=0.15&SY=5&EY=4, this would simulate how TLT would have performed if the 30Y had started at 5% and ended at 4%
Examples (curve-aware method):
IEF: B!YL=DGS7&YH=DGS10&ML=7&M=8.4&MH=10&E=0.15
ZROZ: B!YL=DGS20&YH=DGS30&ML=20&M=28&MH=30&C=Z&E=0.15
IEF with yields 2% → 6%: B!YL=DGS7&YH=DGS10&ML=7&M=8.4&MH=10&E=0.15&SY=2&EY=6, this would simulate how IEF would have performed if the 10Y had started at 2% and ended at 6%, and the 7Y was such that 10Y-7Y spread was maintained.
Tools
Portfolio Backtester
Formatting:

There is a limit of 5 portfolios per backtest, and a limit of 10 tickers per portfolio.
Tickers must be accompanied by a corresponding percentage within the portfolio, which can be negative. Otherwise, it will be ignored. To perform a backtest, the percentages in an portfolio need to add up to 100%.
Note that all tickers are assumed to represent prices in the same currency. If you mix and match different tickers that are traded in different currencies, you will get inaccurate results.

Methodology:

Portfolios are invested on the close of the specified start date. If a start date is not specified, historical data going as far back as possible is used.
Rebalancing and cashflows are performed at the close of the last trading day of the specified period by default (offset = 0). When an offset is specified:
Offset = 0: Rebalancing occurs on the last trading day of the period (default)
Offset = 1: Rebalancing occurs on the second-to-last trading day of the period
Offset = 2: Rebalancing occurs on the third-to-last trading day of the period
Offset = n: Rebalancing occurs on the (n+1)-to-last trading day of the period
Cashflows are distributed across the portfolio according to the portfolio's allocation at that time.
Cashflows can be defined as multiple legs with their own amount, frequency, offset, and optional end date; legs are applied in chronological order.
Each cashflow leg can be specified as either a fixed dollar amount or a percentage of the portfolio value at the time of the cashflow; when using a percentage, only negative values (withdrawals) are allowed.
When multiple cashflow legs are specified, their dates must be in order and within the effective backtest window; legs without an end date run until the backtest end.
If a cashflow and a rebalance occurs on the same date, the cashflow occurs before the rebalancing.
Checking the "Invest dividends" box on a portfolio will reinvest all dividends into their respective assets on the distribution date. This properly simulates the "total return" of the portfolio.
All preset tickers (except TBILL/CASHX/EFFRX) track only total return, so choosing to invest dividends or not for those will not change anything for them.
Checking the "Rebalance bands" box will allow you to specify absolute and relative deviation thresholds for rebalancing.
An asset with a target allocation of 10% in a portfolio with an absolute deviation threshold of 5% will trigger a rebalance if it ends a trading day outside of the range of 5% to 15%.
An asset with a target allocation of 10% in a portfolio with a relative deviation threshold of 25% will trigger a rebalance if it ends a trading day outside of the range of 7.5% to 12.5%.
Setting a threshold to 0% will disable that type of rebalancing band.
Rebalancing bands can be used at the same time as periodic rebalancing.
Checking the "Adjust for inflation" adjusts every dollar amount in the backtest for inflation to the start date.
In other words, if a portfolio is backtested starting in 1970 and ending in 2024, and the backtest is adjusted for inflation, all dollar values will be in 1970 dollars, not 2024 dollars.
This applies for cashflows too, so a $100 cashflow will always represent $100 in 1970 dollars.
Benchmark picker: if left unchecked, SPYSIM is used as the benchmark. If checked, your selected ticker is used instead for benchmark-based metrics and is also included as an additional benchmark result row.
MWRR and the portfolio value chart take into account cashflows. All other statistics and charts ignore cashflows, including CAGR, which behaves like TWRR if there are cashflows.
Saved portfolios are stored in your browser's localStorage. No saved data ever reaches our servers.

Statistics:

Sharpe and Sortino ratios are calculated ex-post with excess daily returns and volatility, using TBILL as the risk-free asset, then annualized.
The mean daily excess return is found by taking the arithmetic mean of realized daily excess returns over the entire time period.
The Excess CAGR rolling metric is NOT the same excess return used to calculate the rolling Sharpe ratio; it is simply the portfolio's CAGR minus TBILL CAGR over the time period.
Rolling Skewness measures the asymmetry of daily return distribution within each rolling window (0 ≈ symmetric).
Rolling Kurtosis is excess kurtosis of daily returns within each rolling window (0 ≈ normal; fat tails > 0).
Rolling Full Kelly is the optimal daily leverage to maximize CAGR with borrowing at the T-bill rate; computed per window.
The Ulcer Index is an alternative measure of risk that uses the magnitude and duration of drawdown rather than volatility. More information can be found here.
Avg Drawdown is the average drawdown depth across all days when the portfolio is below an all time high.
Longest Drawdown is the longest consecutive time the portfolio spends below an all time high.
The Calmar Ratio measures risk-adjusted returns by dividing CAGR by the absolute value of maximum drawdown. Higher values indicate better risk-adjusted performance.
The Drawdown Recovery Factor measures total return relative to the worst historical drawdown, computed as cumulative return divided by the absolute value of maximum drawdown. Higher values indicate more total return earned per unit of drawdown.
The Diversification Ratio measures the risk reduction from combining imperfectly correlated assets (weighted avg of asset volatilities / portfolio volatility).
Other Risk and Return Metrics:
Downside Deviation: standard deviation-like risk measure that only uses negative returns: sqrt(mean(min(0, r)^2)). It is reported for daily/monthly/annual returns, and annualized variants are scaled by sqrt(252) (daily) or sqrt(12) (monthly).
Benchmark Correlation: Pearson correlation between portfolio daily returns and selected benchmark daily returns (SPYSIM by default) over overlapping dates.
Beta: daily-return beta vs selected benchmark (SPYSIM by default), computed from return covariance/volatility relationship.
Alpha (daily / annualized): CAPM alpha using daily excess returns: (r_p - r_f) - beta * (r_m - r_f), with TBILL as r_f; annualized alpha is daily alpha × 252.
Upside Capture Ratio: portfolio return vs benchmark return using only periods where benchmark return is positive; 100 means matching benchmark upside capture.
Downside Capture Ratio: same concept as upside capture, but only for periods where benchmark return is negative.
Capture Spread: Capture Spread: Upside Capture Ratio minus Downside Capture Ratio (reported for daily/monthly/annual variants). Measures asymmetric capture efficiency relative to the benchmark (0). Positive values indicate the portfolio is more efficient at capturing gains than it is at realizing losses.
Active Return: annualized portfolio return minus annualized benchmark return over the same aligned dates.
Tracking Error: annualized standard deviation of daily active returns (r_p - r_m).
Information Ratio: Active Return divided by Tracking Error.
Modigliani–Modigliani Measure (M²): Sharpe ratio translated into return units: rf + Sharpe * benchmark_vol, reported as an annualized percent metric.
Value at Risk (VaR): empirical left-tail percentile cutoff of returns (shown at 1%, 5%, and 10% for daily/monthly/annual returns).
Conditional Value at Risk (CVaR): average return of observations in the VaR tail (returns less than or equal to the VaR threshold).
Average Gain: arithmetic mean of returns conditional on returns being positive.
Average Loss: arithmetic mean of returns conditional on returns being negative.
Gain/Loss Ratio: Average Gain divided by absolute value of Average Loss.
Cumulative Return is the cumulative return over the backtest period (ending value divided by starting value minus 1), ignoring cashflows.
Return Required to Recover (RRTR) Chart: This chart shows the inverse of the drawdown chart, displaying the return required to recover from a drawdown. For example:
A 1.25x RRTR corresponds to 25% return required to recover, which occurs when the drawdown is 20%
A 50% drawdown requires a 2x (100%) return to recover
A 90% drawdown requires a 10x (900%) return to recover
A 99% drawdown requires a 100x (9900%) return to recover
Nominal Ending Value shows the ending balance in nominal dollars when inflation adjustment is enabled. Only the final balance is converted back to nominal terms; cashflows and all other statistics remain inflation adjusted.
Total Contributions represents the initial investment plus the cumulative sum of all cashflows (contributions/withdrawals) made during the backtest period. This helps you understand the total amount invested versus the ending value.
The n-Month Lump Sum Win Rate is the percent of n-month rolling periods where a lump sum (LS) investment outperformed a daily DCA spread evenly throughout the period. The DCA does not assume any interest gained from sitting in cash.
The n-Month MLSA and MLSD (Mean Lump Sum Advantage and Disadvantage) is the average percent difference between LS and DCA given that LS outperformed (MLSA) or underperformed DCA (MLSD) over all n-month rolling periods.
A 3-month MLSA of 5% means that, on average, when LS outperformed DCA in a 3-month period, the LS portfolio was 5% larger than the DCA portfolio.
A 12-month MLSD of -3% means that, on average, when LS underperformed DCA in a 12-month period, the LS portfolio was 3% smaller than the DCA portfolio.
Safe Withdrawal Survival Analysis:
w% Port. Surv. Rate: % of N-year rolling windows where daily, inflation-adjusted withdrawals at an annual rate of w% never deplete the portfolio.
w% SCTM (Survival-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across those windows where daily, inflation-adjusted withdrawals at an annual rate of w% keep the portfolio > 0.
Perpetual Withdrawal Preservation Analysis:
w% Port. Pres. Rate: % of N-year rolling windows where daily, inflation-adjusted withdrawals at an annual rate of w% end with terminal wealth ≥ initial portfolio.
w% PCTM (Preservation-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across those windows where daily, inflation-adjusted withdrawals at an annual rate of w% preserve or grow starting capital.
Safe Withdrawal Rate Analysis:
p% Surv. SWR: the annual withdrawal rate (daily, inflation-adjusted) w% such that at least p% of N-year rolling windows never deplete the portfolio.
p% SCTM (Survival-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across windows that survive when withdrawing daily (inflation-adjusted) at w% = p% Surv. SWR.
Perpetual Withdrawal Rate Analysis:
p% Pres. PWR: the annual withdrawal rate (daily, inflation-adjusted) w% such that at least p% of N-year rolling windows end with terminal wealth ≥ initial.
p% PCTM (Preservation-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across windows that preserve or grow capital when withdrawing daily (inflation-adjusted) at w% = p% Pres. PWR.
Extended Withdrawal Stats (Curves):
When enabled, the Withdrawal Stats tab includes a Curves view that shows SWR and PWR across retirement lengths (x-axis is retirement length in years; y-axis is annual withdrawal rate).
Extended withdrawal stats: enables the curve calculations and includes them in the results response.
Projection:
No projection: only windows fully contained in the available historical data are included.
Use portfolio long-term CAGR: when a window extends past the end of available history, the tail is extended using the portfolio’s long-term growth rate.
Loop around: when a window extends past the end of available history, the tail is extended by continuing from the beginning of the backtest history.
Min real years: minimum amount of real historical data that must be present within each window before projection is used.
Seasonality charts show the average annual cumulative return path for each portfolio, aligned by calendar days.
Annual returns are calculated from the closing value of the portfolio on the last trading day of each year.
The annual return percentages ignore cashflows, while the annual balances include cashflows.
Monthly returns are calculated from the closing value of the portfolio on the last trading day of each month.
The monthly return percentages ignore cashflows, while the monthly balances include cashflows.
The daily return percentages ignore cashflows, while the daily balances include cashflows.
The average number of rebalancings per year is the total number of rebalancings divided by the number of years in the backtest, assuming there are 252 trading days in a year.
The average turnover per rebalancing is the average percent of the portfolio that is sold and then rebought during a rebalancing event.
The average turnover per year is the sum of turnover percentages across all rebalancings divided by the number of years in the backtest, assuming there are 252 trading days in a year.
Each row of the "Rebalancing Events" table represents a rebalancing event and shows the percent allocations of tickers at the end of the trading day but before the rebalancing actually occurs.
Each row of the "Cashflows" table shows an individual cashflow event, including its date, sign (deposit or withdrawal), amount, cumulative cashflows for that portfolio, and total balance after the cashflow.

Regression:

The Regression tab regresses one portfolio's historical returns against one or more other portfolios using daily, monthly, or annual returns from the completed backtest.
Inputs:
Return Frequency chooses daily, monthly, or annual returns.
Dependant Portfolio (Y) is the portfolio being explained by the regression.
Independent Portfolios (X) are the portfolios used to explain Y.
Include intercept toggles whether the regression includes a constant term.
The Conditional Scatter controls let you choose which X variable to plot on the x-axis and how to hold the other X variables constant.
Monthly and annual regressions exclude incomplete first and last periods, matching the return statistics tables.
Outputs include a model summary (Dependent Portfolio, Observations, R², Adj. R², RMSE, MAE), coefficient estimates (Coefficient, Std. Err., t-stat, p-value, and 95% Confidence Interval), an Actual vs Fitted chart, a Residuals chart, and a Conditional Scatter plot.

Glidepath Portfolios:

A glidepath combines 2-4 existing portfolios and specifies allocation anchors (Start/End are implicit; interior anchors require dates). Weights summing to 100% for every anchor is also required. Up to 15 anchors are allowed.
Allocations are interpolated linearly between anchors on trading days and rebalanced daily (between portfolios) at the glide layer to those targets.
Results show two allocation charts for glidepaths: by Portfolio and by Ticker (CASHX/TBILL are shown as CASH). Rebalancing stats/events are hidden for glidepaths.
Asset Analyzer
Formatting:
Tickers must be space-delimited, and the maximum number of tickers you can analyze at the same time is 5.
Note that all tickers are assumed to represent prices in the same currency. If you mix and match different tickers that are traded in different currencies, you will get inaccurate results.

Methodology:
Assets are invested on the close of the specified start date. If a start date is not specified, historical data going as far back as possible is used.
The total return profiles, i.e. assuming all distributions are reinvested, of assets are used for all calculations.
Checking the "Adjust for inflation" adjusts every dollar amount in the backtest for inflation to the start date.
In other words, if an analysis starts in 1970 and ends in 2024, and the analysis is adjusted for inflation, all dollar values will be in 1970 dollars, not 2024 dollars.

Statistics:
Pearson correlations are calculated using daily returns over the specified time period.
Sharpe and Sortino ratios are calculated ex-post with excess daily returns and volatility, using TBILL as the risk-free asset, then annualized. The mean daily excess return is found by taking the arithmetic mean of realized daily excess returns over the entire time period.
Rolling Skewness measures the asymmetry of daily return distribution within each rolling window (0 ≈ symmetric) on the Rolling tab.
Rolling Kurtosis is excess kurtosis of daily returns within each rolling window (0 ≈ normal; fat tails > 0) on the Rolling tab.
Rolling Full Kelly is the optimal daily leverage to maximize CAGR with borrowing at the T-bill rate; computed per window.
The Ulcer Index is an alternative measure of risk that uses the magnitude and duration of drawdown rather than volatility. More information can be found here.
Avg Drawdown is the average drawdown depth across all days when the asset is below an all time high.
Longest Drawdown is the longest consecutive time the asset spends below an all time high.
Beta measures the asset's beta against the selected benchmark (SPYSIM by default) using daily returns.
Cumulative Return is the cumulative return over the analysis period (ending value divided by starting value minus 1).
Nominal Ending Value shows the ending balance in nominal dollars when inflation adjustment is enabled. Only the final balance is converted back to nominal terms; cashflows and all other statistics remain inflation adjusted.
Correlations are calculated based on daily returns. The correlation matrix depicts asset correlations over the entire analysis period.
Annual returns are calculated from the closing value of the portfolio on the last trading day of each year.
Monthly returns are calculated from the closing value of the portfolio on the last trading day of each month.
Return Required to Recover (RRTR) Chart: This chart shows the inverse of the drawdown chart, displaying the return required to recover from a drawdown. For example:
A 1.25x RRTR corresponds to 25% return required to recover, which occurs when the drawdown is 20%
A 50% drawdown requires a 2x (100%) return to recover
A 90% drawdown requires a 10x (900%) return to recover
A 99% drawdown requires a 100x (9900%) return to recover
Monte Carlo Portfolio Simulator
For a full walkthrough, use the Monte Carlo Portfolio Simulator guide.

What the tool does:
Monte Carlo Portfolio Simulator resamples aligned historical market data with block-bootstrap sampling to generate many possible portfolio paths instead of replaying one fixed historical sequence.
In compare mode, it can run two portfolios on those same sampled paths so you can inspect paired Portfolio 1, Portfolio 2, Difference, and Ratio views.
It is designed to study outcome ranges, path dependence, sequence risk, optional contributions or withdrawals, and how rebalancing interacts with different sampled return orders.

Inputs and sampling rules:
The date range is first clamped to the overlapping history shared by the selected tickers and required auxiliary series such as inflation and T-bills.
Simulations use synthetic time, not real calendar dates. 1 year = 252 trading days.
Number of years is rounded up to the next quarter year before the simulation runs.
Min block and max block are entered in years, then converted to trading-day block lengths internally.
With replacement samples one contiguous block at a time and allows the same historical block to appear multiple times in one simulation.
Without replacement partitions the sampled history into blocks, shuffles those blocks, uses them once, and starts a new pass only if more days are needed to fill the target horizon.
The random seed controls reproducibility. The same inputs and the same seed will reproduce the same simulation results.
In two-portfolio mode, the union of both portfolios' tickers is aligned and clamped first, and only then are the two portfolios constructed from that shared history.

Portfolio, rebalancing, and cashflows:
The portfolio uses the same allocation, drag, dividend, and rebalancing-style inputs as the other portfolio tools.
Rebalancing and cashflow schedules are synthetic trading-day schedules rather than calendar schedules. For example, monthly is treated as every 21 trading days and yearly is every 252 trading days.
Cashflow mode can be no cashflows, fixed contributions, or fixed withdrawals.
If inflation-adjusted cashflows is enabled, the actual simulated cashflow amount grows with the sampled inflation path.
Rebalance offset is fixed at 0 in Monte Carlo, so scheduled rebalances happen at the end of each synthetic period.

How the simulation is evaluated:
Each sampled path is run through the portfolio engine with rebalancing and cashflows, then summarized into per-simulation metrics such as Ending Value, CAGR, Max Drawdown, Avg Drawdown, Longest Drawdown, Volatility, Sharpe, Sortino, Calmar, Ulcer Index, and UPI.
Inflation-adjusted versions of those metrics are also calculated and can be viewed separately in the Summary, Distribution, and Scenario views.
SWR and PWR are always calculated from the full-horizon inflation-adjusted no-cashflow path for each simulation, so they do not depend on the configured cashflows.
Scenario tabs such as Best, percentiles, Median, and Worst are chosen by nominal ending value. Inflation-adjusted scenario views use the same sampled scenarios, but display inflation-adjusted numbers for those specific runs.
Compare mode adds paired Difference and Ratio outputs in the Summary and Distribution views. Because both portfolios share the same sampled paths, those comparisons are simulation-by-simulation rather than two unrelated Monte Carlo runs.

Results and interpretation:
Summary includes a transposed distribution-statistics table, a Portfolio Value Range chart, and Portfolio Success charts.
The Portfolio Value Range chart shows monthly cross-simulation curves for min, max, and selected percentiles of portfolio value.
Portfolio Success can be defined three ways:
Survival: portfolio value > 0
Preservation: portfolio value >= starting value
Profit: portfolio value > net capital invested, where net capital invested = starting value + contributions - withdrawals
Inflation-adjusted Preservation and Profit lines compare outcomes to inflation-adjusted thresholds, not just nominal thresholds.
Distributions shows histograms and percentile statistics for each metric.
Scenarios shows representative daily paths and a performance table for selected nominal-ending-value scenarios.
Portfolio Optimizer
Formatting:
Tickers must be space-delimited, with a maximum of 5 tickers allowed.
Note that invalid tickers can be used. For any invalid ticker, you must manually provide assumptions for its CAGR, volatility, and correlations with the other assets.
If you would like to use historical CAGR, volatility, and correlations for valid tickers, check the “Use Historical Values” box. The info icon next to the checkbox will have information about the effective date range of the retrieved values and the limiting ticker.
If you want to provide minimum or maximum exposure constraints for any asset, check the “Exposure Limits” box and fill out the corresponding table.
Any cells left blank in that table will be treated as unconstrained (0% for minimums and inf for maximums).
Any inputs that have a gray background will use the placeholder value (denoted in light text) upon optimization. Type your desired value in the input to override the placeholder.

Optimization Assumptions:

The provided volatility values should be interpreted as annualized daily volatilities.
The provided correlation values should be interpreted as Pearson correlations of daily returns.
The portfolio is assumed to be rebalanced on a daily basis.
Short positions (leverage below 0) and negative exposures to assets are not considered in the optimization search.
For leverage above 1, the annual leverage cost, per additional unit of leverage, is assumed to be the average T-bill rate plus 1%. The extra 1% accounts for typical borrowing costs (approximately 0.5% above the risk-free rate) and other expenses (e.g., 3x leveraged ETFs often have about a 1% expense ratio, which translates to 0.5% per unit of leverage).
For leverage below 1, the uninvested portion (i.e., the cash or T-bill allocation) is assumed to earn the average T-bill rate annually.
When the optimization method is based on risk parity, the unleveraged portfolio weights are first calculated to achieve risk parity among the included assets. Then, the optimal leverage factor is determined to best meet the specified objective.

Optimization Methodology:
The optimization algorithm can calculate the CAGR and volatility of any unleveraged portfolio (rebalanced daily) given asset weights and the assumed asset-level CAGRs, volatilities, and pairwise correlations. In these calculations, we incorporate “Shannon's Demon” (the rebalancing bonus) when estimating portfolio CAGR. The portfolio volatility is derived from the asset weights (which are constant since we assume daily rebalancing), volatilities of the underlying assets and their correlations.
After determining the unleveraged portfolio's characteristics, we extend these to leveraged portfolios. For leverage greater than 1, we account for borrowing costs and the impact of volatility decay. For leverage less than 1, we factor in the returns on any leftover cash (at the T-bill rate), as well as the “volatility bonus” from rebalancing with cash daily. We then use these leveraged CAGR and volatility estimates, along with the T-bill rate, to form an objective function (e.g., maximizing CAGR or Sharpe ratio, minimizing volatility, etc.). We employ a numerical optimization algorithm (via the scipy package's minimize function) to search within the feasible space defined by your constraints for the portfolio that best meets the chosen objective.
Note: Because this is a numerical optimization with a stopping criterion, the solution found is a very good approximation of the true optimal solution. In cases where the objective function may be flat across certain regions, the reported solution could be one of several equally optimal choices.

Statistics:
The optimal portfolio composition is presented in a table, showing the following:
Weights: The fraction of the portfolio allocated to each asset (unleveraged).
Leverage: The overall leverage factor applied to each asset (same across all assets by design).
Exposure: Calculated as weight X leverage for each asset. Summed across all assets (including any T-bill allocation), total exposure equals 100%. Note that T-bill exposure can be negative to indicate borrowing.

The optimal portfolio stats contains the expected CAGR, expected volatility, and expected Sharpe ratio for the optimal portfolio found by the optimization algorithm.
Backtest Optimizer
Goal:
The Backtest Optimizer searches for portfolio weights that would have performed best over a historical period, given your rebalancing rules, cashflows, and constraints. This is useful for exploring “what would have been optimal,” but keep in mind that using history directly can lead to overfitting.

Inputs:
Tickers (space-delimited): the assets the optimizer can allocate to.
Start Date / End Date: the historical window to optimize over. Leave blank to use all overlapping data across tickers.
Starting Value: used for dollar-denominated outputs (like ending value) and for end-value objectives when cashflows are present.
Adjust for inflation (checkbox): indexes dollars/returns to the US CPI.
Rolling Window: controls the window length (months) used for rolling charts/tables when a backtest is run on the optimized portfolio. Not used in the optimization itself.
Rebalance frequency and Offset: defines how often the portfolio rebalances, and when within each period rebalancing occurs.
Rebalance bands (checkbox): enables additional rebalance triggers when weights drift. If enabled:
Abs. ∆: absolute drift threshold.
Rel. ∆: relative drift threshold.
Add cashflows (checkbox): if enabled, applies recurring contributions/withdrawals during the window. If enabled:
Cashflow: dollar amount (+ or -).
Cashflow Frequency: how often it occurs.
Offset: when within each cashflow period it occurs.
Objective: choose what the optimizer should maximize/minimize (examples include CAGR, Sharpe/Sortino, and drawdown-based metrics).
Solver: selects the optimization method (GA/DE/PSO).
Solve speed: trades off speed vs search thoroughness by changing solver settings (faster runs do fewer evaluations).
Constraints: optional restrictions/guardrails. Leaving an input blank means it is not enforced. Available inputs include:
Max holdings: maximum number of tickers with a non-zero allocation.
Min weight to include: if a ticker is included, it must be at least this weight.
Min CAGR, Min Sharpe, Min Sortino, Min UPI, Min Calmar: minimum acceptable performance constraints.
Max vol, Max Max DD, Max Avg DD, Max Ulcer Index: maximum acceptable risk constraints.
Weight limits (checkbox): enables a per-ticker min/max weight table. Empty cells are treated as unconstrained.

Methodology:
The optimizer evaluates many candidate portfolios by running a historical simulation using the same backtest engine used elsewhere in Testfolio. It then uses a numerical search algorithm to improve candidate weights while enforcing your constraints. Because this is a heuristic search with a stopping criterion, the result is typically a very good approximation of the best solution found under the chosen settings.

Results:
The output includes:
A table of optimal weights (percent allocations) for the selected tickers.
A set of portfolio metrics for the optimized portfolio.
A Backtest of the optimized portfolio and the individual tickers used in the inputs.
Efficient Frontier
Goal:
The Efficient Frontier tool generates a set of historically-tested portfolios that trade off return vs risk (a Pareto front). You choose how to measure “risk” (volatility, drawdown, ulcer index, etc.), and the tool returns multiple optimized portfolios across that spectrum.

Inputs:
Tickers (space-delimited): the assets the solver can allocate to.
Start Date / End Date: the historical window to build the frontier over. Leave blank to use all overlapping data across tickers.
Adjust for inflation (checkbox): indexes dollars/returns to the US CPI.
Rebalance frequency and Offset: defines how often the portfolio rebalances, and when within each period rebalancing occurs.
Rebalance bands (checkbox): enables additional rebalance triggers when weights drift. If enabled:
Abs. ∆: absolute drift threshold.
Rel. ∆: relative drift threshold.
Allow Cash Allocation (checkbox): optionally runs an additional “cash overlay” frontier that includes CASHX. If enabled:
Allow leverage (checkbox): allows CASHX to be negative (borrowing) in the overlay run.
Borrow spread: extra annual borrowing cost above CASHX when CASHX is negative.
Max leverage: caps leverage by limiting how negative CASHX can be.
Return objective: currently maximize CAGR.
Risk objective: choose one risk metric to minimize: volatility, max drawdown, average drawdown, or ulcer index.
Solver: selects the optimization method (currently NSGA2).
Solve speed: trades off speed vs search thoroughness (faster runs do fewer evaluations).
Constraints: optional restrictions on the search space:
Max holdings: maximum number of tickers with a non-zero allocation.
Min weight to include: if a ticker is included, it must be at least this weight.
Weight limits (checkbox): enables a per-ticker min/max weight table. Empty cells are treated as unconstrained.

Methodology:
The solver evaluates many candidate portfolios by running historical simulations under your rebalancing rules. Instead of returning a single “best” portfolio, it solves a two-objective problem:
Maximize return (CAGR)
Minimize the selected risk metric
The result is a set of nondominated portfolios that form the efficient frontier.

Results:
The output includes:
An Efficient Frontier plot (risk on x-axis, return on y-axis) with selectable points. A “knee” portfolio is highlighted by default.
A Selected Portfolio section with:
Weights (allocations) for the selected point
Portfolio metrics (return, risk, and risk-adjusted stats)
An allocation vs risk chart showing how the portfolio mix changes across the frontier.
A Correlation Matrix of the input assets (based on daily returns over the selected period).
Tactical Allocation
Formatting:

Tickers must be accompanied by a corresponding percentage within the allocation, which can be negative. Otherwise, it will be ignored. To perform a backtest, the percentages in an allocation need to add up to 100%.
Tactical also has an Optimize mode that chooses daily long-only weights from candidate tickers inside each allocation. Tactical Grid Search supports Backtest mode only and does not run Optimize mode.
Note that all tickers are assumed to represent prices in the same currency. If you mix and match different tickers that are traded in different currencies, you will get inaccurate results.

Methodology:

Signals:
Signals act as boolean masks that are always true or false on the close of any given trading day.
Signals are created by comparing the values of two indicators. Note that there are limitations on which indicators can be compared (e.g. RSI can't be compared to a ticker's price).
The SMA indicator is a simple moving average of the prices of the specified ticker in the lookback period.
The EMA indicator is an exponential moving average of the prices of the specified ticker in the lookback period with a decay factor of 2 / (lookback + 1).
The Price indicator is the price of the specified ticker on the close of the current day.
The Return indicator is the percent change in the price of the specified ticker from lookback to the current day.
The CAGR indicator is the annualized version of the Return indicator, using (1 + return)^(252 / lookback) - 1.
The CMGR indicator is the monthly equivalent version of the Return indicator, using (1 + return)^(21 / lookback) - 1.
The Volatility indicator is the annualized standard deviation of daily returns of the specified ticker in the lookback period.
The Drawdown indicator is the magnitude of the percent drawdown of the specified ticker.
The RSI indicator is the relative strength index of the specified ticker over the lookback period. The average up and down close changes are calculated using an exponential moving average with a decay factor of 1 / lookback. Lookback periods of no up changes, no down changes, or all flat changes are assigned RSI values of 0, 100, and 50 respectively.
The Win Rate indicator is the percentage of positive daily returns over the lookback period.
The Correlation indicator is the correlation between daily returns of two tickers over the lookback window.
The VIX indicator is the CBOE Volatility Index.
The VIX3M indicator is the CBOE S&P 500 3-Month Volatility Index.
The T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y indicators are Treasury yields as percentages.
The Month indicator is the month number on any given trading day. For example, on August 1st, it would output 8, while on March 15th, it would output 3.
The Day of Week indicator is the day of the week as a number, on any given trading day. For example, on Monday, it would output 1, while on Thursday, it would output 4.
The Day of Month indicator is the day number within the month, on any given trading day. For example, on August 1st, the day of month indicator would output 1, while on March 15th, it would output 15.
The Day of Year indicator is the day number within the year, on any given trading day. For example, on January 1st, the day of year indicator would output 1, while on December 31st, it would output 365 (or 366 in a leap year).
The Threshold indicator simply outputs a constant value that you specify. This is used to set absolute thresholds to compare with other indicators, i.e. volatility above 15%, RSI below 50, etc.
The delay parameter can be applied to each indicator individually to shift the data series forward. For example, while normally the 200 day SMA indicator would output the average close price from 199 days ago to today, a delay parameter of 3 would cause it to output the average close price from 202 days ago to 3 days ago. Another way of thinking about this is that a delay of 3 would cause any indicator to output its value from 3 days ago rather than today's value.
Negative delays work the same way but in reverse. A delay of -3 would cause any indicator to output its value from 3 days in the future rather than today's value. Make sure you know what you're doing when you use them, since you're allowing your strategy to see the future!
The tolerance parameter allows an amount of deviation to be tolerated without the signal switching from true to false or from false to true. For percent-based indicators (Return, Volatility, Drawdown, Win Rate, VIX, VIX3M, and all Treasury yield indicators), the tolerance is in absolute terms. For all other indicators, tolerance is in relative terms. Setting a tolerance value reduces signal whipsawing (i.e. switching between true and false) when the first indicator is very close to the second indicator. Larger tolerance values are a tradeoff between less whipsawing and increased lag.
When using the equal comparator, the tolerance value creates a range around the second indicator where the first indicator is considered equal. For example, given a tolerance of 1%, SPYSIM's volatility as the first indicator, and a 14% threshold as the second indicator, the signal will be true when SPYSIM's volatility is between 13% and 15%, and false otherwise.
When using the less/greater comparators, the tolerance value creates a "buffer" around the second indicator that the first indicator must pass fully before switching between true and false.
For example, consider this series of stock prices: 100, 110, 108, 100, 115, 130, 115.
The 3 day SMA would be, starting from the third day: 106, 106, 107.67, 115, 120.
A "Price > 3 day SMA" signal on this stock would output True, False, True, True, False.
The same signal but with a 5% tolerance would output True, False, True, True, True. Note that the last day does not switch to False since the price needed to be less than 120 * 0.95 = 114 to do so. On the other hand, switches do occur on the fourth and fifth days since the price movements are large enough to bypass the buffer zone.
Derived signals follow the same logic as regular signals but allow you to specify an operation between two indicators and compare the result to a fixed threshold for more flexibility.
Allocations:
Each allocation has its own internal rebalancing settings. By default, allocations rebalance daily. You can also choose a less frequent schedule and/or rebalance bands.
With daily allocation rebalancing, the allocation is reset to its target ticker weights every trading day. With non-daily rebalancing or rebalance bands, the underlying ticker weights are allowed to drift between rebalances and are only reset when a scheduled or band-triggered rebalance occurs. Non-daily allocation rebalancing uses a more computationally expensive engine and is only available to Pro/Pro+ users.
Allocation conditions are evaluated as true or false at the close of each trading day. When the strategy switches into an allocation, that allocation starts from its target ticker weights at entry.
Inverting a signal changes all days on which the signal is true to false, and vice versa. For example, if a signal "Price > SMA" is true when the stock is above its 200 SMA, inverting that signal will make it true when the stock is below its 200 SMA instead.
Conditions are evaluated as a sum of products, i.e. an OR of ANDs. In other words, ANDs take precedence over ORs. You can use various calculators online to convert arbitrary boolean expressions into a sum of products.
The order in which you specify allocations is important: the leftmost allocations take precedence, so if the conditions for two allocations are both true on a given day, only the leftmost allocation will be invested in.
Ranked allocations let you rank a universe of tickers inside a single allocation and invest in the winners rather than specifying fixed weights up front.
Each ranked row can use a separate Rank On ticker and Invest In ticker. This allows you to rank one asset but invest through a different vehicle, such as a leveraged ETF or an alternate proxy.
The ranking metric can be Total Return, Volatility, Price / SMA, or RSI. Rankings can use one lookback or the equal average of multiple lookbacks.
You can choose whether to pick from the Top or Bottom of the ranked universe, and ranked allocations support a separate Evaluate Ranking schedule from the allocation’s own rebalance schedule.
If thresholding is enabled, only tickers whose score is above or below a specified threshold are eligible. If fewer tickers satisfy the threshold than the number you pick, the allocation invests only in the qualifying names. If none qualify, the allocation invests in the specified fallback ticker instead.
Winner weights can be assigned using Equal Weight, Inverse Volatility, or Inverse Variance. The inverse-volatility-based methods use the trailing volatility of the selected Invest In tickers over the chosen volatility lookback.
Ranked allocations are reevaluated throughout history on their ranking schedule, even while inactive. When the strategy enters a ranked allocation, it can reevaluate again on the entry date before subsequent trading and reporting continue from that updated ranked state.
Evaluate Ranking controls when the winners are recomputed. The allocation’s own Rebalance setting controls when those current winners are reset back to target weights. The strategy-level Trading Frequency is separate again: it determines when the overall strategy is allowed to switch between allocations. So a ranked allocation can keep the same selected names between evaluation dates, rebalance those names on a different schedule, and still only become active when the broader strategy is allowed to trade into it.
All allocations and signals assume dividends are reinvested, i.e. the total return of tickers is used.
The strategy is invested on the close of the specified start date. If a start date is not specified, historical data going as far back as possible is used.
The trading frequency parameter determines how often the strategy is allowed to switch between allocations. This is separate from each allocation's own internal rebalancing settings. A trading frequency of "Weekly", for example, means that any allocation switches, if needed, will occur on the last trading day of the week (or earlier if an offset is specified). The default is "Daily", meaning that switches occur as soon as the conditions change.
Benchmark picker: if left unchecked, SPYSIM is used as the benchmark. If checked, your selected ticker is used instead for benchmark-based metrics and is also included as an additional benchmark result row.
For trading costs, switches assume 100% turnover for the entire allocation.
Saved strategies are stored in your browser's localStorage. No saved data ever reaches our servers.

Statistics:

Sharpe and Sortino ratios are calculated ex-post with excess daily returns and volatility, using TBILL as the risk-free asset, then annualized.
The mean daily excess return is found by taking the arithmetic mean of realized daily excess returns over the entire time period.
The Excess CAGR rolling metric is NOT the same excess return used to calculate the rolling Sharpe ratio; it is simply the portfolio's CAGR minus TBILL CAGR over the time period.
Rolling Skewness measures the asymmetry of daily return distribution within each rolling window (0 ≈ symmetric).
Rolling Kurtosis is excess kurtosis of daily returns within each rolling window (0 ≈ normal; fat tails > 0).
Rolling Full Kelly is the optimal daily leverage to maximize CAGR with borrowing at the T-bill rate; computed per window.
The Ulcer Index is an alternative measure of risk that uses the magnitude and duration of drawdown rather than volatility. More information can be found here.
Avg Drawdown is the average drawdown depth across all days when the strategy is below an all time high.
Longest Drawdown is the longest consecutive time the strategy spends below an all time high.
The Calmar Ratio measures risk-adjusted returns by dividing CAGR by the absolute value of maximum drawdown. Higher values indicate better risk-adjusted performance.
Other Risk and Return Metrics:
Downside Deviation: standard deviation-like risk measure that only uses negative returns: sqrt(mean(min(0, r)^2)). It is reported for daily/monthly/annual returns, and annualized variants are scaled by sqrt(252) (daily) or sqrt(12) (monthly).
Benchmark Correlation: Pearson correlation between portfolio daily returns and selected benchmark daily returns (SPYSIM by default) over overlapping dates.
Beta: daily-return beta vs selected benchmark (SPYSIM by default), computed from return covariance/volatility relationship.
Alpha (daily / annualized): CAPM alpha using daily excess returns: (r_p - r_f) - beta * (r_m - r_f), with TBILL as r_f; annualized alpha is daily alpha × 252.
Upside Capture Ratio: portfolio return vs benchmark return using only periods where benchmark return is positive; 100 means matching benchmark upside capture.
Downside Capture Ratio: same concept as upside capture, but only for periods where benchmark return is negative.
Capture Spread: Upside Capture Ratio minus Downside Capture Ratio (reported for daily/monthly/annual variants). Higher values indicate stronger upside participation relative to downside participation vs benchmark.
Active Return: annualized portfolio return minus annualized benchmark return over the same aligned dates.
Tracking Error: annualized standard deviation of daily active returns (r_p - r_m).
Information Ratio: Active Return divided by Tracking Error.
Modigliani–Modigliani Measure (M²): Sharpe ratio translated into return units: rf + Sharpe * benchmark_vol, reported as an annualized percent metric.
Value at Risk (VaR): empirical left-tail percentile cutoff of returns (shown at 1%, 5%, and 10% for daily/monthly/annual returns).
Conditional Value at Risk (CVaR): average return of observations in the VaR tail (returns less than or equal to the VaR threshold).
Average Gain: arithmetic mean of returns conditional on returns being positive.
Average Loss: arithmetic mean of returns conditional on returns being negative.
Gain/Loss Ratio: Average Gain divided by absolute value of Average Loss.
Beta measures the portfolio's beta against the selected benchmark (SPYSIM by default) using daily returns.
Cumulative Return is the cumulative return over the backtest period (ending value divided by starting value minus 1).
Seasonality charts show the average annual cumulative return path for each portfolio, aligned by calendar days.
Annual returns are calculated from the closing value of the portfolio on the last trading day of each year.
Monthly returns are calculated from the closing value of the portfolio on the last trading day of each month.
Return Required to Recover (RRTR) Chart: This chart shows the inverse of the drawdown chart, displaying the return required to recover from a drawdown. For example:
A 1.25x RRTR corresponds to 25% return required to recover, which occurs when the drawdown is 20%
A 50% drawdown requires a 2x (100%) return to recover
A 90% drawdown requires a 10x (900%) return to recover
A 99% drawdown requires a 100x (990%) return to recover
Safe Withdrawal Survival Analysis:
w% Port. Surv. Rate: % of N-year rolling windows where daily, inflation-adjusted withdrawals at an annual rate of w% never deplete the portfolio.
w% SCTM (Survival-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across those windows where daily, inflation-adjusted withdrawals at an annual rate of w% keep the portfolio > 0.
Perpetual Withdrawal Preservation Analysis:
w% Port. Pres. Rate: % of N-year rolling windows where daily, inflation-adjusted withdrawals at an annual rate of w% end with terminal wealth ≥ initial portfolio.
w% PCTM (Preservation-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across those windows where daily, inflation-adjusted withdrawals at an annual rate of w% preserve or grow starting capital.
Safe Withdrawal Rate Analysis:
p% Surv. SWR: the annual withdrawal rate (daily, inflation-adjusted) w% such that at least p% of N-year rolling windows never deplete the portfolio.
p% SCTM (Survival-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across windows that survive when withdrawing daily (inflation-adjusted) at w% = p% Surv. SWR.
Perpetual Withdrawal Rate Analysis:
p% Pres. PWR: the annual withdrawal rate (daily, inflation-adjusted) w% such that at least p% of N-year rolling windows end with terminal wealth ≥ initial.
p% PCTM (Preservation-Conditional Terminal Multiple): average terminal wealth multiple—relative to the initial portfolio—across windows that preserve or grow capital when withdrawing daily (inflation-adjusted) at w% = p% Pres. PWR.
Extended Withdrawal Stats (Curves):
When enabled, the Withdrawal Stats tab includes a Curves view that shows SWR and PWR across retirement lengths (x-axis is retirement length in years; y-axis is annual withdrawal rate).
Extended withdrawal stats: enables the curve calculations and includes them in the results response.
Projection:
No projection: only windows fully contained in the available historical data are included.
Use portfolio long-term CAGR: when a window extends past the end of available history, the tail is extended using the portfolio’s long-term growth rate.
Loop around: when a window extends past the end of available history, the tail is extended by continuing from the beginning of the backtest history.
Min real years: minimum amount of real historical data that must be present within each window before projection is used.
Tactical Grid Search
Goal:
Tactical Grid Search runs many Tactical combinations and returns a compact, metrics-only comparison view.

How to use:
Build a base strategy exactly like Tactical (signals, derived signals, allocations, dates, and trading frequency).
Define variables in the Variables card. The first filled variable is X (columns), second is Y (rows), third is Z (tabs/panels). Additional variables are fixed single values.
Put variable symbols into supported fields (for example lookbacks, delays, thresholds, tolerances, and allocation tickers). Variables are not supported in allocation weights.
Run Backtest to evaluate all combinations on one unified common date window.

Output:
Results header shows the effective date range used across evaluated combinations.
Up to three grid tables are shown at once, each with a selectable metric.
Cell colors are metric-relative (green = better, red = worse), with best/worst cells outlined.
If a third variable exists, each value appears as its own tab/panel.
Clicking a cell selects that combination and populates the Selected Variables and Selected Strategy Metrics cards below the grids.
Use Load in Tactical to open the selected combination directly in Tactical for full charts and detailed outputs.
Rebalancing Sensitivity
Goal:
Rebalancing Sensitivity tests one fixed-allocation portfolio across all supported rebalancing schedules and offsets, then compares the outcomes.

Inputs:
The portfolio must have at least two tickers with non-zero weights. Allocations must sum to exactly 100%.
Start and end dates are optional. If left blank, the tool uses full available history and then clamps to the effective overlapping window across all portfolio tickers.
Drag, total return, and inflation adjustment settings work the same way as in Portfolio Backtester.

Schedules tested:
Daily, weekly, monthly, bimonthly, quarterly, every 4 months, semiannually, and yearly.
Each frequency is evaluated across all valid offsets for that frequency.
Offsets indicate how many trading days before period-end a rebalance occurs for each tested schedule:
Offset = 0: Rebalancing occurs on the last trading day of the period (default)
Offset = 1: Rebalancing occurs on the second-to-last trading day of the period
Offset = 2: Rebalancing occurs on the third-to-last trading day of the period
Offset = n: Rebalancing occurs on the (n+1)-to-last trading day of the period

Output:
Results include a unified effective date range and one row per schedule/offset combination.
Metrics include CAGR, volatility, max drawdown, average drawdown, Sharpe, Sortino, Calmar, Ulcer Index, and UPI.
Tabs provide scatter view, distributions, offset curves, and full tables by frequency.
Principal Component Analysis
Goal:
Principal Component Analysis identifies the orthogonal statistical components that explain the variance of a group of asset return series.

Inputs:
Tickers defines the asset universe to analyze.
Start Date and End Date define the analysis window.
Return Frequency chooses daily, monthly, or annual returns.
Return Matrix chooses correlation matrix or covariance matrix PCA.

Methodology:
The tool fetches all selected tickers, clamps them to overlapping history, aligns the daily series, and converts them to the selected return frequency.
Correlation-matrix PCA equalizes asset volatility before decomposition, while covariance-matrix PCA preserves raw volatility differences.
Monthly and annual runs exclude incomplete first and last periods, matching the filtering rules used elsewhere in the app.

Output:
Results include effective date range, limiting ticker, and a model summary with tickers, observations, first and last sample period, and return matrix.
Principal Component Portfolios report both raw eigenvector loadings and normalized component weights that sum to 100%.
Explained Variance reports variance explained and cumulative variance for each principal component.
Factor Regression
Goal:
Factor Regression regresses one backtested portfolio's excess returns against selected factor return series.

Inputs:
Start Date and End Date define the analysis window.
Return Frequency chooses daily, monthly, or annual returns.
Risk-free rate source is subtracted from portfolio returns to form the dependent excess-return series.
Factors selects one or more factor return series from the supported Fama French, AQR, q-Factors sets, and fixed income factors.
Pro and Pro+ users can also add custom factors defined as a raw ticker return, a ticker return minus the selected risk-free rate, or a ticker return minus another ticker.
Portfolio uses the same backtest-style portfolio definition inputs for tickers, weights, dividends, drag, and rebalancing assumptions.

Methodology:
The tool fetches portfolio, factor, and risk-free series, then clamps them to their overlapping history before converting them to the selected return frequency.
The regression is run on portfolio excess returns, with the chosen risk-free source subtracted from portfolio returns.
Custom factors are built from the same clamped and aligned return sample as preset factors, then included in the same regression matrix.
Monthly and annual regressions exclude incomplete first and last periods.

Output:
Results include a model summary with Portfolio, Risk-free rate source, Observations, first and last sample period, R², Adj. R², RMSE, MAE, Regression F statistic, Breusch-Godfrey autocorrelation results, and Breusch-Pagan heteroscedasticity results.
The coefficient table reports factor labels, descriptions, loadings, standard errors, t-stats, p-values, 95% confidence intervals, factor premia, portfolio factor returns, Alpha, and Annualized Alpha.
Charts include Actual vs Fitted Excess Returns and Residual Excess Returns.
LETF Analysis
Goal:
LETF Analysis studies a synthetic leveraged ETF built from an underlying ticker, a selected daily leverage, an expense ratio, and a borrowing spread.

Inputs:
Date range presets provide quick windows such as full history, last N years, last N full years, and to-date since a chosen year.
Start Date and End Date can also be set explicitly. Leaving them blank uses all available history or the latest available date.
Starting Value is the initial portfolio value used for the performance comparison paths.
Underlying ticker is the base series used to build the 1x path, the selected LETF path, and the DCA shuffle study.
LETF daily leverage is the fixed daily leverage used to construct the synthetic LETF path.
LETF expense ratio is an annual expense ratio applied to the selected LETF. For leverage above 1x, costs are scaled when the tool compares other leverage levels.
Borrowing spread is an extra annual spread added on top of the financing rate for leverage above 1x.
# of shuffles for DCA controls how many shuffled return paths are used for the DCA outcome distribution.
DCA annual contributions are converted into an equal daily contribution schedule.
Contributions growth rate is an annual rate that is converted into a fixed daily increase per trading day for the DCA study.

Methodology:
The tool builds a synthetic fixed-leverage path from the underlying ticker, the selected daily leverage, the expense ratio, and the borrowing spread.
It also searches across fixed leverage levels to identify the leverage that maximizes CAGR over the selected backtest window.
For the DCA study, each shuffle breaks the underlying path into a random set of large blocks and reorders them.
This keeps the overall return the same but changes the sequence of returns through time.
The LETF path is then built from that shuffled underlying path, so the final CAGR is preserved while DCA ending values can vary materially depending on when gains and losses occur.

Output:
Summary compares the underlying, the selected LETF, and the fixed leverage that maximizes CAGR over the backtest window.
Leverage tradeoff charts show CAGR, volatility, drawdown, Sharpe, Sortino, Calmar, Ulcer Index, and UPI across evaluated fixed leverage levels.
Additional tabs isolate volatility decay and fee drag under related path assumptions.
The DCA tab reports a distribution of ending-value ratios across shuffled paths, plus representative scenario tabs for the real, best, median, percentile, and worst cases.
Lump Sum vs DCA
Goal:
Lump Sum vs DCA compares how a one-time investment and a staged investment plan perform over the same horizon across many rolling start dates.

Inputs:
Start and end dates are optional. If left blank, the tool uses full available history and clamps to the overlapping window across all required series.
Enter a starting value (minimum $100). This same amount is used for both methods.
Configure DCA cadence and horizon:
Daily: equal contributions every trading day.
Contribution Count: equal contributions evenly spaced across the horizon, including first and last day.
Horizon is specified in months and converted to trading-day windows.
Money on the side can be set to uninvested, T-bills, or another ticker while capital is waiting to be deployed.
Portfolio construction, drag, total return, rebalance frequency, offsets, and rebalance bands follow the same rules as Portfolio Backtester.
Optional drawdown filtering can split start dates by whether the source series (portfolio or S.P. 500) is within or deeper than a chosen drawdown threshold.

Methodology:
Ending values are measured at the end of the selected horizon (n months later), right after the last DCA contribution.
DCA contributions use equal amounts:
Daily cadence: contributions are invested each trading day.
Contribution Count cadence: contributions are evenly spaced from start to end, with the first on day one (same day as lump sum) and the last on the final trading day.
For each valid rolling start date, the tool builds one horizon window and computes:
Lump sum end value (full capital invested at the start).
DCA end value (equal staged contributions over the window).
The base portfolio total series uses the same portfolio backtesting pipeline and date alignment approach used in Portfolio Backtester.
The tool reports both full-sample results and (when enabled) drawdown-filtered subsets.

Output:
Summary stats for five series:
LS End Value: Ending value of the lump sum investment.
DCA End Value: Ending value of the DCA investments.
LS - DCA: Difference between the ending values of the lump sum investment and DCA investments.
LS / DCA: Ratio between the ending value of the lump sum investment and DCA investments.
DCA / LS: Ratio between the ending value of DCA investments and the lump sum investment.
Stats include percentiles, mean, standard deviation, win rate, and conditional mean win/loss.
Distribution tabs show histograms and per-series summary tables for all starts and any enabled drawdown regimes.
Signal Analyzer
Formatting:

Dates & sampling
Pick a start/end date and a trading frequency with an optional offset.
Only dates within the overlapping trading‑day window are used.

Methodology:

Indicators
The SMA indicator is a simple moving average of the prices of the specified ticker in the lookback period.
The EMA indicator is an exponential moving average of the prices of the specified ticker in the lookback period with a decay factor of 2 / (lookback + 1).
The Price indicator is the price of the specified ticker on the close of the current day.
The Return indicator is the percent change in the price of the specified ticker from lookback to the current day.
The CAGR indicator is the annualized version of the Return indicator, using (1 + return)^(252 / lookback) - 1.
The CMGR indicator is the monthly equivalent version of the Return indicator, using (1 + return)^(21 / lookback) - 1.
The Volatility indicator is the annualized standard deviation of daily returns of the specified ticker in the lookback period.
The Drawdown indicator is the magnitude of the percent drawdown of the specified ticker.
The RSI indicator is the relative strength index of the specified ticker over the lookback period. The average up and down close changes are calculated using an exponential moving average with a decay factor of 1 / lookback. Lookback periods of no up changes, no down changes, or all flat changes are assigned RSI values of 0, 100, and 50 respectively.
The Win Rate indicator is the percentage of positive daily returns over the lookback period.
The Correlation indicator is the correlation between daily returns of two tickers over the lookback window.
The VIX indicator is the CBOE Volatility Index.
The VIX3M indicator is the CBOE S&P 500 3-Month Volatility Index.
The T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y indicators are Treasury yields as percentages.
The Month indicator is the month number on any given trading day. For example, on August 1st, it would output 8, while on March 15th, it would output 3.
The Day of Week indicator is the day of the week as a number, on any given trading day. For example, on Monday, it would output 1, while on Thursday, it would output 4.
The Day of Month indicator is the day number within the month, on any given trading day. For example, on August 1st, the day of month indicator would output 1, while on March 15th, it would output 15.
The Day of Year indicator is the day number within the year, on any given trading day. For example, on January 1st, the day of year indicator would output 1, while on December 31st, it would output 365 (or 366 in a leap year).
Signals
Constructed as: Left Indicator [Operation Right Indicator].
Allowed operations (selected by the tool):
Price/SMA/EMA: divide; right must be Price/SMA/EMA with the same ticker.
Return: none or subtract; subtract requires right Return with the same lookback.
Volatility: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
VIX/VIX3M: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
Drawdown: none or subtract; right is Drawdown.
RSI: none, subtract, or divide; right is RSI.
T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y (yields): none or subtract; right is any treasury yield in that set.
Calendar (Month, Day of Week/Month/Year): single‑series (no operation).
Delay: shifts the indicator in time. A positive delay uses a prior value (lags the series).
Forward metrics
Choose a ticker and one metric per analysis: Return, CAGR, Volatility, Mean Abs Return, or Win Rate.
Also choose a forward horizon N trading days:
Return: percent change over the next N trading days.
CAGR: annualized growth rate implied by the next N trading days.
Volatility: annualized volatility (standard deviation) of daily returns over the next N days. This will be the absolute value of the daily return if the horizon N = 1.
Mean Abs Return: average of absolute daily moves over the next N days (not annualized).
Win Rate: percent of days with positive returns over the next N days.
Alignment
All series are aligned to the sampling schedule and clamped to a common valid window. The scatter uses only dates where both x and y are valid.
Fits
Polynomial: in‑sample fit; displays R² for context.
Regressogram: piecewise‑constant by x‑bins; empty bins remain NaN and the step breaks across them.

Statistics & Results:

Fit summary tables
Polynomial: lists terms (Intercept, [Signal]^k) and their coefficients; includes R².
Regressogram: for each bin, shows [Signal] Range, Count, Proportion, and the forward metric value. For Return forwards, an accompanying Return CAGR column is shown (annualized from the N‑day return). The table title indicates the chosen statistic (Arithmetic, Compounded, or Median) and binning.
Binning
Uniform: equal‑width bins across the x‑range.
Quintile: equal‑frequency bins (similar counts per bin).
Custom: uses your interior edges; min/max auto‑included.
Statistics
Arithmetic mean: average of Y values in the bin.
Compounded mean:
For Return or CAGR: compounded mean of returns in the bin.
For Volatility: compounded volatility from stitched forward daily returns.
For Mean Abs Return or Win Rate: average of stitched forward daily returns; numerically identical to the arithmetic mean.
Median: 50th percentile of Y values in the bin.
Scatter plot
x = signal, y = forward metric; optional color/size encodings and invert toggles.
Best fit overlay: polynomial line or regressogram step.
Time series plots
Up to four charts: main signal, forward metric, and (if selected) color/size “New signal”.
Vertical cursor and x‑zoom are synchronized for inspection.
Dual Signal Analyzer
Formatting:

Dates & sampling
Pick a start/end date and a trading frequency with an optional offset. The analyzer samples both signals on the same schedule.
Only dates within the overlapping trading-day window across all tickers are used.

Methodology:

Indicators
The SMA indicator is a simple moving average of the prices of the specified ticker in the lookback period.
The EMA indicator is an exponential moving average of the prices of the specified ticker in the lookback period with a decay factor of 2 / (lookback + 1).
The Price indicator is the price of the specified ticker on the close of the current day.
The Return indicator is the percent change in the price of the specified ticker from lookback to the current day.
The CAGR indicator is the annualized version of the Return indicator, using (1 + return)^(252 / lookback) - 1.
The CMGR indicator is the monthly equivalent version of the Return indicator, using (1 + return)^(21 / lookback) - 1.
The Volatility indicator is the annualized standard deviation of daily returns of the specified ticker in the lookback period.
The Drawdown indicator is the magnitude of the percent drawdown of the specified ticker.
The RSI indicator is the relative strength index of the specified ticker over the lookback period. The average up and down close changes are calculated using an exponential moving average with a decay factor of 1 / lookback. Lookback periods of no up changes, no down changes, or all flat changes are assigned RSI values of 0, 100, and 50 respectively.
The Win Rate indicator is the percentage of positive daily returns over the lookback period.
The Correlation indicator is the correlation between daily returns of two tickers over the lookback window.
The VIX indicator is the CBOE Volatility Index.
The VIX3M indicator is the CBOE S&P 500 3-Month Volatility Index.
The T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y indicators are Treasury yields as percentages.
The Month indicator is the month number on any given trading day. For example, on August 1st, it would output 8, while on March 15th, it would output 3.
The Day of Week indicator is the day of the week as a number, on any given trading day. For example, on Monday, it would output 1, while on Thursday, it would output 4.
The Day of Month indicator is the day number within the month, on any given trading day. For example, on August 1st, the day of month indicator would output 1, while on March 15th, it would output 15.
The Day of Year indicator is the day number within the year, on any given trading day. For example, on January 1st, the day of year indicator would output 1, while on December 31st, it would output 365 (or 366 in a leap year).
Signals
Constructed as: Left Indicator [Operation Right Indicator].
Allowed operations (selected by the tool):
Price/SMA/EMA: divide; right must be Price/SMA/EMA with the same ticker.
Return: none or subtract; subtract requires right Return with the same lookback.
Volatility: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
VIX/VIX3M: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
Drawdown: none or subtract; right is Drawdown.
RSI: none, subtract, or divide; right is RSI.
T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y (yields): none or subtract; right is any treasury yield in that set.
Calendar (Month, Day of Week/Month/Year): single‑series (no operation).
Delay: shifts the indicator in time. A positive delay uses a prior value (lags the series).
The analyzer forms a 2D grid by binning Signal 1 along the X-axis and Signal 2 along the Y-axis.
Forward metrics
Choose up to three forward metrics: Return, CAGR, Volatility, Mean Abs Return, Win Rate. “None” disables an optional metric while keeping the common horizon.
Definitions:
Return: percent change over the next N trading days.
CAGR: annualized growth rate implied by the next N trading days.
Volatility: annualized volatility (standard deviation) of daily returns over the next N days. When N = 1, this equals the absolute value of the daily return.
Mean Abs Return: average of absolute daily moves over the next N days (not annualized).
Win Rate: percent of days with positive returns over the next N days.
Alignment
All series are aligned to the sampling schedule and clamped to a common valid window. The regressogram uses only dates where Signal 1, Signal 2, and the forward metric(s) are valid.

Best Fit (Regressogram):

Method
Regressograms partition the 2D signal space into bins and aggregate the forward metric per bin.
Binning options mirror the single-signal tool: Uniform, Quintile, or Custom edges for each axis. Custom uses interior edges (min/max auto‑included). Quintile edges are deduplicated to avoid zero‑width bins.
Statistics
Arithmetic mean: average of Y values per bin.
Compounded mean stitches forward daily returns within each bin before computing the metric:
For Return or CAGR: compounded mean of returns in the bin.
For Volatility: compounded volatility from stitched forward daily returns.
For Mean Abs Return or Win Rate: average of stitched forward daily returns; numerically identical to the arithmetic mean.
Median: 50th percentile per bin.
For Return metrics, an accompanying CAGR is derived from the compounded mean of returns (even when the statistic is Arithmetic or Median).
Empty bins remain NaN and are omitted from the heatmap; no tooltip is shown for empty bins.

Statistics & Results:

Best Fit Table displays bin ranges, counts, proportions, forward statistics, and derived CAGR when applicable. Padding is applied to extremely narrow observed ranges to keep bins visible while respecting bin edges.
2D Regressogram Chart mirrors the table using padded rectangles and hover tooltips summarizing all forward metrics per bin.
Time Series Plots chart Signal 1, Signal 2, and each forward metric over time. The vertical cursor and x‑axis zoom are synchronized for inspection.
Multi Signal Analyzer
Formatting:

Dates & sampling
Pick a start/end date and a trading frequency with an optional offset. All signals are sampled on the same schedule.
Only dates within the overlapping trading‑day window across all tickers are used. The Results header calls out any limiting ticker/signal.
Train/Test split
Data before the split date will be used for training, and data after this date will be used as a test set. Leave blank if you don't want a test set

Methodology:

Indicators
The SMA indicator is a simple moving average of the prices of the specified ticker in the lookback period.
The EMA indicator is an exponential moving average of the prices of the specified ticker in the lookback period with a decay factor of 2 / (lookback + 1).
The Price indicator is the price of the specified ticker on the close of the current day.
The Return indicator is the percent change in the price of the specified ticker from lookback to the current day.
The CAGR indicator is the annualized version of the Return indicator, using (1 + return)^(252 / lookback) - 1.
The CMGR indicator is the monthly equivalent version of the Return indicator, using (1 + return)^(21 / lookback) - 1.
The Volatility indicator is the annualized standard deviation of daily returns of the specified ticker in the lookback period.
The Drawdown indicator is the magnitude of the percent drawdown of the specified ticker.
The RSI indicator is the relative strength index of the specified ticker over the lookback period. The average up and down close changes are calculated using an exponential moving average with a decay factor of 1 / lookback. Lookback periods of no up changes, no down changes, or all flat changes are assigned RSI values of 0, 100, and 50 respectively.
The Win Rate indicator is the percentage of days with positive returns over the lookback window.
The Correlation indicator is the correlation between daily returns of two tickers over the lookback window.
The VIX indicator is the CBOE Volatility Index.
The VIX3M indicator is the CBOE S&P 500 3-Month Volatility Index.
The T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y indicators are Treasury yields as percentages.
The Month indicator is the month number on any given trading day. For example, on August 1st, it would output 8, while on March 15th, it would output 3.
The Day of Week indicator is the day of the week as a number, on any given trading day. For example, on Monday, it would output 1, while on Thursday, it would output 4.
The Day of Month indicator is the day number within the month, on any given trading day. For example, on August 1st, the day of month indicator would output 1, while on March 15th, it would output 15.
The Day of Year indicator is the day number within the year, on any given trading day. For example, on January 1st, the day of year indicator would output 1, while on December 31st, it would output 365 (or 366 in a leap year).
Signals
Constructed as: Left Indicator [Operation Right Indicator].
Allowed operations (selected by the tool):
Price/SMA/EMA: divide; right must be Price/SMA/EMA with the same ticker.
Return: none or subtract; subtract requires right Return with the same lookback.
Volatility: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
VIX/VIX3M: none, subtract, or divide; right is Volatility, VIX, or VIX3M.
Drawdown: none or subtract; right is Drawdown.
RSI: none, subtract, or divide; right is RSI.
T3M/T6M/T1Y/T2Y/T3Y/T5Y/T7Y/T10Y/T20Y/T30Y (yields): none or subtract; right is any treasury yield in that set.
Calendar (Month, Day of Week/Month/Year): single‑series (no operation).
Delay: shifts the indicator in time. A positive delay uses a prior value (lags the series).
The analyzer forms a 2D grid by binning Signal 1 along the X-axis and Signal 2 along the Y-axis.
Forward metrics
Choose up to three forward metrics: Return, Volatility, Mean Abs Return, Win Rate. “None” disables an optional metric from being used. Only the first forward meteric will be used to fit the tree. The others are for reporting purposes only.
Definitions:
Return: percent change over the next N trading days.
CAGR: annualized growth rate implied by the next N trading days.
Volatility: annualized volatility (standard deviation) of daily returns over the next N days. When N = 1, this equals the absolute value of the daily return.
Mean Abs Return: average of absolute daily moves over the next N days (not annualized).
Win Rate: percent of days with positive returns over the next N days.
Decision Tree Model
Criterion: MSE or MAE. Manual hyperparameters: Max leaves and/or Min leaf size %. Cross-validation supports grids for both and a time-ordered fold scheme.
Purge days (CV): excludes a gap (in days) around each validation fold to prevent leakage from overlapping forward windows.
Feature importance is impurity-based (no permutation).
Alignment
All series are aligned to the sampling schedule and clamped to a common valid window prior to model fitting.

Statistics & Results:

Model summary
Displays criterion, averaging mode, Max leaves, Min leaf size %, Training/Testing sample counts and date ranges.
Tree & Node Details
The tree shows split criteria per internal node and displays, per node, the Training proportion and forward metrics (for Return, nodes also show Return CAGR derived from the compounded mean when applicable).
Selecting a node reveals a details table with Train/Test Count, Proportion, and forward metrics (plus CAGR for Return).
Tree Table
Tabulates all leaves with Train/Test counts, proportions, forward metrics, and Return CAGR (if applicable), sorted by the primary forward.
Feature importance & Model metrics
Importance (impurity-based) and primary-forward model metrics (R², RMSE, MAE).
Calculator Suite
Stock ETF CAGR Calculator: estimates a stock ETF’s compound annual growth rate.
Input Investment years for the projection horizon.
Select Fundamentals type (Revenues & Margin or Earnings).
Select Growth rate type (Nominal or Real Growth & Inflation).
Enter Growth rate, Inflation rate (if shown), Profit Margin Now and Profit Margin in N Years (if Revenues & Margin), P/E Ratio Now and P/E Ratio in N Years, and FCF as % of Earnings.
Result: displays the approximate CAGR.
Bond ETF CAGR Calculator: estimates a bond ETF’s compound annual return.
Input Investment years for the projection period.
Enter Average duration of the bonds in years.
Check Zero coupon bond ETF if applicable.
Provide Yield now and Yield in N Years, or leave Average yield blank to default to the midpoint.
Result: displays the approximate CAGR.
LETF CAGR Calculator: estimates the long-run return of a leveraged ETF.
Enter Underlying ETF CAGR and Underlying ETF Volatility.
Specify Daily Leverage Factor (e.g. 3 for 3x).
Provide T-Bill Rate, Borrowing Spread above T-bills, and LETF Expense Ratio.
Result: displays the approximate LETF CAGR.
Optimal Daily Leverage Calculator: finds the leverage factor that maximizes risk-adjusted growth.
Enter Underlying ETF CAGR and Underlying ETF Volatility.
Provide Average T-Bill Rate, Borrowing Spread above T-bills, and Expense per Leverage.
Result: displays the approximate optimal leverage factor.
Two Fund Portfolio Calculator: computes combined CAGR and volatility of a stock/bond mix.
Enter Stock ETF CAGR, Bond ETF CAGR, Stock ETF Volatility, Bond ETF Volatility, and Stock-Bond Correlation.
Set Allocation to Stock ETF and Allocation to Bond ETF (sums to 100% unless Allow leverage is checked).
If Allow leverage is enabled, you may allocate >100% and must also enter Average T-Bill Rate, Borrowing Spread, and Expense Ratio for Leverage. The leftover allocation to T-bills is computed automatically.
Result: displays the portfolio’s CAGR and volatility.
Call Option Leverage Calculator: analyzes the leverage and borrowing implied by a call option versus owning the underlying ETF.
Enter Underlying Spot Price, Underlying Dividend Yield, Call Option Spot Price, Call Option Strike, and Call Option Expiration Date. The call price must be less than the underlying price.
The tool reports Time to Expiration, the implied leverage and simple annualized borrowing rate (per unit leverage) in the in-the-money linear region, and several key thresholds where the call becomes worthless, breaks even, or outperforms the underlying.
Time Value of Money Calculator
Builds a TVM solution surface from cashflow assumptions and plots feasible combinations of selected variables.
Choose contribution frequency/timing, select X and Y variables (optional color variable), and optionally constrain X/Y ranges or explicit color levels.
Results show scatter plots (combined and per color slice), a selectable scenario card, and scenario path views (chart, pie, and table).
Selecting a point in the scatter plot updates the selected scenario and shows its scenario path and scenario path table.
References
Data Sources
The data source for ordinary tickers not listed below is Tiingo.

Preset Tickers:
Note: Data series from FRED are denoted in [brackets]. This website uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.
TBILL/CASHX: Shiller 10Y rate - 1% (1885-1926), Fama-French Rf (1926-1954), 3-month T-Bill rate [DTB3] (1954-present)
SPYSIM/SPYTR: Schwert Dow Jones Composite Portfolio (1885-1928), Schwert S&P 500 Composite Portfolio (1928-1962), S&P 500 Price Index (1962-1993), SPY + 0.0945% p.a. (1993-present). Shiller dividends are added to all pre-SPY data. Created with the help of this GitHub repo.
OEFSIM: S&P100 Total Return Index (1989-2000), OEF + 0.20% p.a. (2000-present)
MDYSIM: S&P400 Total Return Index (1991-1995), MDY + 0.24% p.a. (1995-present)
IJRSIM: S&P600 Total Return Index (1994-2000), IJR + 0.06% p.a. (2000-present)
IWMSIM: Russell 2000 Total Return Index (1978-2000), IWM + 0.19% p.a. (2000-present)
USMVSIM: MSCI USA Minimum Volatility Index (1988-2011) - 0.15% p.a., USMV (2011-present)
KMLMSIM/KMLMX: KFA MLM Index - 0.9% p.a. (1988-2020), KMLM (2020-present)
GLDSIM/GOLDX: LBMA Gold Price at 3PM (1968-2004), GLD + 0.4% p.a. (2004-present)
SLVSIM/SLVTR: LBMA Silver Price at 3PM (1968-2006) SLV + 0.5% p.a. (2006-present)
SVIXSIM/SVIXX: Six Figure Investing backtest (derived from SHORTVOL) (2005-2022), SVIX (2022-present)
UVIXSIM: Six Figure Investing backtest (derived from LONGVOL) (2005-2022), UVIX (2022-present)
ZVOLSIM/ZIVBX: Six Figure Investing backtest (derived from SPVXMPI) (2004-2023), ZVOL (2023-present)
TLTSIM/TLTTR: 20Y rate [DGS20] (1962-1977), 30Y rate [DGS30] (1977-2002), TLT (2002-present)
ZROZSIM/ZROZX: 20Y rate [DGS20] (1962-1977), 30Y rate [DGS30] (1977-2009), ZROZ (2009-present)
VXUSSIM/VXUSX: MSCI World ex USA Index NR (1970-1996), VGTSX + 0.18% p.a. (1996-2011), VXUS + 0.05% p.a. (2011-present)
EFASIM: MSCI EAFE total return index NR (1970-2001), EFA + 0.32% p.a. (2001-present)
VEASIM: MSCI EAFE total return index NR (1970-1996), VTMGX + 0.08% p.a. (1996-2007), VEA + 0.03% p.a. (2007-present)
VWOSIM: VEIEX + 0.23% p.a. (1994-2005), VWO (2005-present)
VSSSIM: DISVX + 0.36% p.a. (1995-2009), VSS (2009-present)
EFVSIM: DFIVX (1995-2005), EFV (2005-present)
The MSCI World ex USA Index only has end-of-month prices available before 2000. Daily returns during that time period were generated to have a reasonable correlation with SPYSIM and match monthly volatility while maintaining end-of-month prices. Rebalancing frequencies of monthly or greater ensure that the backtest will emulate real-world performance.
VTISIM/VTITR: Fama-French Rm-Rf + Rf (1926-1992), VTSMX + 0.14% p.a. (1992-2001), VTI + 0.03% p.a. (2001-present)
Note that Fama-French use CRSP data, and Rm effectively tracks the CRSP US Total Market Index.
VTSIM: VTISIM/VXUSSIM returns at market cap weights (1970-2008), VT + 0.08% p.a (2008-present)
URTHSIM: VTISIM/EAFSIM returns at market cap weights (1970-1995), MSCI World Total Net Return Index (1995-2012), URTH + 0.24% p.a. (2012-present)
VVSIM/VOOSIM: Fama-French US Large Cap Blend (1926-1993), SPY + 0.20% p.a. (1993-present)
VTVSIM: Fama-French US Large Cap Value (1926-2004), VTV + 0.04% p.a. (2004-present)
VUGSIM: Fama-French US Large Cap Growth (1926-2004), VUG + 0.04% p.a. (2004-present)
VOSIM: Fama-French US Mid Cap Blend (1926-2004), VO + 0.04% p.a. (2004-present)
VOESIM: Fama-French US Mid Cap Value (1926-2007), VOE + 0.07% p.a. (2007-present)
VOTSIM: Fama-French US Mid Cap Growth (1926-2007), VOT + 0.07% p.a. (2007-present)
VBSIM: Fama-French US Small Cap Blend (1926-2004), VB + 0.05% p.a. (2004-present)
VBRSIM: Fama-French US Small Cap Value (1926-2004), VBR + 0.07% p.a. (2004-present)
VBKSIM: Fama-French US Small Cap Growth (1926-2004), VBK + 0.07% p.a. (2004-present)
IWCSIM: Fama-French US Micro Cap (1926-2005), IWC + 0.60% p.a. (2005-present)
Note that Fama-French Size & B/M portfolios above were constructed from the "100 Portfolios Formed on Size and Book-to-Market (10 x 10)" using the method described by this article from Portfolio Charts
DBMFSIM/DBMFX: SG CTA Index (2000-2019) + 2.5% p.a. - 0.85% p.a., DBMF (2019-present)
DBMF is not bound to any index, but tries to replicate the gross return of large CTA hedge funds. The SG CTA Index reflects the net return of 20 large CTA hedge funds open to new investment. Thus, although they likely have similar return profiles, DBMFSIM performance before 2019 should not be taken as a one-to-one replication of how DBMF would have performed back then.
The SG CTA Index is adjusted from net returns by adding 2.5% p.a (to adjust for hedge fund fees) and then subtracting 0.85% p.a. (to account for DBMF's expense ratio). This is a very rough approximation and should not be taken as the actual gross return of the SG CTA Index.
VIXSIM/VOLIX: VIX [VIXCLS] (1990-present)
GSGSIM/GSGTR: S&P GSCI TR Index - 0.75% p.a. (1979-2006), GSG (2006-present)
IEFSIM/IEFTR: 10Y rate [DGS10] (1962-2002), IEF (2002-present)
IEISIM/IEITR: 5Y rate [DGS5] (1962-2007), IEI (2007-present)
SHYSIM/SHYTR: 2Y rate [DGS2] (1962-2002), SHY (2002-present)
TIPSIM: VIPSX (2000-2003), TIP (2003-present)
STIPSIM: Simulated STIP using DFII5 and 0.03% expense ratio (2003-2010), STIP (2010-present)
LTPZSIM: Simulated LTPZ using DFII20 and DFII30 and 0.2% expense ratio (2003-2009), LTPZ (2009-present)
VCITSIM: Simulated VCIT using BAMLC3A0C57YEY and BAMLC4A0C710YEY and 0.03% expense ratio (1995-2010), VCIT (2010-present)
BNDSIM: VBMFX + 0.12% p.a. (1986-2007), BND (2007-present)
REITSIM: Fama-French RlEst from 48 Industry Portfolios - 0.13% p.a. (1926-1993), DFREX (1993-2004), VNQ (2004-present)
BTCSIM/BTCTR: Bitcoin Price at 4:00 pm ET from FirstRate Data (2010-2024), IBIT + 0.25% p.a. (2024-present)
ETHSIM/ETHTR: Ethereum Price at 4:00 pm ET from FirstRate Data (2016-2024), ETHA + 0.25% p.a. (2024-present)
XLBSIM/XLBTR: Fama-French Chems from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLB (1998-present)
XLCSIM/XLCTR: Fama-French Telcm from 12 Industry Portfolios - 0.09% p.a. (1926-2018), XLC (2018-present)
XLESIM/XLETR: Fama-French Energy from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLE (1998-present)
XLFSIM/XLFTR: Fama-French Money from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLF (1998-present)
XLISIM/XLITR: Fama-French Manuf from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLI (1998-present)
XLKSIM/XLKTR: Fama-French BusEq from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLK (1998-present)
XLPSIM/XLPTR: Fama-French NoDur from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLP (1998-present)
XLUSIM/XLUTR: Fama-French Utils from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLU (1998-present)
XLVSIM/XLVTR: Fama-French Hlth from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLV (1998-present)
XLYSIM/XLYTR: Fama-French Average of Durbl and Shops from 12 Industry Portfolios - 0.09% p.a. (1926-1998), XLY (1998-present)
QQQSIM/QQQTR: Nasdaq 100 index (1986-1994), RYOCX + 1.12% p.a. (1994-1999), QQQ (1999-present) [Nasdaq 100 index (1986-1994) do not include dividends, but the dividend yield was tiny and assumed to be roughly 0.2%, cancelling out QQQ's current expense ratio.]
EFFRX, Federal Funds Rate: Shiller 10Y rate - 1% (1885-1926), Fama-French Rf (1926-1954), Federal Funds Effective Rate [DFF] (1954-present)
INFLATION, Inflation: Shiller CPI (1885-1913), unadjusted CPI-U [CPIAUCNS] (1913-present)
CPI values are pinned to the end of the corresponding month. For example, the CPI for January 2025 is the value used for 2025-01-31. Daily values between CPI releases are filled in via linear interpolation.
CAOSSIM: AVOLX (2013-2023), CAOS (2023-present)
FNGUSIM: FNGA (2018-2025), FNGU (2025-present)
MCISIM: MCI from fund disclosures (1980-1985), MCI (1985-present)
MTUMSIM: MSCI USA Momentum Total Return Index - 0.15% p.a. (1994-2013), MTUM (2013-present)
GDESIM: 90% SPYSIM + 90% GLDSIM - 80% CASHX with quarterly rebalance, 5% band rebalance and 0.2% annual expenses (1968-2022), GDE (2022-present)
RSSBSIM: simulated RSSB using this testfolio portfolio (1969-2023), RSSB (2023-present)
NTSDSIM: 90% SPYSIM + 60% EAFSIM - 50% CASHX with quarterly rebalance, 5% band rebalance and 0.35% annual expenses (1969-2026), NTSD (2026-present)
UUPSIM: DXY index + 100% CASHX - 0.7% p.a. (1971-2007), UUP (2007-present) [The roll yield from interest rate differentials is omitted prior to 2007 due to limited foreign rate data. Historically, U.S. short-term rates have tended to be slightly above the DXY basket average, so this assumption may modestly underestimate returns during this period.]

Factor Return Sources:
Fama French: Ken French Data Library
AQR: AQR Datasets
q-Factors: global-q factors library
Fixed Income: the derived fixed income factors used in Factor Regression are built from preset ticker returns. Term (intermediate) = IEFSIM return minus the selected risk-free rate, Term (long) = TLTSIM return minus the selected risk-free rate, Term (ultra long) = ZROZSIM return minus the selected risk-free rate, and Credit = VCITSIM return minus IEFSIM return.
Featured guides
Portfolio Backtester Guide
Inputs, methodology, rebalancing, cashflows, outputs, and result interpretation.
Tactical Allocation Guide
Signals, allocation precedence, trading schedules, outputs, and tactical strategy interpretation.
Signal Analyzer Guide
Signal expressions, forward metrics, splits, best-fit methods, and result interpretation.
Asset Analyzer Guide
ETF, fund, and stock comparison across total return, drawdown, rolling metrics, beta, and correlation history.
Monte Carlo Portfolio Simulator Guide
Block-bootstrap sampling, synthetic rebalancing and cashflow schedules, inflation-adjusted metrics, success probabilities, and scenario interpretation.
Portfolio Optimizer Guide
Expected inputs, leverage, exposure constraints, frontier output, and allocation interpretation.
Efficient Frontier Guide
Historical frontier generation, cash overlay points, objective selection, and frontier interpretation.
Tactical Grid Search Guide
Tactical parameter sweeps, common-window grid comparison, and Tactical handoff.
Dual Signal Analyzer Guide
Two-signal expressions, 2D binning, forward metrics, split views, and interpretation.
Backtest Optimizer Guide
Historical weight search, heuristic solvers, constraints, withdrawal targets, and result interpretation.
Multi Signal Analyzer Guide
Multi-signal feature sets, tree fitting, train/test splits, cross-validation, and interpretation.
Rebalancing Sensitivity Guide
Rebalancing schedule comparison, period-end offsets, and timing effects on a fixed allocation.
Lump Sum vs DCA Guide
Lump sum investing versus dollar cost averaging across the same portfolio, side-cash treatment, and rolling historical windows.
LETF Analysis Guide
Synthetic leverage modeling, financing and fee drag, volatility decay, and shuffled-path DCA analysis.
Factor Regression Guide
Portfolio excess returns regressed against selected and custom factors with alpha, loadings, and model diagnostics.
Principal Component Analysis Guide
Principal components, explained variance, and raw versus normalized component portfolios for an aligned asset return set.
Custom Bond Tickers Guide
Flat and curve-aware bond syntax, maturity anchors, yield references, scenario tilts, and synthetic bond-series behavior.
Custom Tickers Guide
Syntax, aliases, leverage, financing references, backfills, return tuning, caps, and shuffle behavior.
My Workspace Guide
Uploads, aliases, saved portfolios, glidepaths, strategies, saved runs, local versus cloud storage, and My Metrics.
Calculator Suite Guide
Stock ETF CAGR, bond ETF CAGR, LETF CAGR, optimal leverage, two-fund portfolio, and call option leverage formulas.
Time Value of Money Calculator Guide
TVM surfaces, contribution schedules, solved variables, color slices, and scenario paths.
Browse all guides
testfolio

Advanced portfolio research tools for backtesting, optimization, tactical systems, signal analysis, and deeper portfolio diagnostics across repeatable workflows.

Testfolio's mission is to be the most intuitive and reliable portfolio analytics platform for DIY investors and financial advisors.

Market data updates at 6:00 PM and 9:30 PM EST.
PRODUCT
Portfolio Backtester
Asset Analyzer
Portfolio Optimizer
Backtest Optimizer
Efficient Frontier
Tactical Allocation
Tactical Grid Search
RESOURCES
Guides
Help
Changelog
Pricing
Terms of Service
Privacy Policy
Report a Bug
Contact Us
CONTACT
Facebook
X/Twitter
Reddit
Instagram
Email

Disclaimer: Past performance does not indicate future results. Information on this website is for educational purposes only and is not financial advice. No guarantees are made regarding accuracy or completeness of data or computations. Consult a qualified financial professional before making investment decisions.

© 2026 testfolio LLC
Built for portfolio research and education
Announcement
2026-04-23
Added URTHSIM preset ticker, which simulates URTH (Developed Markets including US) back to 1970.
Added aggregate signals to Tactical Allocation, which let you build breadth, weakest-link, and strongest-link style signals by taking the mean, min, or max of multiple indicators.
Full changelog
1 / 89
```
