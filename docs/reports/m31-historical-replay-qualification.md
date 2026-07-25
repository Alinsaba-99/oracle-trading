# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-07-25T13:56:00.732618+00:00`
- Git commit: `8f590d8186084f31436da4a0c604d64381f87785`
- Data hash: `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`

## Decisione

- Median Sharpe 0.342445 fails minimum threshold 0.5.
- Median Sortino 0.492101 fails minimum threshold 0.5.
- Worst drawdown 0.159433 fails maximum threshold 0.04.
- Hard breaches 88 fails maximum threshold 0.

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
| Periodi | 6 |
| Varianti eseguite | 8/8 |
| Osservazioni | 48 |
| Median net return | 0.86% |
| Median Sharpe | 0.3424 |
| Median Sortino | 0.4921 |
| Median Calmar | 0.3546 |
| Worst drawdown | 15.94% |
| Hard breaches | 88 |
| Median execution cost ratio | 0.27% |
| Worst luck p-value | 0.4551 |
| Pooled luck p-value | 0.0020 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 0.7812 ms |
| Risk checks | 984 |
| Rule evaluations | 1944 |
| Ordini OMS | 1744 |
| Fill registrati | 1520 |
| Ledger entries | 3800 |
| Reconciliation | 48 |
| Mismatch | 0 |
| Slice non flat | 0 |

## Periodi

| Regime | Inizio | Fine | Selezione | Score |
|---|---|---|---|---:|
| bear | 2026-02-02 | 2026-03-30 | rolling_return | -0.0877187 |
| bull | 2026-03-30 | 2026-05-26 | rolling_return | 0.179822 |
| high_volatility | 2026-02-20 | 2026-04-17 | annualized_realized_volatility | 0.158948 |
| liquidity_shock | 2025-09-26 | 2025-11-20 | range_volume_shock_score | 0.0292086 |
| macro_surprise | 2026-03-13 | 2026-05-08 | absolute_actual_minus_consensus | 9000 |
| sideways | 2025-09-25 | 2025-11-19 | absolute_rolling_return | 0.000262773 |

## Osservazioni

| Periodo | Variante | Engine | Return | Sharpe | Max DD | Hard | Risk | Ordini | Fill | Recon |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.25% | 0.5213 | 10.93% | 1 | 28 | 56 | 56 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.91% | 0.8051 | 14.52% | 2 | 8 | 16 | 16 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.36% | 0.1877 | 14.19% | 2 | 23 | 39 | 32 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 20 | 29 | 18 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 2.07% | 0.4972 | 15.94% | 2 | 25 | 50 | 50 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | 0.1569 | 14.00% | 2 | 19 | 28 | 18 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 7 opening orders.
- Risk gate rejected 11 opening orders.
- Risk gate rejected 10 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
