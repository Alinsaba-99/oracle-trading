# AI Analyst Swarm — Historical Backtest (2020-01-01)

**Generated**: 2026-08-17T06:53:11.718103+00:00
**As-of date**: 2020-01-01
**Forward window**: 12 months
**Targets**: 2 tickers
**SPY 12mo return**: 16.64%

## Hit-rate summary

| Decision | N | Beat SPY | Hit Rate |
|---|---|---|---|
| APPROVE | 0 | 0 | 0.0% |
| REDUCE_SIZE | 0 | n/a | n/a |
| REJECT | 2 | 0 | 0.0% |

## Per-ticker detail

| Ticker | Decision | Conf | Forward Return | Alpha vs SPY |
|---|---|---|---|---|
| AAPL | REJECT | 0.00 | 79.62% | 62.98% |
| MSFT | REJECT | 0.00 | 39.48% | 22.83% |

## Interpretation

- APPROVE hit rate > 65% → swarm has edge on long picks
- APPROVE hit rate near 50% → swarm APPROVE is noise
- REJECT underperform rate > 65% → swarm Skeptic has edge
- For statistical significance: target 100+ theses (current: 2)
- Apply DSR (Deflated Sharpe Ratio) correction for multiple testing
