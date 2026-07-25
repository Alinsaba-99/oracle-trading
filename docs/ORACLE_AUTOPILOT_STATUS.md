# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-25 (post-audit remediation beta).
> La gerarchia documentale è: ROADMAP (perché) → STATUS (cosa) → BACKLOG
> (come) → ADR (decisioni) → report (evidenza). Solo STATUS riporta la
> matrice gate/stato.

## 1. Identità del checkpoint

- **Branch**: `audit-remediation-beta`
- **HEAD**: `ffe91b4` (feat(g6-i): G3 Postgres + G5 restore + Factor Timing v1 + regime ensemble + Lorentzian causal fix)
- **Working tree**: pulito (i 5 script untracked sono ereditati da lavoro precedente non mio)
- **Modalità autorizzata**: RESEARCH, REPLAY, PAPER
- **PAPER, SHADOW, EVALUATION, FUNDED**: PAPER parziale (gate rejected). SHADOW/EVALUATION/FUNDED: DISABLED

## 2. Baseline verificata

| Comando | Esito |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 491 files formatted |
| `mypy --strict core/ market/ analytics/ execution/ genetics/ research/ agents/ audit/ policy/ orchestration/` | ✅ Success: no issues |
| `pytest tests/` | **✅ 2116+ passed**, 6 skipped, 0 failed |
| Postgres path (`--storage=postgres`) | ✅ — schema applicato, OMS/ledger verdi |
| Smoke regime→paper→OMS | ✅ |

## 3. Gate status (unica tabella gate/stato autoritativa)

| Gate | Stato | Evidenza | Limite noto |
|---|---|---|---|
| G0 baseline | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan | warning budget non applicato |
| G1 autorità/ambienti | ✅ PASSED | mode guard, startup fail-closed, credential isolation, CLI guard | `OrderManager` ammette risk=None in path script untracked |
| G2 contract data | 🟡 PARTIAL | ContractSpec, CME calendars, roll, PIT detection. Intraday futures **non disponibile** (Polygon key required) | ES=F daily solo da yfinance |
| G3 ledger/OMS | ✅ PASSED | PostgreSQL path attivo 25-lug; RecoveryService + ReconciliationWorker + idempotency; restart senza perdita/dup | persistenza Postgres solo in `--storage=postgres` |
| G4 hard risk | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit | adapter PropFirm cablato in CLI ma **escluso dal paper harness** |
| **G5 research truth** | ❌ **REGRESSED** | M31 riproducibile solo **se** `data/ohlcv/ES_1d.parquet` rimane pinned a `09a22…`. ADR-014 documenta la perdita di evidenza. | dataset non pinned; refresh_data lo sovrascrive |
| G6 paper | 🟡 **REJECTED** | M32 diagnostic 20/20 PASSED (max DD 0.21%). M32a WP2: 23/30 PASSED, **mean_sharpe = -0.31 (borderline -0.5)**, **pass_rate 0.77 vs target 0.90** | gate failed per regime choppy-biased + missing Lorentzian weighting |
| G6-I feedback loop | 🟡 PARTIAL | Factor Timing v1 (26 test), Lorentzian causal-fix (6 test), Regime Ensemble (14 test) | nessun gate end-to-end; Lorentzian mai trigger dominante |
| G7 programm prop-firm | ⚪ NOT_STARTED | dipende da G5+G6+poli cert | block su G5/G6 |
| G8 funded limited | ⚪ NOT_STARTED | | |
| G9 continuous ops | ⚪ NOT_STARTED | | |

### 3.1 Risultati M32a WP2 (verifica 25-lug)

Eseguito: `python scripts/run_g6_wp2_paper_sessions.py --sessions 30 --data data/ohlcv/ES_1d.parquet --storage memory`

| Metrica | Target | Risultato |
|---|---|---|
| pass_rate | ≥ 0.90 | **0.77** (23/30) ❌ |
| mean_sharpe | ≥ -0.5 | -0.31 ✅ (borderline) |
| mean_max_dd | ≤ 3.0% | 1.54% ✅ |
| reconcile_clean_rate | = 1.0 | 1.00 ✅ |

**Decisione**: REJECTED. Causa: regime choppy-biased (29/30 mean_rev per default `_sma_regime_heuristic`).

### 3.2 Distribuzione regime (M32a)

| Regime | n sessioni | Specialist attivo | Pass rate |
|---|---|---|---|
| choppy | 29 | mean_rev | 21/29 (72%) |
| volatile | 1 | breakout | 1/1 (100%) |

## 4. Rischi residui

1. **🔴 Dataset non pinned.** `data/ohlcv/ES_1d.parquet` è untracked (vedi
   `.gitignore`). Qualunque `refresh_data.py --multi-timeframe ES` o
   `yfinance_futures("ES")` lo riscrive. Backlog: BL-001/002/003.
2. **🟡 Regime detector choppy-biased.** Soglie fisse del `_sma_regime_heuristic`
   producono 96%+ choppy su 250gg daily. Backlog: BL-010..014.
3. **🟡 Warning budget 321 Python warnings** non bloccante in CI; da definire scope.
4. **🟡 NATS / QuestDB / Qdrant / Redis** descritti in Compose oltre l'uso reale.
5. **🟡 CCXT_bridge e uvicorn** in `ps -ef` non sono di Oracle (sono di
   `distill-lab`). Niente da fare qui.

## 5. Stato reale vs dichiarato

| Affermazione | Verificato |
|---|---|
| "M31 APPROVED per historical replay" | ❌ falso — ADR-014: dataset lineage GAP. M31 da rifare |
| "G3 Postgres path attivo" | ✅ vero (commit ffe91b4) |
| "G6-WP2 PASSED 20/20" | ✅ vero **solo per il primo diagnostic M32** (DD 0.21%). M32a paper 23/30 = REJECTED |
| "Regime-ensemble routing OK" | 🟡 routing OK, ma routing quasi sempre choppy perché heuristica sbilanciata |
| "Lorentzian causal fix" | ✅ test verdi, ma Lorentzian mai trigger dominante nel paper run |
| "Live disabilitato finché G7 non è PASSED" | ✅ vero — modalità RESEARCH/PAPER autorizzate, live bloccato |

## 6. Cosa NON è stato risolto

- I 5 script `run_backtest_evaluation.py` / `run_lorentzian_test.py` /
  `run_lorentzian_v2.py` / `run_risk_sized_eval.py` / `run_rolling_challenge.py`
  sono untracked e **hanno errori mypy** che non ho toccato (lavoro
  precedente non mio scope). Vedi `BACKLOG.md` BL-030 per cleanup.
- `data/ohlcv/ES_1d.parquet` va pinnato in `data/pinned/` (BL-001).
- Regime detector va ricalibrato (BL-010..014).
- M31 va rifatto da zero (BL-022) — non si può "recuperare" il vecchio
  (ADR-014).
- `_sma_regime_heuristic` non è hysteresys-aware (`ensemble.py` ha
  `_apply_hysteresis` ma non è esposta via `RoutingDecision`).

## 7. Prossimo lavoro eseguibile (single source of truth: BACKLOG.md)

Vedi `BACKLOG.md` per le task atomiche. Sommario:

1. **P1**: BL-001..003 — pin ES_1d, anti-overwrite, dataset registry
2. **P1**: BL-010..014 — regime rebalance + hysteresys
3. **P1**: BL-020..024 — 100 sessioni paper indipendenti, MES-aware sizing
4. **P2**: BL-030..031 — cleanup script untracked, mypy remediation
5. **P2**: BL-022 — M31 re-run con post-fix code
6. **P3**: G6-I Phase 2 (factor timing → cross-asset)
7. **P3**: G7 readiness (una firm specifica)

## 8. Decisioni chiave recenti (link agli ADR)

- **ADR-008** modular monolith + authority boundaries → ACCEPTED 2026-07-18
- **ADR-009** data/state storage → ACCEPTED 2026-07-18 (PostgreSQL SoT)
- **ADR-010** execution safety boundary → ACCEPTED
- **ADR-011** backtest discovery vs qualification → ACCEPTED
- **ADR-012** capability gate al posto delle Phase → ACCEPTED
- **ADR-013** versioned prop-firm rule catalog → ACCEPTED
- **ADR-014** M31 evidence loss → ACCEPTED 2026-07-23 (G5 REGRESSED)

## 9. Link di lettura

- [`ROADMAP.md`](../ROADMAP.md) — vision, gate G0-G9, principi
- [`BACKLOG.md`](../BACKLOG.md) — task atomiche eseguibili (BL-NNN)
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — architettura corrente e target
- [`docs/AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) — audit secco 2026-07-25
- [`docs/RUNBOOK.md`](RUNBOOK.md) — operatività
- [`docs/ADR/`](ADR/) — decisioni normative immutabili
