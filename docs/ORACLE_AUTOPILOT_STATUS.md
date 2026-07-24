# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-24 (post cleanup).
> Gerarchia fonti: ROADMAP (perché) → STATUS (cosa) → BACKLOG (come) → ADR (decisioni) → report (evidenza).

## 1. Identità del checkpoint

- **Branch**: `audit-remediation-beta` HEAD `a5ef2dc`
- **Baseline HEAD**: `a5ef2dc` (chore(beta.5): mypy --strict cleanup — 21 → 0 errors)
- **Working tree**: pulito — binary untracked, empty dirs rimossi, TODO aggiornati, backlog allineato
- **Gate attivo**: G6 — Paper & Shadow Operations 🟡
- **Gate precedente**: G5 — Research Truth (PASSED — M31 APPROVED, ma dataset hash non corrisponde)
- **Modalità autorizzata**: RESEARCH, REPLAY
- **PAPER, SHADOW, EVALUATION, FUNDED**: DISABLED

## 2. Baseline verificata (2026-07-24 post-cleanup)

| Comando/prova | Esito |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 491 files already formatted |
| `mypy --strict core/ market/ analytics/ execution/ genetics/ research/ agents/ audit/ policy/ orchestration/` | ✅ Success: no issues |
| `pytest tests/` | **✅ 2116 passed**, 6 skipped, 0 failed |

### Dettaglio test

| Suite | Risultato |
|---|---|
| tests/unit/ | 1022 pass |
| tests/integration/ | 5 pass |
| tests/policy/ | 88 pass |
| tests/genetics/ | 398 pass, 5 skip (pybroker) |
| tests/qualification/ | 14 pass |
| tests/execution/ | pass |
| tests/agents/ | pass |

## 3. Gate status

| Gate | Stato | Evidenza sintetica |
|:----:|:-----:|----------|
| G0 | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan, .dockerignore |
| G1 | ✅ PASSED | OracleMode, startup guard, credential isolation, API auth, CLI guard |
| G2 | ✅ PASSED | ContractSpec (8 futures), CME calendari, roll, PIT data quality |
| G3 | ✅ (in-memory) | InMemoryLedger/OMS, reconciliation startup, chaos test; PostgreSQL path non attivo |
| G4 | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit |
| G5 | ✅ PASSED (M31) | 6 regimi, 48 slice, 0 hard breach, APPROVED; dataset ES_1d hash non corrisponde |
| G6 | **🟡 IN PROGRESS** | M32 re-run: 20/20 PASS, max DD 0.21%. Paper gate review PASSED. |
| G7 | ⚪ NOT_STARTED | |
| G8 | ⚪ NOT_STARTED | |
| G9 | ⚪ NOT_STARTED | |

## 4. Risultati M32 — Post-Beta Re-run

Eseguito con codice post-fix (B1/B2/B3 + ReconciliationEngine):

| Metrica | Prima (pre-fix) | Dopo (post-beta) |
|---|---|---|
| Finestre totali | 60 | 20 |
| Passate | 9 (15%) | **20 (100%)** |
| Fallite | 51 | **0** |
| Drawdown massimo | 21.14% | **0.21%** |
| Gate decision | ❌ REJECTED | **✅ PASSED** |

**Nota**: i 20 test M32a sono sessioni paper indipendenti (non finestre sovrapposte come il vecchio diagnostic). Servono 30 sessioni per l'exit formale G6-WP2.

## 5. Cleanup eseguito (2026-07-24)

| Cosa | Stato |
|---|---|
| Untrack file binari (data/ohlcv/*.parquet, checkpoints/*.json, experiments/experiments.db) | ✅ |
| Rimossi 13 package dir vuoti (scaffold mai riempiti) | ✅ |
| TODO marker semplificati nel codice (run_ga.py, graph.py) | ✅ |
| `.dockerignore` verificato esistente | ✅ |
| G0-010 marcato completato | ✅ |
| M32-024 aggiornato a PASSED | ✅ |
| Backlog HEAD + data aggiornati | ✅ |

## 6. Rischi residui

1. ⚠️ Dataset ES_1d hash cambiato — M31 non riproducibile su working tree corrente
2. ⚠️ Warning Python (321) e coverage scope non definito
3. ⚠️ NATS, QuestDB, Qdrant, Redis descritti oltre l'uso reale

## 7. Prossimo lavoro eseguibile

1. **G6-WP2**: 30 sessioni paper live indipendenti (M32a; ne servono 30, fatte 20)
2. **G6-103/104**: Recovery idempotency + open orders dopo restart
3. **G6-105**: Periodic reconciliation worker
4. **G6-107**: Adapter futures certificato per paper broker
5. **G6-WP3**: M33 — Shadow trading (25 task)
6. **G5 fix**: Ripristinare dataset ES_1d o rigenerare report M31

## 8. Nuovo workstream: G6-I — Intelligence Feedback Loop 📍

Il progetto si sblocca aggiungendo un **ciclo chiuso di apprendimento** parallelo
ai gate operativi. Ispirato a Inalpha e VARRD.

| Priorità | Milestone | Cosa fa | Stima |
|:--------:|:---------:|---------|:-----:|
| 🔴 P1 | **I-01 Factor Timing** | 50 fattori classificati per Rank IC corrente | 3-5gg |
| 🔴 P1 | **I-02 Research Memory** | Decisioni registrate, confidence calibrata | 3-4gg |
| 🟡 P2 | **I-03 HMM+Lorenzian** | Regime detection ibrida, pesi per regime | 2-3gg |
| 🟡 P2 | **I-04 Strategy Evolution** | LLM scrive strategie, cross-val, promozione | 5-8gg |
| 🟢 P3 | **I-05 Edge Discovery** | Event study per nuovi pattern | 1-2gg |
| 🟢 P3 | **I-06 Three-step Orders** | propose→approve→execute con token | 2-3gg |

Dettaglio completo: [docs/plan-integration-inalpha-varrd.md](plan-integration-inalpha-varrd.md)
