# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T20:57:00.889605+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `keltner_reversion`

## Decisione

- Median net return -0.032817 fails minimum threshold 0.
- Median Sharpe -0.64267 fails minimum threshold 0.5.
- Median Sortino -0.311787 fails minimum threshold 0.5.
- Median Calmar -0.209871 fails minimum threshold 0.25.
- Worst drawdown 0.0423651 fails maximum threshold 0.04.
- Hard breaches 16 fails maximum threshold 0.
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
| Median net return | -3.28% |
| Median Sharpe | -0.6427 |
| Median Sortino | -0.3118 |
| Median Calmar | -0.2099 |
| Worst drawdown | 4.24% |
| Hard breaches | 16 |
| Median execution cost ratio | 0.34% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 1.0000 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 4.1806 ms |
| Risk checks | 10216 |
| Rule evaluations | 136016 |
| Ordini OMS | 13736 |
| Fill registrati | 7040 |
| Ledger entries | 10560 |
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
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.32% | -0.6427 | 3.89% | 0 | 72 | 112 | 80 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.31% | -0.1296 | 2.82% | 0 | 38 | 66 | 56 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.16% | 0.6127 | 0.35% | 0 | 13 | 26 | 26 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.77% | 0.1983 | 1.65% | 0 | 23 | 46 | 46 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -0.0004 | 3.68% | 0 | 105 | 116 | 22 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.28% | -0.7454 | 3.99% | 1 | 58 | 93 | 70 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.95% | -0.9331 | 4.17% | 0 | 136 | 156 | 40 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.23% | -0.1238 | 3.32% | 0 | 114 | 135 | 42 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.74% | -1.1259 | 4.00% | 0 | 102 | 129 | 54 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -0.7788 | 4.09% | 0 | 84 | 121 | 74 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.15% | -0.0020 | 3.00% | 0 | 50 | 80 | 60 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.77% | -0.7727 | 4.24% | 0 | 109 | 137 | 56 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.44% | 0.0577 | 3.00% | 0 | 47 | 74 | 54 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.93% | -1.1971 | 4.00% | 0 | 113 | 139 | 52 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -3.94% | -1.0990 | 3.94% | 0 | 130 | 144 | 28 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.44% | -0.0625 | 2.58% | 0 | 25 | 50 | 50 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 23 opening orders.
- Observation liquidated on hard breach — position closed at bar close, trading halted for the remainder of the period.
- Risk gate rejected 32 opening orders.
- Risk gate rejected 10 opening orders.
- Risk gate rejected 94 opening orders.
- Risk gate rejected 116 opening orders.
- Risk gate rejected 93 opening orders.
- Risk gate rejected 75 opening orders.
- Risk gate rejected 47 opening orders.
- Risk gate rejected 20 opening orders.
- Risk gate rejected 81 opening orders.
- Risk gate rejected 87 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
