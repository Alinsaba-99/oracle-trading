# BL-736 — Portfolio SR-max (combined qualified edges)

**Generated**: 2026-09-03T22:17:00.765198+00:00

16 legs, equal-weight, walk-forward test > 2022-12-31, costs included per-leg (10 bps/turnover).

## Per-leg (test window)

| leg | SR | ann ret | vol |
|---|---|---|---|
| BTCUSDT_rsi_14 | +0.55 | +2.9% | 5.5% |
| BTCUSDT_trend_filt_20_200 | +0.72 | +6.3% | 9.0% |
| ES_alpha_003 | +3.37 | +30.5% | 8.0% |
| ES_bband_20_2 | +0.54 | +3.6% | 7.0% |
| ES_donchian_20 | +1.08 | +10.6% | 9.8% |
| ES_ema_20_50 | +1.13 | +12.9% | 11.4% |
| ETHUSDT_ema_20_50 | +0.87 | +8.2% | 9.6% |
| EURUSD_alpha_050 | +3.52 | +20.8% | 5.4% |
| EURUSD_bband_30_2.5 | +0.60 | +2.7% | 4.7% |
| SPY_alpha_001 | +1.18 | +8.1% | 6.7% |
| SPY_donchian_50 | +1.09 | +12.3% | 11.2% |
| basis_BTCUSDT | +0.16 | +0.9% | 7.6% |
| basis_ETHUSDT | -0.15 | -1.6% | 8.2% |
| funding_z_ADAUSDT | -0.79 | -6.4% | 8.0% |
| funding_z_ETHUSDT | +0.42 | +2.8% | 7.3% |
| funding_z_XRPUSDT | -0.63 | -4.2% | 6.5% |

## Leverage ladder

| lev | ann ret | vol | SR | MaxDD | m-mean | P(m≥5%) |
|---|---|---|---|---|---|---|
| 1.0× | +4.1% | 2.9% | +1.40 | 2.6% | +0.47% | 0.0% |
| 1.5× | +6.1% | 4.3% | +1.40 | 3.9% | +0.71% | 0.0% |
| 2.0× | +8.2% | 5.7% | +1.40 | 5.2% | +0.95% | 0.0% |
| 3.0× | +12.4% | 8.6% | +1.40 | 7.8% | +1.41% | 8.9% |
| 4.0× | +16.6% | 11.5% | +1.40 | 10.3% | +1.88% | 13.3% |

## Honest note

5%/month net requires SR ~4 at 20% vol; leverage scales return AND drawdown — this report measures the true gap without inflation.
