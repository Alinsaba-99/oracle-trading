# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-08-04T20:47:40.649223+00:00`
- Git commit: `8e9bfbee09b1396593b1e2ff92059f6cf45bfa8b`
- Data hash: `lake:ES:1d:6523rows`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`
- Segnale: `donchian_breakout`

## Decisione

- Median Sharpe 0.215862 fails minimum threshold 0.5.
- Median Sortino 0.179167 fails minimum threshold 0.5.
- Median Calmar 0.147641 fails minimum threshold 0.25.
- Worst drawdown 0.0477071 fails maximum threshold 0.04.
- Hard breaches 16 fails maximum threshold 0.

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
| Median net return | 1.37% |
| Median Sharpe | 0.2159 |
| Median Sortino | 0.1792 |
| Median Calmar | 0.1476 |
| Worst drawdown | 4.77% |
| Hard breaches | 16 |
| Median execution cost ratio | 0.31% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 0.0020 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 3.1517 ms |
| Risk checks | 6320 |
| Rule evaluations | 136048 |
| Ordini OMS | 9744 |
| Fill registrati | 6848 |
| Ledger entries | 10272 |
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
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2004-08-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2009-03-09 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -2.84% | -0.6342 | 3.63% | 0 | 34 | 68 | 68 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bear-2020-03-23 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 7.10% | 0.9081 | 2.79% | 0 | 20 | 40 | 40 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2007-02-08 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.82% | 0.4779 | 1.93% | 0 | 32 | 64 | 64 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2013-02-28 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.49% | 0.7629 | 1.45% | 0 | 23 | 46 | 46 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| bull-2024-03-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.82% | 0.2159 | 4.77% | 0 | 263 | 279 | 32 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2004-08-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -4.00% | -1.0180 | 4.00% | 1 | 69 | 95 | 52 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2011-12-22 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.28% | 0.2261 | 1.98% | 0 | 24 | 48 | 48 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| high_volatility-2022-11-14 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.29% | 0.6412 | 3.79% | 0 | 33 | 55 | 44 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2005-04-15 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.44% | -0.3158 | 3.46% | 0 | 32 | 64 | 64 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2010-05-06 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.88% | 0.1640 | 3.71% | 0 | 24 | 48 | 48 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| liquidity_shock-2022-01-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 10.45% | 0.7459 | 2.93% | 0 | 31 | 53 | 44 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2009-05-11 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.51% | 0.0948 | 3.75% | 0 | 28 | 56 | 56 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| macro_surprise-2019-10-07 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 12.64% | 0.9328 | 2.90% | 0 | 27 | 45 | 36 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2005-06-16 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.19% | -0.2660 | 2.84% | 0 | 32 | 64 | 64 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2012-04-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.43% | 0.4247 | 1.97% | 0 | 22 | 44 | 44 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |
| sideways-2018-12-24 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.37% | 0.1988 | 3.10% | 0 | 27 | 54 | 54 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 43 opening orders.
- Observation liquidated on hard breach — position closed at bar close, trading halted for the remainder of the period.
- Risk gate rejected 247 opening orders.
- Risk gate rejected 11 opening orders.
- Risk gate rejected 9 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
