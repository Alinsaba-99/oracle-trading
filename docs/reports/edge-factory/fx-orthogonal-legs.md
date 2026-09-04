# BL-738 — FX orthogonal legs (TSMOM + XSMOM, spot 1h Dukascopy)

**Generated**: 2026-09-03T22:24:57.553063+00:00

19 pairs, 58 legs, walk-forward > 2022-12-31, costs 1.5 bps/turnover.

| leg | SR | ann ret | vol | MaxDD | P(m≥5%) |
|---|---|---|---|---|---|
| xsmom_fx_30d | -0.42 | -1.5% | 3.5% | 5.9% | 0.0% |
| tsmom30 | -2.33 | -9.5% | 4.2% | 23.3% | 0.0% |
| tsmom90 | -1.89 | -7.7% | 4.2% | 19.0% | 0.0% |
| tsmom180 | -0.93 | -3.7% | 4.0% | 12.6% | 0.0% |
| portfolio_fx_ew | -2.05 | -6.9% | 3.4% | 17.1% | 0.0% |

## Verdetto onesto

FX momentum (TSMOM e XSMOM) su spot majors/crosses Dukascopy 1h è **negativo** nella finestra walk-forward > 2022-12-31 (pre-2023 era marginalmente positivo, coerente con il decay documentato del momentum FX). Le famiglie FX momentum NON entrano nel portafoglio BL-737. Il canale FX resta aperto solo per: carry con policy-rate proxy (richiede tassi, non solo spot) e intraday seasonality — entrambi da qualificare separatamente.
