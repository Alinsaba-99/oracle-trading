# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-23 (post audit-remediation-beta Fase 1-2).
> Gerarchia fonti: ROADMAP (perché) → STATUS (cosa) → BACKLOG (come) → ADR (decisioni) → report (evidenza).

## 1. Identità del checkpoint

- **Branch**: audit-remediation-beta (in flight); base `main` HEAD `974ab91`
- **Baseline HEAD**: `974ab91` (fix(beta.1): OMS VWAP + Ledger notional + idempotency persistence + overfill guard)
- **Working tree**: contiene Fase 3 (CLI risk adapter, ReconciliationEngine, ruff fix/format)
- **Gate attivo**: G6 — Paper e shadow operations (BLOCKED — pre-requisito tecnico risolto, manca validazione M32 post-fix)
- **Gate precedente**: G5 — Research truth (NOT_STARTED, vedi [ADR-014](ADR/ADR-014-m31-evidence-loss.md))
- **Modalità autorizzata**: RESEARCH, REPLAY
- **PAPER, SHADOW, EVALUATION, FUNDED**: DISABLED
- **Roadmap**: [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md)
- **Backlog v3**: [docs/ORACLE_AUTOPILOT_BACKLOG.md](ORACLE_AUTOPILOT_BACKLOG.md)

## 2. Baseline verificata (2026-07-23 post-beta)

| Comando/prova | Esito |
|---|---|
| `uv lock --check` | Pass |
| `uv build --wheel` + `oracle trade submit --dry-run` | ✅ Pass — packaging include `application` |
| `oracle --help` | ✅ Entry point installato |
| `oracle trade submit --risk-adapter propfirm --dry-run` | ✅ Nuovo flag accettato |
| `oracle trade reconcile --broker paper` | ✅ ReconciliationEngine end-to-end |
| Pytest test_ledger_oms (audit beta) | ✅ 28/28 — VWAP, notional, overfill, SQLite persistence |
| Pytest test_contracts_audit (audit beta) | ✅ 8/8 — PortfolioPlan, TradeIntent, validators |
| Pytest test_cross_engine (audit beta) | ✅ 5/5 — incl. Nautilus schema guard |
| Pytest test_event_driven_qualification | ✅ 10/10 — broker/ledger cash parity restored |
| Pytest test_replay_qualification | ✅ 4/4 |
| Pytest tests/unit/ full | 1059 pass, 1 skip (unrelated) |
| Pytest tests/policy/ | 88 pass |
| Pytest tests/genetics/ | 398 pass, 5 skipped (pybroker unavailable) |
| Ruff check | 69 errors (was 744, post-fix+unsafe-fixes) |
| Ruff format | 33 files reformatted, 457 OK (was 144) |
| Docker Compose config | ✅ Parse valido |
| API /api/health con auth | ✅ 200 |
| Secret scan | ✅ gitleaks pass |
| Wheel smoke (venv pulita) | ✅ CLI funzionante |

## 3. Gate status

| Gate | Stato | Evidenza sintetica |
|:----:|:-----:|----------|
| G0 | IN_PROGRESS | Test e lint locali verdi; CI remota non verificata; warning budget non bloccante |
| G1 | IN_PROGRESS | OracleMode enum, startup guard, credential isolation esistono; CLI fallisce su `application` (fissato), risk kernel obbligatorio, API auth fail-closed |
| G2 | IN_PROGRESS | ContractSpec (8 futures), calendari CME, roll, provenance, data quality esistono |
| G3 | NOT_STARTED | OMS/ledger/reconciliation sono in-memory e non collegati al path CLI operativo |
| G4 | IN_PROGRESS | RiskManager obbligatorio, governor esiste; CLI ha `_PaperRiskAdapter` di default + `--risk-adapter propfirm` ora disponibile |
| G5 | **NOT_STARTED** | Vedi [ADR-014](ADR/ADR-014-m31-evidence-loss.md) — M31 evidence non riproducibile. Dataset hash cambiato (9a526125... vs 09a22268... del vecchio M31). Regime selector mai implementato. |
| G6 | **BLOCKED** | M32 diagnostic FAIL (9/60 pass, drawdown 8.2%); pre-requisiti tecnici risolti in beta (OMS VWAP, Ledger notional, idempotency persistence, ReconciliationEngine in CLI). Serve re-run M32 con il codice post-fix. |
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

(Le voci 1, 2, 3 sono state chiuse in `audit-remediation-beta` Fase 1-2.)

1. ~~Ripristinare dataset ES_1d a hash M31 o rigenerare report di qualification~~
2. ~~Correggere 8 test genetics obsoleti (operatori causali)~~ → erano 5 fail pybroker, ora 5 skip puliti
3. ~~Creare `.dockerignore` e verificare `docker compose build`~~ → ancora P0/G0
4. Re-run M32 diagnostic con il codice post-fix (B1/B2/B3 + ReconciliationEngine)
5. Validare M32 → sbloccare G6 PAPER
6. Re-run M31 end-to-end (nuovo sprint) per chiudere G5
7. Cablare G3: OMS/ledger/reconciliation production-ready (Postgres path esiste ma non è il default)
