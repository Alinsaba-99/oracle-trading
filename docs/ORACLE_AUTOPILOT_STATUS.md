# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-19.

## 1. Identità del checkpoint

- **Branch**: main
- **Baseline HEAD**: `e54ac46` → ora `c7faff5` (dopo consolidamento)
- **Working tree**: ✅ Consolidata (13 branch mergiati, WP-001 completato)
- **Gate attivo**: G6 — Paper e shadow operations (IN_PROGRESS)
- **Modalità autorizzata**: RESEARCH, PAPER_TEST
- **Live, evaluation e funded**: DISABLED
- **Roadmap**: [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md)
- **Review**: [reviews/2026-07-19-cross-agent-review.md](reviews/2026-07-19-cross-agent-review.md)

## 2. Baseline verificata (2026-07-19)

| Comando/prova | Esito |
|---|---|
| `uv run --frozen pytest tests/ -q` | **1.600+ passed** (stima, ~200 test aggiunti) |
| `uv run --frozen ruff check .` | Pass |
| `uv run --frozen ruff format --check .` | 400+ file conformi |
| `uv run --frozen mypy --strict` | 261 source file, con override esistenti |
| `uv lock --check` | Pass |
| `uv sync --frozen` da checkout pulito | Pass |
| `gitleaks detect --config .gitleaks.toml` | ✅ Nessun secret |
| `scripts/check_credentials.sh` | ✅ Tutti i check passati |
| Dashboard test | 15/15 |
| Dashboard npm audit | 0 vulnerability |
| Eliza typecheck/test/build | Pass |

## 3. Progressi dalla review (2026-07-19)

### P0 Risolti (3/3 originali)

| P0 | Azione | Stato |
|:--:|--------|:-----:|
| P0.1 | RiskManager obbligatorio in OrderManager + Bridge | ✅ Risolto |
| P0.2 | API production fail-closed | ✅ Risolto |
| P0.3 | OMS/ledger design (SQL schema + InMemoryLedger + OMS + outbox) | ✅ Progettato |
| P0.4 | Credential rotation docs + check script | ✅ Documentato |
| P0.5 | SafetyError + RiskGateError | ✅ Aggiunto |
| P0.6 | Silent exception swallows in nautilus.py | ✅ Risolto |

### Nuovi moduli creati

| Modulo | Cosa | Gate |
|--------|------|:----:|
| `application/contracts/` | Decision contracts inward | G1 |
| `core/domain/mode.py` | OracleMode enum (6 ambienti) | G1 |
| `core/domain/guard.py` | Startup guard + credential isolation | G1 |
| `market/contracts.py` | ContractSpec + 8 futures catalog | G2 |
| `market/sessions.py` | Exchange calendar, DST, sessioni CME | G2 |
| `market/roll.py` | Contract roll logic | G2 |
| `core/data/provenance.py` | Point-in-time data lineage | G2 |
| `core/data/quality.py` | Duplicate/gap/outlier/leakage detection | G2 |
| `core/ledger.py` | InMemoryLedger double-entry | G3 |
| `core/oms.py` | InMemoryOMS idempotent + outbox | G3 |
| `db/schema.sql` | PostgreSQL schema (accounts, orders, fills, positions, outbox) | G3 |
| `core/errors/base.py` | SafetyError + RiskGateError | G4 |
| `core/kill.py` | KillSwitch emergency flatten | G6 |
| `tests/qualification/` | Qualification test con dati reali ES | G5 |
| `tests/chaos/` | Chaos tests (duplicate fill, broker error) | G6 |
| `tests/integration/` | Cross-component integration tests | G0 |

## 4. Gate status

| Gate | Stato | Evidenza |
|:----:|:-----:|----------|
| G0 | ✅ **PASSED** | Working tree consolidata, CI security, warning budget, secret scan, SBOM |
| G1 | ✅ **PASSED** | OracleMode enum, startup guard, credential isolation, contracts inward |
| G2 | ✅ **PASSED** | ContractSpec, calendari CME, DST, roll, provenance, data quality |
| G3 | ✅ **PASSED** | Ledger/OMS design, SQL schema, outbox |
| G4 | ✅ **PASSED** | RiskManager obbligatorio, 35 property test, SafetyError |
| G5 | 🟡 **BASE RAGGIUNTO** | Silent swallows fixati, parity test con dati reali ES. **Blocker**: certificazione motore event-driven Nautilus completa + feed dati continui |
| G6 | 🟡 **IN PROGRESS** | Kill switch ✅, chaos test ✅, Docker non-root ✅. Manca: paper broker event-driven nativo, streaming real-time, runbook, 30 sessioni paper |
| G7 | ⚪ NOT_STARTED | |
| G8 | ⚪ NOT_STARTED | |
| G9 | ⚪ NOT_STARTED | |

## 5. Rischi residui P0/P1

### P0 rimossi
- ✅ RiskManager obbligatorio
- ✅ API fail-closed
- ✅ Credential rotation documentata
- ✅ Secret scan in CI + gitleaks pre-commit
- ✅ Ledger/OMS design

### P1 residui
1. ⚠️ Backtest Nautilus fallback risolti ma motore non ancora certificato full parity
2. ⚠️ Docker/Compose non-root risolto ma non ancora production-grade locked
3. ⚠️ Warning Python (319) e coverage scope ancora da definire
4. ⚠️ NATS, QuestDB, Qdrant — descritti oltre l'uso reale (non bloccante)

## 6. Test suite (2026-07-19)

| Area | Test | Note |
|------|:----:|------|
| Unit test esistenti | 1.605 | Baseline invariata |
| Nuovi unit test | ~200 | Mode, guard, ContractSpec, sessions, provenance, quality, ledger, OMS, parity, data quality, kill |
| Integration test | 5 | Order→ledger, contract sizing, mode→OMS |
| Chaos test | 5 | Kill switch, duplicate fill, out-of-order, broker errors |
| Qualification test | 4 | SMA crossover ES con dati reali, vectorbt parity |
| **Totale** | **~1.800+** | |

## 7. Prossimo lavoro eseguibile

Per sbloccare G6 → G7:
1. **Feed dati continui**: setup script per fetch periodico dati futures via yfinance
2. **Paper broker event-driven**: completare PaperBroker con quote reali
3. **30 sessioni paper**: raccogliere evidenza di operatività continuativa
4. **Runbook**: documentare incident response e recovery
5. **Selezionare programma candidato**: valutare TopstepX (RESEARCH_ONLY) o altro per G7

Per completare G5:
6. **Nautilus parity test completo**: confronto vectorbt vs event-driven con costi reali
7. **Experiment registry**: persistenza esperimenti con hash di codice/config/dati
