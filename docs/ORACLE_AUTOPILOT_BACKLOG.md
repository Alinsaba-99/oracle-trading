# Oracle Autopilot — Execution Backlog v3

> Versione: 3.0
> Sostituisce: docs/plans/oracle-autopilot-gate-backlog-v2.md (archiviato)
> Allineato a: docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md (capability gate G0-G9)
> La matrice gate/stato fresca è in docs/ORACLE_AUTOPILOT_STATUS.md.
> Ultimo aggiornamento: 2026-07-24 | HEAD: a5ef2dc

## Regole operative

### Stati
- `[ ]` non iniziata
- `[~]` in corso
- `[x]` completata e verificata
- `[!]` bloccata con blocker documentato
- `[-]` rimossa con ADR

### Definition of Done
1. codice/test/docs esistono nel repository
2. pytest, ruff, mypy --strict verdi sul percorso interessato
3. nessun segreto introdotto
4. evidenza registrata nel report del milestone

---

## G0: Baseline Veritiera e Riproducibile

- [x] G0-001 Working tree consolidata
- [x] G0-002 Python 3.12 + Node 24 dichiarati
- [x] G0-003 Installazione da uv.lock verificata
- [x] G0-004 pytest, ruff, mypy strict (con override)
- [x] G0-005 Secret scan (gitleaks) attivo
- [x] G0-006 Lock Node (dashboard, eliza)
- [x] G0-007 Audit dipendenze Python
- [x] G0-008 Audit dipendenze Node
- [x] G0-009 Docker build verificato (pre-patch)
- [x] G0-010 `.dockerignore` e clean Docker build
- [ ] G0-013 Warning budget CI bloccante
- [ ] G0-014 SBOM Node
- [ ] G0-015 Report di chiusura G0

## G1: Autorità, Ambienti e Confini

- [x] G1-001 OracleMode enum
- [x] G1-002 Startup guard fail-closed
- [x] G1-003 Credenziali separate per ambiente
- [x] G1-004 Schema credenziali broker
- [x] G1-005 API auth fail-closed (key assente = solo dev)
- [x] G1-006 CLI live disabilitata (solo paper/dry-run)
- [x] G1-007 PortfolioPlan/TradeIntent in application/contracts/
- [x] G1-008 Test environment crossing
- [ ] G1-016 Report chiusura G1

## G2: Verità Futures e Point-in-Time Data

- [x] G2-001 ContractSpec con exchange, multiplier, point/tick value
- [x] G2-003 Catalogo ES/MES, NQ/MNQ, GC/MGC, CL/MCL
- [x] G2-006 TradingSession, timezone, maintenance break
- [x] G2-007 Holiday calendar CME, DST
- [x] G2-008 Roll policy
- [x] G2-012 Provenance: event_time, available_at, ingested_at
- [x] G2-015 Duplicate/gap/outlier detection
- [ ] G2-019 Catalogo ZN/ZB, 6E/M6E
- [ ] G2-021 Roll cost model
- [ ] G2-022 Intraday futures dataset certificato
- [ ] G2-023 Report chiusura G2
- [!] G2-024 Dataset ES_1d congelato per riproducibilità

## G3: Ledger, OMS e Reconciliation

- [x] G3-001 InMemoryLedger double-entry
- [x] G3-002 InMemoryOMS con idempotency key
- [x] G3-005 PostgreSQL schema (db/schema.sql)
- [x] G3-006 Reconciliation startup
- [x] G3-009 Duplicate fill handling
- [x] G3-012 Chaos test suite
- [ ] G3-013 PostgreSQL ledger production
- [ ] G3-014 Periodic reconciliation
- [ ] G3-017 Recovery idempotency dopo restart

## G4: Hard Risk Non Bypassabile

- [x] G4-001 FirmProgramProfile versionato
- [x] G4-002 SupportMode
- [x] G4-005 RiskManager obbligatorio in OrderManager
- [x] G4-013 Property test (35 test)
- [x] G4-015 Bypass-path audit
- [ ] G4-016 Automation policy dettaglio (Topstep ToS)
- [ ] G4-020 Report chiusura G4
- [ ] G4-021 PropFirmOrderRiskAdapter cablato nella CLI

## G5: Research Truth (M31 - Historical Replay Qualification)

- [x] G5-001 6 regimi esercitati
- [x] G5-002 Matrice 2x2x2 completa
- [x] G5-005 Profilo Topstep 50K certificato per replay
- [x] G5-006 Motore event-driven utilizzato
- [x] G5-009 Parity economica broker/ledger (48/48)
- [x] G5-012 0 hard breach, 0 mismatch, 0 slice non-flat
- [x] G5-013 Report M31 pubblicato (docs/reports/m31-*)
- [!] **REGRESSIONE**: data hash ES_1d cambiato — evidenza non riproducibile su working tree corrente

## G6: Paper & Shadow Operations

### G6-WP1: M32 — Rolling Paper Replay Diagnostic

- [x] M32-001..019 — scaffolding script, PaperBroker, resilience drills
- [x] M32-020 — Paper fill realism measurement
- [x] M32-021 — Decision stability measurement
- [x] M32-022 — Alpha decay measurement
- [x] M32-023 — 60 finestre mobili replay storico ES 1h
- [x] M32-024 — **Gate review: PASSED** (20/20 pass, max DD 0.21%) post-beta fix re-run
- [~] M32-025 — Report diagnostico generato
- [~] **G6-107 — Adapter futures certificato per paper** — non iniziato
- [~] **G6-103/104** — Recovery idempotency dopo restart — non iniziato
- [~] **G6-105** — Periodic reconciliation worker — non iniziato

### G6-WP2: M32a — Paper Sessions Live (post-M32)

Da avviare solo dopo che M32 diagnostic è accettato e la strategia è modificata per drawdown contenuto:

- [ ] M32a-001 Feed live paper (Polygon o alternativo)
- [ ] M32a-002 30 sessioni paper indipendenti (non sovrapposte)
- [ ] M32a-003 Policy breach check su ogni sessione
- [ ] M32a-004 Proof di kill-to-flat e recovery

### G6-WP3: M33 — Shadow Trading

Bloccato su M32a:

- [ ] M33-001..025 — Shadow broker, reconciliation, parity

### G6-I: Intelligence Feedback Loop (Q3 2026)

| Code | Task |
|:----:|------|
| `I-01` | **Factor Timing**: port da Inalpha di Rank IC, ICIR, decay state, null IC benchmark su `genetics/alpha/factors.py` (50 fattori) |
| `I-01b` | `factor_timing/factor_rank.py`: engine che ordina fattori per IC corrente |
| `I-01c` | `factor_timing/catalog.py`: registro fattori con metadata (source, kind, direction_hint) |
| `I-01d` | Collegamento tool `factor.timing` per agente Oracle |
| `I-01e` | Test: factor timing su ES 1h, verifica decay detection |
| `I-02` | **Research Memory**: `agents/confidence/memory.py` — ResearchMemory store (SQLite) |
| `I-02b` | `agents/confidence/tracker.py` — Hook nel decision path |
| `I-02c` | `agents/confidence/calibrator.py` — Platt scaling su accuracy storica |
| `I-02d` | `agents/confidence/decay.py` — DecayMonitor su strategie attive |
| `I-03` | **HMM+Lorenzian**: `analytics/regime/classification/lorenzian.py` — Lorenzian classifier |
| `I-03b` | `analytics/regime/classification/features.py` — Feature engineering |
| `I-03c` | `analytics/regime/classification/transition.py` — Transition detector |
| `I-03d` | `analytics/regime/classification/ensemble.py` — HMM + Lorenzian + BOCD voting |
| `I-03e` | Integrazione factor timing con regime ensemble (pesi per regime) |
| `I-04` | **Strategy Evolution Loop**: `genetics/evolver/governor/loop.py` — Evolution main loop |
| `I-04b` | `genetics/evolver/mutator/llm.py` — LLM mutation client |
| `I-04c` | `genetics/evolver/mutator/prompts.py` — Prompt templates |
| `I-04d` | `genetics/evolver/sandbox/ast_audit.py` — AST security audit |
| `I-04e` | `genetics/evolver/sandbox/subprocess.py` — Isolated subprocess run |
| `I-04f` | `genetics/evolver/sandbox/contract.py` — Strategy protocol check |
| `I-04g` | `genetics/evolver/evaluator/fitness.py` — Multi-objective fitness |
| `I-04h` | `genetics/evolver/evaluator/runner.py` — Backtest runner |
| `I-04i` | `analytics/backtest/cv/walkforward.py` — WalkForward splitter |
| `I-04j` | `analytics/backtest/cv/purgedkf.py` — Purged K-Fold |
| `I-04k` | `analytics/backtest/cv/cpcv.py` — Combinatorial Purged CV |
| `I-04l` | `analytics/backtest/cv/deflated_sharpe.py` — Deflated Sharpe Ratio |
| `I-04m` | Promozione candidato → paper live runner |
| `I-05` | **Edge Discovery** (VARRD style): `analytics/qualification/discovery/hypothesis.py` |
| `I-05b` | `analytics/qualification/discovery/event_study.py` — Event study engine |
| `I-05c` | `analytics/qualification/discovery/significance.py` — Bootstrap + FDR |
| `I-05d` | `analytics/qualification/discovery/edge_library.py` — Edge registry |
| `I-06` | **Three-step Orders**: `agents/decision/three_step.py` — ThreeStepOrder model |
| `I-06b` | `agents/decision/approval.py` — Approval token generator |
| `I-06c` | Bridge three-step → OMS.submit |

## G7: Certificazione Programma Prop-Firm

Non iniziato (dipende da G6).

---

## Note tecniche

### M32 — Post-Beta Re-run

Il re-run post-beta fix (B1/B2/B3 + ReconciliationEngine) ha prodotto:

| Metrica | Pre-fix | Post-beta |
|---------|:-------:|:---------:|
| Pass rate | 9/60 (15%) | **20/20 (100%)** |
| Max DD | 21.14% | **0.21%** |
| Gate decision | REJECTED | **PASSED** |

### G5 — Perché REGRESSED

Il dataset ES_1d.parquet su working tree corrente ha hash diverso dalla provenienza M31.
Serve ripristinare il dataset al commit M31 (`6106003`) o rigenerare il report.
