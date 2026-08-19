# AI Analyst Swarm — Historical Backtest (2020-01-01)

**Generated**: 2026-08-17T07:14:39.979587+00:00
**As-of date**: 2020-01-01
**Forward window**: 12 months
**Targets**: 49 tickers
**SPY 12mo return**: 16.64%

## Hit-rate summary

| Decision | N | Beat SPY | Hit Rate |
|---|---|---|---|
| APPROVE | 0 | 0 | 0.0% |
| REDUCE_SIZE | 18 | n/a | n/a |
| REJECT | 31 | 13 | 41.9% |

## Per-ticker detail

| Ticker | Decision | Conf | Forward Return | Alpha vs SPY |
|---|---|---|---|---|
| AAPL | REDUCE_SIZE | 0.65 | 79.62% | 62.98% |
| MSFT | REJECT | 0.00 | 39.48% | 22.83% |
| AMZN | REJECT | 0.00 | 73.12% | 56.48% |
| GOOGL | REJECT | 0.00 | 26.86% | 10.21% |
| META | REJECT | 0.00 | 29.60% | 12.96% |
| NVDA | REJECT | 0.00 | 119.54% | 102.90% |
| TSLA | REJECT | 0.00 | 707.40% | 690.75% |
| JPM | REJECT | 0.00 | -7.92% | -24.56% |
| V | REDUCE_SIZE | 0.65 | 14.96% | -1.69% |
| JNJ | REJECT | 0.00 | 9.81% | -6.83% |
| WMT | REDUCE_SIZE | 0.65 | 23.24% | 6.60% |
| MA | REJECT | 0.00 | 17.82% | 1.18% |
| PG | REDUCE_SIZE | 0.65 | 14.39% | -2.25% |
| UNH | REJECT | 0.00 | 19.89% | 3.24% |
| HD | REDUCE_SIZE | 0.65 | 23.61% | 6.97% |
| DIS | REDUCE_SIZE | 0.65 | 22.25% | 5.60% |
| BAC | REJECT | 0.00 | -13.63% | -30.27% |
| XOM | REJECT | 0.00 | -36.64% | -53.28% |
| INTC | REJECT | 0.00 | -17.88% | -34.52% |
| KO | REJECT | 0.00 | 2.39% | -14.25% |
| CSCO | REJECT | 0.00 | -5.67% | -22.32% |
| PFE | REJECT | 0.00 | 2.98% | -13.66% |
| MRK | REDUCE_SIZE | 0.65 | -9.66% | -26.30% |
| PEP | REDUCE_SIZE | 0.65 | 11.62% | -5.02% |
| AVGO | REDUCE_SIZE | 0.65 | 41.04% | 24.40% |
| CRM | REJECT | 0.00 | 33.18% | 16.54% |
| ADBE | REJECT | 0.00 | 48.75% | 32.10% |
| NFLX | REJECT | 0.00 | 59.06% | 42.42% |
| ABBV | REDUCE_SIZE | 0.65 | 24.06% | 7.42% |
| TMO | REJECT | 0.00 | 41.82% | 25.17% |
| COST | REJECT | 0.00 | 32.95% | 16.30% |
| CVX | REDUCE_SIZE | 0.65 | -25.75% | -42.39% |
| ABT | REDUCE_SIZE | 0.65 | 26.68% | 10.04% |
| MCD | REJECT | 0.00 | 7.99% | -8.65% |
| ACN | REDUCE_SIZE | 0.65 | 24.52% | 7.88% |
| WFC | REDUCE_SIZE | 0.65 | -42.43% | -59.07% |
| LIN | REDUCE_SIZE | 0.65 | 26.33% | 9.69% |
| QCOM | REDUCE_SIZE | 0.65 | 73.40% | 56.76% |
| TXN | REJECT | 0.00 | 29.26% | 12.62% |
| DHR | REDUCE_SIZE | 0.65 | 42.86% | 26.22% |
| NEE | REJECT | 0.00 | 29.87% | 13.23% |
| ORCL | REJECT | 0.00 | 21.47% | 4.83% |
| PM | REJECT | 0.00 | 1.93% | -14.71% |
| UPS | REJECT | 0.00 | 47.07% | 30.42% |
| MS | REJECT | 0.00 | 34.28% | 17.64% |
| RTX | REJECT | 0.00 | -23.84% | -40.48% |
| HON | REDUCE_SIZE | 0.65 | 19.40% | 2.76% |
| IBM | REJECT | 0.00 | -3.37% | -20.01% |
| COP | REJECT | 0.00 | -36.42% | -53.07% |

## Interpretation

- APPROVE hit rate > 65% → swarm has edge on long picks
- APPROVE hit rate near 50% → swarm APPROVE is noise
- REJECT underperform rate > 65% → swarm Skeptic has edge
- For statistical significance: target 100+ theses (current: 49)
- Apply DSR (Deflated Sharpe Ratio) correction for multiple testing
