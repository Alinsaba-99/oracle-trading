# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T20:44:22.777194+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `bollinger_reversion`

## Decisione

- Median net return -0.027587 fails minimum threshold 0.
- Median Sharpe -0.625266 fails minimum threshold 0.5.
- Median Sortino -0.340854 fails minimum threshold 0.5.
- Median Calmar -0.176156 fails minimum threshold 0.25.
- Worst drawdown 0.0422174 fails maximum threshold 0.04.
- Hard breaches 32 fails maximum threshold 0.
- Pooled luck p-value 1 fails maximum threshold 0.1.

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
| Median net return | -2.76% |
| Median Sharpe | -0.6253 |
| Median Sortino | -0.3409 |
| Median Calmar | -0.1762 |
| Worst drawdown | 4.22% |
| Hard breaches | 32 |
| Median execution cost ratio | 0.45% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 1.0000 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 6.4539 ms |
| Risk checks | 13800 |
| Rule evaluations | 136040 |
| Ordini OMS | 18520 |
| Fill registrati | 9440 |
| Ledger entries | 14160 |
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
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.63% | -0.7363 | 3.87% | 0 | 113 | 168 | 110 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.13% | -0.1052 | 3.36% | 0 | 51 | 92 | 82 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.61% | 0.2487 | 0.54% | 0 | 33 | 66 | 66 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.99% | 0.2087 | 2.02% | 0 | 39 | 78 | 78 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.84% | 0.2073 | 3.83% | 0 | 157 | 173 | 32 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.76% | -0.6253 | 3.99% | 0 | 163 | 201 | 76 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -0.9332 | 4.00% | 1 | 24 | 48 | 48 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0286 | 3.91% | 0 | 118 | 152 | 68 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.41% | -0.9630 | 4.20% | 1 | 121 | 152 | 62 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -0.8466 | 4.05% | 1 | 110 | 155 | 90 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.27% | 0.1249 | 3.58% | 0 | 61 | 102 | 82 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.62% | -0.7360 | 4.10% | 0 | 161 | 195 | 68 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1439 | 3.58% | 0 | 55 | 90 | 70 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.01% | -1.1697 | 4.22% | 1 | 119 | 148 | 58 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.67% | -0.9916 | 3.99% | 0 | 198 | 216 | 36 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.65% | 0.3921 | 2.50% | 0 | 39 | 78 | 78 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 125 opening orders.
- Risk gate rejected 58 opening orders.
- Risk gate rejected 10 opening orders.
- Risk gate rejected 141 opening orders.
- Observation liquidated on hard breach — position closed at bar close, trading halted for the remainder of the period.
- Risk gate rejected 84 opening orders.
- Risk gate rejected 90 opening orders.
- Risk gate rejected 65 opening orders.
- Risk gate rejected 20 opening orders.
- Risk gate rejected 127 opening orders.
- Risk gate rejected 180 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
