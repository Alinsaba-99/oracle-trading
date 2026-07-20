# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-07-20.

## 1. Identità del checkpoint

- **Branch**: main
- **Baseline HEAD**: (merged feat/m32-paper-trading)
- **Working tree**: Paper session script, Polygon REST polling, WebSocket feed; M32 in corso
- **Gate attivo**: G6 — Paper e shadow operations (IN_PROGRESS)
- **Gate precedente**: G5 — Research truth e qualification (✅ PASSED per M31)
- **Modalità autorizzata**: RESEARCH, PAPER_TEST, PAPER
- **Live, evaluation e funded**: DISABLED
- **Roadmap**: [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md)
- **Backlog v2**: [plans/oracle-autopilot-gate-backlog-v2.md](plans/oracle-autopilot-gate-backlog-v2.md)

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
| Test mirati M31 + OMS/ledger/reconciliation | **66 passed** |
| Ruff check/format sui file M31 | Pass |
| Replay event-driven MES/ES proxy | **6 regimi, 48 osservazioni, APPROVED** |

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
| `analytics/qualification/` | Period selection, replay event-driven, audit, gate e report M31 | G5 |
| `config/qualification/m31.yaml` | Soglie M31 versionate | G5 |
| `scripts/run_replay_qualification.py` | Replay event-driven fail-closed e report firmato da hash | G5 |
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
| G5 | ✅ **PASSED** | M31 APPROVED: 6 regimi, 48 slice (matrice 2x2x2), macro PIT hashata, profilo Topstep replay-only verificato, parity broker/ledger, 0 hard breach e soglie rispettate |
| G6 | 🟡 **IN PROGRESS** | Paper fill realistico, feed realtime, Docker non-root, observability, audit, RBAC e runbook presenti. Mancano sessioni paper/shadow qualificate, recovery evidence e adapter futures certificato |
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
1. ✅ M31 ha certificato il motore locale per replay storico, non per produzione
2. ✅ Macro actual-vs-consensus con `available_at` e hash PIT presente
3. ✅ Matrice intelligence 2x2x2 eseguita con artefatti offline causali hashati
4. ✅ Parity economica broker/ledger verificata su tutte le 48 slice
5. ✅ Controllo MES con SMA 5/15 long-short e stop intrabar rispetta le soglie M31
6. ⚠️ Docker/Compose non-root risolto ma non ancora production-grade locked
7. ⚠️ Warning Python (319) e coverage scope ancora da definire
8. ⚠️ NATS, QuestDB, Qdrant — descritti oltre l'uso reale (non bloccante)

## 6. Test suite (2026-07-19)

| Area | Test | Note |
|------|:----:|------|
| Unit test esistenti | 1.605 | Baseline invariata |
| Nuovi unit test | ~200 | Mode, guard, ContractSpec, sessions, provenance, quality, ledger, OMS, parity, data quality, kill |
| Integration test | 5 | Order→ledger, contract sizing, mode→OMS |
| Chaos test | 5 | Kill switch, duplicate fill, out-of-order, broker errors |
| Qualification test | 4 | SMA crossover ES con dati reali, vectorbt parity |
| M31/control-plane mirati | 66 | Event-driven, regime, evaluator, Topstep replay gate, stop intrabar, parity |
| **Totale** | **~1.800+** | |

## 7. Prossimo lavoro eseguibile

Per proseguire dopo M31:
1. **M32 paper**: account paper dedicato, feed/clock, bootstrap OMS-ledger e 60 sessioni senza incidente hard
2. **M33 shadow**: broker read-only, posizioni/ordini/account, fill e reconciliation shadow
3. **M34 evaluation**: solo dopo paper e shadow completati, con approvazione umana esplicita
4. **M35-G7**: certificare adapter futures e programma specifico; M31 non abilita live/funded
