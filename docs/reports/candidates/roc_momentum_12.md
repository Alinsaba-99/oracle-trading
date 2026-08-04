# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T20:41:23.251319+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `roc_momentum_12`

## Decisione

- Median net return -0.003056 fails minimum threshold 0.
- Median Sharpe -0.0602165 fails minimum threshold 0.5.
- Median Sortino -0.0647114 fails minimum threshold 0.5.
- Median Calmar -0.0305722 fails minimum threshold 0.25.
- Worst drawdown 0.0425096 fails maximum threshold 0.04.
- Hard breaches 8 fails maximum threshold 0.

## Evidenza

| Controllo | Stato |
|---|:---:|
| Periodi selezionati prima dell'esecuzione | PASS |
| Dati point-in-time verificati | PASS |
| Macro surprise verificata | PASS |
| Profilo regole prop certificato | PASS |
| Motore event-driven certificato | PASS |
| Replay regole prop-firm | PASS |
| Risk gate obbligatorio esercitato | PASS |
| OMS autorevole esercitato | PASS |
| Ledger riconciliato | PASS |
| Matrice intelligence completa | PASS |
| Artefatti intelligence verificati | PASS |
| Parità economica verificata | PASS |

## Sintesi

| Metrica | Valore |
|---|---:|
| Periodi | 17 |
| Varianti eseguite | 8/8 |
| Osservazioni | 136 |
| Median net return | -0.31% |
| Median Sharpe | -0.0602 |
| Median Sortino | -0.0647 |
| Median Calmar | -0.0306 |
| Worst drawdown | 4.25% |
| Hard breaches | 8 |
| Median execution cost ratio | 0.79% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 0.0020 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 4.5358 ms |
| Risk checks | 24200 |
| Rule evaluations | 136048 |
| Ordini OMS | 31784 |
| Fill registrati | 15168 |
| Ledger entries | 22752 |
| Reconciliation | 136 |
| Mismatch | 0 |
| Slice non flat | 0 |

## Periodi

| Regime | Inizio | Fine | Selezione | Score |
|---|---|---|---|---:|
| bear | 2000-09-19 | 2004-08-24 | rolling_return | -0.257694 |
| bear | 2005-03-22 | 2009-03-09 | rolling_return | -0.424313 |
| bear | 2016-03-31 | 2020-03-23 | rolling_return | 0.0823787 |
| bull | 2003-03-11 | 2007-02-08 | rolling_return | 0.816932 |
| bull | 2009-03-09 | 2013-02-28 | rolling_return | 1.23854 |
| bull | 2020-03-23 | 2024-03-11 | rolling_return | 1.30714 |
| high_volatility | 2000-09-25 | 2004-08-30 | annualized_realized_volatility | 0.208303 |
| high_volatility | 2008-01-02 | 2011-12-22 | annualized_realized_volatility | 0.2867 |
| high_volatility | 2018-11-26 | 2022-11-14 | annualized_realized_volatility | 0.23077 |
| liquidity_shock | 2001-05-14 | 2005-04-15 | range_volume_shock_score | 0.0498344 |
| liquidity_shock | 2006-05-17 | 2010-05-06 | range_volume_shock_score | 0.132418 |
| liquidity_shock | 2018-02-05 | 2022-01-24 | range_volume_shock_score | 0.0431018 |
| macro_surprise | 2007-05-11 | 2011-05-04 | absolute_actual_minus_consensus | 41000 |
| macro_surprise | 2017-10-10 | 2021-09-29 | absolute_actual_minus_consensus | 6000 |
| sideways | 2001-07-16 | 2005-06-16 | absolute_rolling_return | 0 |
| sideways | 2008-05-08 | 2012-04-30 | absolute_rolling_return | 0.00107759 |
| sideways | 2015-01-02 | 2018-12-24 | absolute_rolling_return | 0.144411 |

## Osservazioni

| Periodo | Variante | Engine | Return | Sharpe | Max DD | Hard | Risk | Ordini | Fill | Recon |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.32% | -0.0636 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.39% | -0.7263 | 4.15% | 0 | 98 | 176 | 156 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 8.00% | 1.0390 | 3.03% | 0 | 57 | 114 | 114 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.25% | 0.3424 | 2.16% | 0 | 75 | 150 | 150 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.27% | 0.5924 | 1.23% | 0 | 63 | 126 | 126 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.11% | 0.3448 | 4.02% | 0 | 334 | 368 | 68 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.31% | -0.0602 | 2.52% | 0 | 74 | 148 | 148 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.96% | -1.0997 | 3.96% | 0 | 449 | 478 | 58 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 11.24% | 0.8940 | 3.78% | 0 | 145 | 190 | 90 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.58% | -0.1312 | 2.28% | 0 | 79 | 158 | 158 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.67% | -0.6196 | 4.12% | 0 | 287 | 345 | 116 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 9.41% | 0.7142 | 3.88% | 0 | 78 | 138 | 120 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.86% | -0.9955 | 4.17% | 0 | 437 | 478 | 82 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.48% | 0.9863 | 3.76% | 0 | 69 | 122 | 106 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.19% | 0.0517 | 1.48% | 0 | 76 | 152 | 152 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.91% | -1.2194 | 4.25% | 0 | 534 | 556 | 44 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1361 | 4.01% | 1 | 96 | 126 | 60 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 20 opening orders.
- Risk gate rejected 300 opening orders.
- Risk gate rejected 420 opening orders.
- Risk gate rejected 100 opening orders.
- Risk gate rejected 229 opening orders.
- Risk gate rejected 18 opening orders.
- Risk gate rejected 396 opening orders.
- Risk gate rejected 16 opening orders.
- Risk gate rejected 512 opening orders.
- Risk gate rejected 66 opening orders.
- Observation liquidated on hard breach — position closed at bar close, trading halted for the remainder of the period.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
