# M31 — Historical Replay Qualification

> Decisione: **REJECTED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-07-30T22:10:02.385872+00:00`
- Git commit: `ce644ba582808a250e45e9feec7b302ed18dbcbd`
- Data hash: `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`

## Decisione

- Median net return -0.0024492 fails minimum threshold 0.
- Median Sharpe -1.15371 fails minimum threshold 0.5.
- Median Sortino 0.0428035 fails minimum threshold 0.5.
- Median Calmar -3.1481 fails minimum threshold 0.25.
- Worst drawdown 0.127396 fails maximum threshold 0.04.
- Hard breaches 48 fails maximum threshold 0.

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
| Median net return | -0.24% |
| Median Sharpe | -1.1537 |
| Median Sortino | 0.0428 |
| Median Calmar | -3.1481 |
| Worst drawdown | 12.74% |
| Hard breaches | 48 |
| Median execution cost ratio | 0.06% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 0.0519 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 0.8539 ms |
| Risk checks | 448 |
| Rule evaluations | 1920 |
| Ordini OMS | 640 |
| Fill registrati | 384 |
| Ledger entries | 960 |
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
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.08% | -2.5100 | 0.08% | 0 | 1 | 2 | 2 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 23 | 26 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 6 | 9 | 6 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.41% | -5.9230 | 0.41% | 0 | 5 | 10 | 10 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.24% | 0.2026 | 12.74% | 2 | 12 | 15 | 6 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -0.75% | -8.4381 | 0.75% | 0 | 9 | 18 | 18 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.
- Risk gate rejected 20 opening orders.
- Risk gate rejected 3 opening orders.
- Risk gate rejected 9 opening orders.

## Stop condition

M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
