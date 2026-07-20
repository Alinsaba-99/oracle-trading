# M31 — Historical Replay Qualification

> Decisione: **APPROVED**
> Questo report non autorizza evaluation, live o funded trading.

## Identità

- Generato: `2026-07-19T18:52:59.272696+00:00`
- Git commit: `13c4a35adbb3283ccb0ad240a3f2f6b9e2a62a21`
- Data hash: `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42`
- Config hash: `8f27b8cdd97aa8b8d4e212a1982993845f33d117b587fe058b3cb06d2a85c302`
- Discovery engine: `oracle-regime-selector-v1`
- Qualification engine: `oracle-event-driven-paper-v1`

## Decisione

- All M31 coverage, authority, and threshold checks passed.

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
| Median net return | 0.88% |
| Median Sharpe | 1.0130 |
| Median Sortino | 2.8353 |
| Median Calmar | 3.1978 |
| Worst drawdown | 3.43% |
| Hard breaches | 0 |
| Median execution cost ratio | 0.46% |
| Worst luck p-value | 1.0000 |
| Pooled luck p-value | 0.0080 |
| Luck test | pooled out-of-sample moving-block bootstrap |
| Worst decision latency p95 | 1.0657 ms |
| Risk checks | 984 |
| Rule evaluations | 1952 |
| Ordini OMS | 1968 |
| Fill registrati | 1968 |
| Ledger entries | 3936 |
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
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bear-2026-03-30 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.83% | 1.9328 | 1.93% | 0 | 28 | 56 | 56 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| bull-2026-05-26 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 4.08% | 4.0042 | 1.42% | 0 | 8 | 16 | 16 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| high_volatility-2026-04-17 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 0.07% | 0.0931 | 3.43% | 0 | 23 | 46 | 46 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| liquidity_shock-2025-11-20 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.42% | -2.3812 | 2.30% | 0 | 20 | 40 | 40 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| macro_surprise-2026-04-13 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | 1.69% | 1.9945 | 1.71% | 0 | 25 | 50 | 50 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-off__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-off__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-on__debate-off__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-baseline | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |
| sideways-2025-11-19 | scouts-on__debate-on__fund-manager-challenger | oracle-event-driven-paper-v1 | -1.35% | -2.2626 | 2.23% | 0 | 19 | 38 | 38 | PASS |

## Limitazioni dichiarate

- Official prop rules are exercised through an explicit historical replay-only gate.
- Offline intelligence artifacts are deterministic and make no external model calls.

## Stop condition

M31 è conclusa: tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 è completa e ogni soglia versionata è rispettata.
