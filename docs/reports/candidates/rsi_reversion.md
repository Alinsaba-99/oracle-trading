# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T21:09:22.514709+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `rsi_reversion`

## Decisione

- Median net return -0.025912 fails minimum threshold 0.
- Median Sharpe -0.473644 fails minimum threshold 0.5.
- Median Sortino -0.163226 fails minimum threshold 0.5.
- Median Calmar -0.174698 fails minimum threshold 0.25.
- Worst drawdown 0.0454593 fails maximum threshold 0.04.
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
| Median net return | -2.59% |
| Median Sharpe | -0.4736 |
| Median Sortino | -0.1632 |
| Median Calmar | -0.1747 |
| Worst drawdown | 4.55% |
| Hard breaches | 0 |
| Median execution cost ratio | 0.26% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 1.0000 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 5.5145 ms |
| Risk checks | 7752 |
| Rule evaluations | 136008 |
| Ordini OMS | 10464 |
| Fill registrati | 5424 |
| Ledger entries | 8136 |
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
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 74 | 102 | 56 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.40% | -0.6600 | 3.77% | 0 | 79 | 113 | 68 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.41% | 0.0579 | 2.78% | 0 | 30 | 50 | 40 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.39% | 0.2335 | 0.87% | 0 | 8 | 16 | 16 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.87% | 0.4864 | 1.78% | 0 | 11 | 22 | 22 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.64% | -1.0611 | 3.64% | 0 | 97 | 101 | 8 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.51% | -0.7567 | 3.87% | 0 | 75 | 103 | 56 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.87% | -0.6848 | 3.87% | 0 | 115 | 137 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.19% | -0.2640 | 4.55% | 0 | 95 | 106 | 22 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.59% | -0.4926 | 3.77% | 0 | 78 | 111 | 66 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.38% | -0.1466 | 3.62% | 0 | 44 | 63 | 38 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.91% | -0.4736 | 4.07% | 0 | 74 | 97 | 46 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.55% | -0.0525 | 2.80% | 0 | 43 | 61 | 36 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.43% | -1.0244 | 3.82% | 0 | 53 | 73 | 40 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.26% | -0.1586 | 3.17% | 0 | 21 | 42 | 42 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.00% | 0.0073 | 2.56% | 0 | 19 | 38 | 38 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 46 opening orders.
- Risk gate rejected 45 opening orders.
- Risk gate rejected 10 opening orders.
- Risk gate rejected 93 opening orders.
- Risk gate rejected 47 opening orders.
- Risk gate rejected 84 opening orders.
- Risk gate rejected 33 opening orders.
- Risk gate rejected 25 opening orders.
- Risk gate rejected 51 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
