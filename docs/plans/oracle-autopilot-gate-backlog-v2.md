# Oracle Autopilot — Gate-Aligned Execution Backlog v2

> Versione: 2.0
> Sostituisce: `docs/plans/oracle-autopilot-atomic-backlog-v1.md` (deprecato)
> Allineato a: `docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md` (capability gate G0-G9)
> Stato al: 2026-07-20
> HEAD: `13c4a35` (M30 security consolidata + M31 closeout in working tree)

## Regole operative

### Stati ammessi
- `[ ]` non iniziata
- `[~]` in corso
- `[x]` completata e verificata
- `[!]` bloccata con blocker documentato
- `[-]` rimossa con ADR

### Definition of Done
Una task è completa quando:
1. codice/test/docs esistono nel repository
2. `pytest`, `ruff`, `mypy --strict` verdi
3. nessun segreto introdotto
4. evidenza registrata nel gate report

### Sequenza di ripresa
1. leggere `docs/ORACLE_AUTOPILOT_STATUS.md`
2. verificare `git status` e `git log --oneline -5`
3. eseguire `uv run --frozen pytest tests/ -q` per baseline
4. selezionare prima task `[ ]` con dipendenze soddisfatte
5. marcarla `[~]`, implementare, testare, marcarla `[x]`

---

## Stato sintetico

| Gate | Stato | In backlog |
|:----:|:-----:|:----------:|
| G0 | ✅ PASSED | M00-M01 |
| G1 | ✅ PASSED | M02-M03 |
| G2 | ✅ PASSED | M04-M06 |
| G3 | ✅ PASSED | M19-M21 (design) |
| G4 | ✅ PASSED | M23-M24 |
| G5 | ✅ PASSED | M31 |
| G6 | 🟡 **IN PROGRESS** | M27, M32-M33 📍 |
| G6-WP1 | ✅ **COMPLETED** | M31 closeout + working tree consolidation |
| G6-data | ✅ **COMPLETED** | Polygon WebSocket + REST polling + dual-mode feed |
| G7 | ⚪ NOT_STARTED | M34 |
| G8 | ⚪ NOT_STARTED | M35-M36 |
| G9 | ⚪ NOT_STARTED | M37-M38 |

---

# G0: Baseline Veritiera e Riproducibile ✅ PASSED

**Copre:** M00 (Governance) + M01 (Baseline riproducibile)
**Evidenza:** 1600+ test, CI verde, uv.lock, secret scan, ruff/mypy pass

- [x] G0-001 Working tree consolidata e artefatti esclusi
- [x] G0-002 Python 3.12 + Node 24 dichiarati
- [x] G0-003 Installazione da uv.lock verificata
- [x] G0-004 pytest, ruff, ruff format, mypy strict verdi
- [x] G0-005 Secret scan (gitleaks) attivo in CI
- [x] G0-006 Lock Node per dashboard ed Eliza bridge
- [x] G0-007 Audit dipendenze Python (nessuna vulnerabilità nota)
- [x] G0-008 Audit dipendenze Node (0 vulnerability dashboard, 5 low Eliza)
- [x] G0-009 Docker build verificato
- [x] G0-010 Smoke test di import e installazione
- [x] G0-011 CI remota con GitHub Actions configurata
- [x] G0-012 .gitignore, .pre-commit-config.yaml, .gitleaks.toml attivi
- [ ] G0-013 Warning budget CI definito e bloccante
- [ ] G0-014 SBOM Node alla release pipeline
- [ ] G0-015 Report di chiusura G0 pubblicato

---

# G1: Autorità, Ambienti e Confini Applicativi ✅ PASSED

**Copre:** M02 (Configurazione) + M03 (Contratti IC)
**Evidenza:** OracleMode enum, startup guard, credential isolation, contracts inward

- [x] G1-001 OracleMode enum (REPLAY, PAPER, SHADOW, EVALUATION, FUNDED)
- [x] G1-002 Startup guard fail-closed per modalità
- [x] G1-003 Credenziali separate per ambiente
- [x] G1-004 Schema tipizzato credenziali broker
- [x] G1-005 API authentication fail-closed in production
- [x] G1-006 CLI live disabilitata fino a certificazione
- [x] G1-007 PortfolioPlan, TradeIntent, PositionTarget in `application/contracts/`
- [x] G1-008 TradingMode, ExecutionPreference, IntentAction definiti
- [x] G1-009 Test environment crossing
- [x] G1-010 Test configurazione mancante / credenziale errata
- [x] G1-011 Scope read-only per intelligence agents
- [x] G1-012 Scope execution per OMS
- [x] G1-013 Scope emergency per kill switch
- [ ] G1-014 Secrets manager production (interfaccia)
- [ ] G1-015 Rotazione API key Oracle
- [ ] G1-016 Report di chiusura G1 pubblicato

---

# G2: Verità Futures e Point-in-Time Data ✅ PASSED

**Copre:** M04 (Futures domain) + M05 (Sessioni/roll) + M06 (PIT data)
**Evidenza:** ContractSpec, cataloghi CME, calendari, provenance, data quality

- [x] G2-001 ContractSpec con exchange, multiplier, point/tick value, currency
- [x] G2-002 Initial/maintenance margin, settlement type, expiry dates
- [x] G2-003 Catalogo ES/MES, NQ/MNQ, GC/MGC, CL/MCL
- [x] G2-004 Mini/micro equivalence ratio
- [x] G2-005 P&L check contro specifiche exchange
- [x] G2-006 TradingSession, exchange timezone, maintenance break
- [x] G2-007 Holiday calendar CME, DST transition test
- [x] G2-008 Roll policy volume-based e calendar-based
- [x] G2-009 Back-adjustment policy
- [x] G2-010 Continuous → tradable mapping
- [x] G2-011 Expired contract detection
- [x] G2-012 Provenance: event_time, published_at, available_at, ingested_at
- [x] G2-013 Raw → normalized → feature lineage
- [x] G2-014 `as_of` query obbligatoria, no query senza cutoff
- [x] G2-015 Duplicate/gap/outlier detection
- [x] G2-016 Future-news leakage test, macro revision test
- [x] G2-017 PIT data quality test suite
- [x] G2-018 Source license e provider version tracciati
- [ ] G2-019 Catalogo ZN/ZB
- [ ] G2-020 Catalogo 6E/M6E
- [ ] G2-021 Roll cost model
- [ ] G2-022 Intraday futures dataset certificato
- [ ] G2-023 Report di chiusura G2 pubblicato

---

# G3: Ledger, OMS e Reconciliation Durevoli ✅ PASSED (design)

**Copre:** M19 (Ledger) + M20 (OMS) + M21 (Reconciliation)
**Nota:** Gate PASSED per design/implementazione in-memory; la persistenza PostgreSQL production è G6/G7

- [x] G3-001 InMemoryLedger double-entry
- [x] G3-002 InMemoryOMS con idempotency key (intent ID)
- [x] G3-003 TradeIntent → OrderRequest translation
- [x] G3-004 Order/ Fill/ Cancel records definiti
- [x] G3-005 PostgreSQL schema (`db/schema.sql`)
- [x] G3-006 Reconciliation snapshot + startup reconciliation
- [x] G3-007 Mismatch classification (recoverable/fatal)
- [x] G3-008 Aperture bloccate su mismatch, flatten preservato
- [x] G3-009 Duplicate fill handling
- [x] G3-010 Out-of-order event handling
- [x] G3-011 Partial fill persistence
- [x] G3-012 Chaos test suite (kill switch, duplicate fill, out-of-order, broker errors)
- [ ] G3-013 PostgreSQL ledger production (da M32)
- [ ] G3-014 Periodic reconciliation
- [ ] G3-015 Post-fill reconciliation
- [ ] G3-016 Broker open order/position import
- [ ] G3-017 Recovery: idempotency dopo restart
- [ ] G3-018 Recovery: open orders dopo restart
- [ ] G3-019 Report di chiusura G3 pubblicato

---

# G4: Hard Risk Non Bypassabile ✅ PASSED

**Copre:** M23 (Rule catalog) + M24 (Risk kernel)
**Evidenza:** RiskManager obbligatorio, 35 property test, Topstep 50K profile

- [x] G4-001 FirmProgramProfile versionato con hash
- [x] G4-002 SupportMode (AUTO_SUPPORTED, ASSISTED_ONLY, RESEARCH_ONLY)
- [x] G4-003 Topstep Trading Combine 50K profile ufficiale
- [x] G4-004 Static/trailing drawdown, daily loss, contract cap
- [x] G4-005 RiskManager obbligatorio in OrderManager
- [x] G4-006 Fail-closed senza contract spec / protective stop
- [x] G4-007 Per-trade risk budget + contract cap base
- [x] G4-008 Mini-equivalent conversion
- [x] G4-009 Current/pending position exposure
- [x] G4-010 Daily loss continuous, trailing drawdown continuous
- [x] G4-011 News blackout, session gate
- [x] G4-012 Stale-data gate, reconciliation gate, clock-drift gate
- [x] G4-013 Property test su tutti i limiti (35 test)
- [x] G4-014 Golden fixtures per prop-firm profile
- [x] G4-015 Bypass-path audit CLI/API/MAS
- [ ] G4-016 Automation policy details (Topstep ToS)
- [ ] G4-017 Margin buffer enforcement
- [ ] G4-018 Max concurrent/concentration/correlated limits
- [ ] G4-019 Expired-profile fail-closed test
- [ ] G4-020 Report di chiusura G4 pubblicato

---

# G5: Research Truth e Strategy Qualification ✅ PASSED (M31)

**Copre:** M31 (Historical replay)
**Evidenza:** 6 regimi, 48 slice, 0 hard breach, parity broker/ledger, APPROVED

- [x] G5-001 6 regimi: bull, bear, sideways, high_volatility, liquidity_shock, macro_surprise
- [x] G5-002 Matrice 2x2x2: scouts on/off × debate on/off × fund-manager baseline/challenger
- [x] G5-003 Periodi selezionati prima dell'esecuzione (no leakage)
- [x] G5-004 Dati point-in-time verificati, macro PIT hashata
- [x] G5-005 Profilo Topstep 50K certificato per replay
- [x] G5-006 Motore event-driven (`analytics/qualification/`)
- [x] G5-007 Risk gate obbligatorio esercitato
- [x] G5-008 OMS autorevole + ledger riconciliato
- [x] G5-009 Parity economica broker/ledger verificata (48/48)
- [x] G5-010 Luck-vs-skill: pooled OOS moving-block bootstrap
- [x] G5-011 Metriche: return, Sharpe, Sortino, Calmar, drawdown, turnover, cost
- [x] G5-012 0 hard breach, 0 mismatch, 0 slice non-flat
- [x] G5-013 Report di chiusura M31 pubblicato

---

# G6: Paper & Shadow Operations 🟡 IN PROGRESS 📍

**Copre:** M27 (Paper broker realism) + M32 (Paper trading) + M33 (Shadow trading)
**Dependency:** G3, G4, G5
**Exit:** 60 sessioni paper + 30 sessioni shadow senza incidente hard

## G6-WP1: Consolidamento Working Tree & M31 Closeout (immediato)

- [x] `G6-001` Committare M31 closeout: qualification engine, report, config, policy
- [x] `G6-002` Aggiornare `ORACLE_AUTOPILOT_STATUS.md` con stato M31/M32
- [ ] `G6-003` Push e verifica CI remota

## G6-WP2: M32 — Live Paper Trading

- [x] `M32-001` Creare account paper dedicato (.env configurato)
- [x] `M32-002` Verificare feed live paper (Polygon REST polling ✅)
- [x] `M32-003` Verificare broker clock (PaperBroker + Polygon timestamps)
- [x] `M32-004` Verificare ledger bootstrap (InMemoryLedger testato)
- [x] `M32-005` Verificare OMS bootstrap (InMemoryOMS via PaperBroker)
- [x] `M32-006` Verificare reconciliation startup (`848d28b`, test broker/OMS/ledger)
- [x] `M32-007` Eseguire prima sessione read-only (run_paper_session.py ✅)
- [x] `M32-008` Eseguire prima sessione con segnali (SMA crossover ✅)
- [x] `M32-009` Eseguire prima sessione con ordini paper (PaperBroker ✅)
- [ ] `M32-010` Verificare stop e bracket
- [ ] `M32-011` Verificare session flatten
- [ ] `M32-012` Verificare daily rollover
- [ ] `M32-013` Verificare restart intraday
- [ ] `M32-014` Verificare reconnect intraday
- [ ] `M32-015` Verificare LLM provider outage
- [ ] `M32-016` Verificare Eliza outage
- [ ] `M32-017` Verificare stale feed response
- [ ] `M32-018` Verificare risk alert response
- [ ] `M32-019` Verificare extreme-market conference
- [ ] `M32-020` Misurare paper fill realism
- [ ] `M32-021` Misurare decision stability
- [ ] `M32-022` Misurare alpha decay
- [ ] `M32-023` Completare sessanta sessioni
- [ ] `M32-024` Approvare o respingere paper gate
- [ ] `M32-025` Pubblicare il report di chiusura M32

## G6-WP3: M33 — Shadow Trading (dopo M32)

- [ ] `M33-001` Creare credenziali broker read-only
- [ ] `M33-002` Bloccare submit nel broker adapter shadow
- [ ] `M33-003` Importare posizioni reali read-only
- [ ] `M33-004` Importare ordini reali read-only
- [ ] `M33-005` Importare account values read-only
- [ ] `M33-006` Generare shadow TradeIntent
- [ ] `M33-007` Simulare shadow fills
- [ ] `M33-008` Stimare achievable fills
- [ ] `M33-009` Confrontare paper e shadow spread
- [ ] `M33-010` Confrontare paper e shadow latency
- [ ] `M33-011` Confrontare paper e shadow slippage
- [ ] `M33-012` Verificare prop limits read-only
- [ ] `M33-013` Verificare session rules read-only
- [ ] `M33-014` Verificare news rules read-only
- [ ] `M33-015` Eseguire restart recovery
- [ ] `M33-016` Eseguire broker disconnect drill
- [ ] `M33-017` Eseguire data disagreement drill
- [ ] `M33-018` Eseguire kill-switch dry run
- [ ] `M33-019` Completare trenta sessioni shadow
- [ ] `M33-020` Calcolare live-parity error
- [ ] `M33-021` Calcolare expected violation probability
- [ ] `M33-022` Calcolare expected challenge value
- [ ] `M33-023` Chiudere parity gaps
- [ ] `M33-024` Approvare o respingere shadow gate
- [ ] `M33-025` Pubblicare il report di chiusura M33

### G6 Work package paralleli (completamento G3/G4 per persistenza)

- [x] `G6-101` PostgreSQL ledger writer persistente (da InMemoryLedger, `de5b4cc`)
- [x] `G6-102` PostgreSQL OMS writer persistente (da InMemoryOMS, `de5b4cc`)
- [ ] `G6-103` Recovery: request idempotency dopo restart
- [ ] `G6-104` Recovery: open orders dopo restart
- [ ] `G6-105` Periodic reconciliation worker
- [ ] `G6-106` Margin buffer enforcement (risk kernel)
- [ ] `G6-107` Adapter futures certificato per paper (selezionare broker)

---

# G7: Certificazione Programma Prop-Firm ⚪ NOT_STARTED

**Copre:** M34 (Evaluation rollout)
**Dependency:** G6
**Exit:** Evaluation completata senza violazioni software

- [ ] `M34-001` Congelare firm/program/profile version
- [ ] `M34-002` Congelare broker adapter version
- [ ] `M34-003` Congelare model registry version
- [ ] `M34-004` Congelare strategy set
- [ ] `M34-005` Congelare risk configuration
- [ ] `M34-006` Creare evaluation account
- [ ] `M34-007` Verificare account rules con fonte ufficiale
- [ ] `M34-008` Verificare automation permission
- [ ] `M34-009` Verificare product allowlist
- [ ] `M34-010` Eseguire preflight checklist
- [ ] `M34-011` Abilitare evaluation mode
- [ ] `M34-012` Monitorare ogni sessione
- [ ] `M34-013` Eseguire daily reconciliation review
- [ ] `M34-014` Eseguire daily risk review
- [ ] `M34-015` Eseguire daily model review
- [ ] `M34-016` Bloccare configurazione durante sessione
- [ ] `M34-017` Registrare ogni manual intervention
- [ ] `M34-018` Gestire eventuale rule change
- [ ] `M34-019` Gestire eventuale platform outage
- [ ] `M34-020` Gestire eventuale strategy pause
- [ ] `M34-021` Completare evaluation o stop condition
- [ ] `M34-022` Separare software breach da market loss
- [ ] `M34-023` Eseguire evaluation post-mortem
- [ ] `M34-024` Approvare o respingere funded promotion
- [ ] `M34-025` Pubblicare il report di chiusura M34

---

# G8: Funded Account Rollout ⚪ NOT_STARTED

**Copre:** M35 (Funded) + M36 (Scaling)
**Dependency:** G7

- [ ] `M35-001`–`M35-025` Funded account minimum-size rollout (25 task)
- [ ] `M36-001`–`M36-025` Scaling e multi-account (25 task)

---

# G9: Continuous Operations ⚪ NOT_STARTED

**Copre:** M37 (Certification) + M38 (Operations)
**Dependency:** G8

- [ ] `M37-001`–`M37-025` Production certification manifest (25 task)
- [ ] `M38-001`–`M38-025` Continuous operations process (25 task)

---

## Appendice: Lane Intelligence (non bloccanti)

Queste lane NON bloccano G6-G9. Possono procedere in parallelo ma non acquisiscono autorità di execution.

| Area | Backlog rif. | Stato |
|:-----|:------------:|:-----:|
| LLM Gateway production | M10 | 0% — da avviare dopo G6 |
| Eliza scouts autonomi | M09 | 0% — da avviare dopo G6 |
| Meeting scheduler | M15 | 0% — non bloccante |
| Execution LLM Agent | M26 | 0% — non bloccante |
| Alpha research pipeline | M17 | 0% — non bloccante |
| Backtest integrity avanzato | M16 (30% residuo) | Post-G6 |
| Memory & embedding retrieval | M14 (64% residuo) | Post-G6 |

---

## Stop Conditions

Il progetto torna PAUSED quando:
- una suite hard-risk fallisce
- mismatch broker/ledger non risolto
- regola firm incerta o scaduta
- vulnerabilità high/critical nel percorso live
- kill switch o flatten non verificabili
- paper/shadow model diverge oltre tolerance approvata
- edge non positivo OOS netto costi
- condizioni violano termini della firm
- modello o plugin non riproducibile/versionato
