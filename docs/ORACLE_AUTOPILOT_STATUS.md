# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-22.
> Gerarchia fonti: ROADMAP (perché) → STATUS (cosa) → BACKLOG (come) → ADR (decisioni) → report (evidenza).

## 1. Identità del checkpoint

- **Branch**: main
- **Baseline HEAD**: `ae209f7` (feat(m32): 60 paper sessions su dati reali ES 1h)
- **Working tree**: contiene modifiche non committate — packaging, Docker, kill-switch, M32 script, test
- **Gate attivo**: G6 — Paper e shadow operations (BLOCKED)
- **Gate precedente**: G5 — Research truth (REGRESSED — data hash mismatch dal M31)
- **Modalità autorizzata**: RESEARCH, REPLAY
- **PAPER, SHADOW, EVALUATION, FUNDED**: DISABLED
- **Roadmap**: [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md)
- **Backlog v3**: [docs/ORACLE_AUTOPILOT_BACKLOG.md](ORACLE_AUTOPILOT_BACKLOG.md)

## 2. Baseline verificata (2026-07-22)

| Comando/prova | Esito |
|---|---|
| `uv lock --check` | Pass |
| `uv build --wheel` + `oracle trade submit --dry-run` | ✅ Pass — packaging include `application` |
| `oracle --help` | ✅ Entry point installato |
| Pytest chaos + M32 test | ✅ 11/11 (test_operations + test_paper_sessions_reale) |
| Pytest non-slow exclude M32 test | ⚠️ 2072 pass, 8 fail (test_operators.py — test su vecchia semantica full-array) |
| Ruff check | ⚠️ 3 errori preesistenti |
| Ruff format --check | ⚠️ 38 file da riformattare (preesistenti, non toccati) |
| mypy strict | ⚠️ 15 errori in 7 file (preesistenti, non toccati) |
| Docker Compose config | ✅ Parse valido, context risolti correttamente |
| Docker build | ⚠️ Da testare con `docker compose build` dopo creazione `.dockerignore` |
| API /api/health con auth | ✅ 200 (esentato da auth middleware) |
| API /api/v1/performance/summary senza auth | ✅ 401 |
| API /metrics | ✅ 200 (counter ancora hardcoded a 0) |
| Dashboard build + test | ✅ 15/15 test, build Vite riuscita |
| Dashboard npm audit | 0 vulnerability |
| Eliza typecheck/test/build | ✅ 2/2 test |
| Secret scan | ✅ gitleaks pass |
| Wheel smoke (venv pulita) | ✅ CLI funzionante |

## 3. Gate status

| Gate | Stato | Evidenza sintetica |
|:----:|:-----:|----------|
| G0 | IN_PROGRESS | Test e lint locali verdi; CI remota non verificata; warning budget non bloccante |
| G1 | IN_PROGRESS | OracleMode enum, startup guard, credential isolation esistono; CLI fallisce su `application` (fissato), risk kernel obbligatorio, API auth fail-closed |
| G2 | IN_PROGRESS | ContractSpec (8 futures), calendari CME, roll, provenance, data quality esistono; dataset ES_1d cambiato hash dal M31 |
| G3 | NOT_STARTED | OMS/ledger/reconciliation sono in-memory e non collegati al path CLI operativo |
| G4 | IN_PROGRESS | RiskManager obbligatorio, governor esiste; CLI usa `_PaperRiskAdapter` minimale |
| G5 | **REGRESSED** | M31 era APPROVED per historical replay; ma data hash ES_1d è cambiato — l'evidenza non è più riproducibile sul working tree corrente |
| G6 | **BLOCKED** | M32 diagnostic FAIL (9/60 pass, drawdown 8.2%); paper non è live; shadow, recovery, adapter certificates non iniziati |
| G7 | NOT_STARTED | |
| G8 | NOT_STARTED | |
| G9 | NOT_STARTED | |

## 4. Risultati M32 — Rolling Paper Replay Diagnostic

Eseguito con script corrente su 60 finestre mobili (5gg, slide 1gg), SMA(5/20), realistic broker, seed 32023:

| Metrica | Valore |
|---|---|
| Finestre totali | 60 |
| Passate | 9 (15%) |
| Fallite | 51 |
| Incidenti hard | 51 (max_dd_exceeded) |
| Gate decision | ❌ REJECTED |
| P&L medio per finestra | -$3,104 |
| Sharpe medio | -0.95 |
| Drawdown medio | 8.24% |
| Drawdown massimo | 21.14% |

**Natura**: finestre mobili sovrapposte (75% overlap medio) su replay storico Parquet, non sessioni live paper indipendenti.

## 5. Rischi residui P0/P1

### P1 aperti
1. ⚠️ Dataset ES_1d cambiato — M31 non riproducibile sul working tree corrente
2. ⚠️ 8 test genetics falliti (operatori causali vs test su full-array)
3. ⚠️ Docker build non verificato (manca `.dockerignore`)
4. ⚠️ Warning Python (319) e coverage scope non definito
5. ⚠️ NATS, QuestDB, Qdrant, Redis descritti oltre l'uso reale

## 6. Prossimo lavoro eseguibile

1. Ripristinare dataset ES_1d a hash M31 o rigenerare report di qualification
2. Correggere 8 test genetics obsoleti (operatori causali)
3. Creare `.dockerignore` e verificare `docker compose build`
4. Chiudere M32 diagnostic con report formale (M32-025)
5. Avviare M32a — paper replay non sovrapposto con feed reale
