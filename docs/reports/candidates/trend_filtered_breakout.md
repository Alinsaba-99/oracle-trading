# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T21:02:10.501617+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `trend_filtered_breakout`

## Decisione

- Median Sharpe 0.166706 fails minimum threshold 0.5.
- Median Sortino 0.135693 fails minimum threshold 0.5.
- Median Calmar 0.077167 fails minimum threshold 0.25.
- Worst drawdown 0.0481165 fails maximum threshold 0.04.

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
| Median net return | 0.89% |
| Median Sharpe | 0.1667 |
| Median Sortino | 0.1357 |
| Median Calmar | 0.0772 |
| Worst drawdown | 4.81% |
| Hard breaches | 0 |
| Median execution cost ratio | 0.28% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 0.0020 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 9.9344 ms |
| Risk checks | 4480 |
| Rule evaluations | 136024 |
| Ordini OMS | 7408 |
| Fill registrati | 5856 |
| Ledger entries | 8784 |
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
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.43% | -0.3795 | 2.35% | 0 | 27 | 54 | 54 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.72% | 0.7568 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.48% | 0.4030 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.11% | 0.4008 | 1.75% | 0 | 28 | 56 | 56 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.76% | 0.0746 | 4.81% | 0 | 210 | 226 | 32 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.12% | 0.0490 | 1.15% | 0 | 14 | 28 | 28 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.73% | 0.1667 | 1.75% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 3.99% | 0.3044 | 4.11% | 0 | 21 | 42 | 42 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.07% | -0.0201 | 1.15% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.89% | 0.2049 | 2.90% | 0 | 19 | 38 | 38 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 5.82% | 0.4408 | 3.63% | 0 | 22 | 44 | 44 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0213 | 2.79% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.59% | 0.5940 | 3.61% | 0 | 19 | 38 | 38 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.15% | 0.0527 | 1.15% | 0 | 21 | 42 | 42 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.57% | 0.3386 | 1.75% | 0 | 22 | 44 | 44 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.04% | 0.1644 | 3.40% | 0 | 25 | 50 | 50 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 194 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
