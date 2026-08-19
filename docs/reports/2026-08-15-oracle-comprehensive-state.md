# Oracle Trading — Report Completo per Consulenza Strategica

> **Data**: 2026-08-15
> **Scope**: assessment integrale del progetto oracle-trading per richiesta consulenza esterna + input a deep-research su "refactor vs redesign"
> **Obiettivo dichiarato dall'operatore**: 5%/mese costante (minimo), possibilmente di più, per vivere di trading prop-firm (The5ers/Lucid/MyFundedFutures) e gestire portfoli propri + di clienti
> **Metodo**: ogni claim è verificato `file:line`. Ogni verdetto (PASSED/REJECTED/PARTIAL) è tratto da report versionati. Sintesi onesta, non goffrata.
> **Struttura**: 13 sezioni. Lettura minima consigliata per il consulente: §1 (executive), §4 (gate status), §8 (edge status), §10 (fattibilità 5%/mese), §11 (refactor vs redesign), §12 (question).

---

## 1. Executive Summary

Oracle è un sistema di trading sistematico multi-agente Python (~131K righe, 916 file, 2.697 test) costruito da un operatore singolo (Alin) con architettura **istituzionale** (PostgreSQL ledger/OMS, recovery, reconciliation, policy prop-firm versionato, GA, multi-agent LangGraph, NautilusTrader/vectorbt dual-engine, ElizaOS bridge, dashboard React).

**Stato reale (2026-08-15)**: l'architettura safety-critical è sana e **G0-G4 PASSED** (baseline, autorità/ambienti, ledger/OMS, hard risk). Ma **G5 (research truth) è REJECTED** — l'edge misurato è α ≈ 0 netto costi (+2-6% lordo annuo trend, "beta scambiato per alpha"), confermato da 4 fasi indipendenti di testing onesto (Fase 5, 5b, 5c, multi-asset walk-forward 0/9). **G6 (paper ops) REJECTED** con 0 trade prodotti in 30/30 sessioni post-fix. Live trading **DISABLED** fino a G7.

**Tre gap infrastrutturali critici** identificati e **chiusi il 2026-08-10**: (1) lookahead bias FRED → risolto con `vintage=` parameter (ALFRED PIT); (2) `paper_limit_penetration_ticks` + `paper_tick_size` per pessimistic-fill risolto; (3) cvxpy "morto" → KEEP documentato (dipendenza viva di `pyportfolioopt`, sarà cablato in S1.2 per sizing Lane A).

**Verdetto onesto su 5%/mese**: NON è realistico con l'edge attuale. Per €3K/mese netti su singolo account 50K serve α ≥ 118,9%/anno; su 5-7 account 150-200K serve α ≥ 39,6-59,5%/anno. Il soffitto misurato è +2-6% lordo annuo (≈0 netto) → **gap di 5-16×**. La lane daily è economicamente morta per canale prop-firm. L'unica via è cambio di canale (intraday 5-30m + multi-asset + sizing dinamico), che richiede dati nuovi (IBKR/Databento — setup manuale operatore) e 2-3 mesi di lavoro focalizzato.

**Refactor vs redesign**: l'architettura è sana e NON va ridisegnata. Il gap è l'edge, non i mattoni. Servono (a) una strategia con edge reale in un canale dove esiste, (b) cablare i componenti esistenti in un loop chiuso (GA → paper → reconcile → decay → replace), (c) dati intraday nuovi. **Redesign logico** (non architetturale): ridefinire la lane attiva da "daily ES trend-following" (falsificato) a "Lane A (PAC multi-asset) + Lane B (turnaround) + Lane C (intraday subordinato)" del piano profittevole.

**Raccomandazione**: prima consulenza esterna su strategia/edge (non su architettura), poi deep-research su "qual è il canale in cui un operatore singolo con questo stack ha la massima probabilità di produrre edge statisticamente onesto nei prossimi 6 mesi", con N onesto, walk-forward anti-beta, costi aggressivi.

---

## 2. Identità e Obiettivo

### 2.1 Chi
- **Operatore**: Alin, sviluppatore singolo (roma, background informatica; trader per obiettivo reddito, non per hobby)
- **Stack tecnico personale**: Python 3.12, LangGraph, vectorbt, NautilusTrader, polars, DEAP (GA), PostgreSQL, NATS/JetStream, React, FastAPI, ElizaOS
- **Repo**: `/home/alin/_repos/oracle-trading` su GitHub, licenza MIT, 916 file Python, ~131K righe, 2.697 test (2697 passed al 2026-08-10)
- **Linee guida fondanti**: `docs/ADR/` (16 ADR normativi); `docs/ARCHITECTURE.md` (living); `docs/SPECIFICATION.md` (FROZEN storico v1.0)

### 2.2 Cosa
Oracle è una **piattaforma di ricerca quantitativa** con:
- **Piano di controllo deterministico** (mode guard, rule resolver, hard risk kernel, OMS durevole, ledger PostgreSQL)
- **Piano di intelligence LLM/agenti** (LangGraph multi-agent: analysts→debate→decision, LLM researcher, GA evolution, ElizaOS bridge)
- **Piano di ricerca** (vectorbt discovery + NautilusTrader qualification, walk-forward, MC, stress gauntlet, experiment registry)

La regola fondante (ADR-010): **"LLM = consulente, mai decisore"**. Gli LLM propongono, dibattono, sintetizzano; ogni decisione numerica (entry/stop/qty/risk) passa attraverso codice deterministico validato. Fail-closed di default.

### 2.3 Perché
Vivere di trading prop-firm. L'operatore vuole raggiungere **5%/mese costante** (60%/anno netto) per:
- Passare challenge The5ers/Lucid/MyFundedFutures e ottenere conti funded
- Cumulare più conti funded (5-20) per moltiplicare il capitale gestibile
- Costruire track record che permetta di gestire portfoli propri + (futuro) di clienti

### 2.4 Regole prop-firm target
- **The5ers Bootcamp** (MT5/CFD, 3-step eval 6%/5% DD, funded 5%/3% daily/4% overall, leva 1:30, overnight+weekend OK, EA OK, ~$95 entry)
- **Lucid LucidPro** (futures CME, intraday-only NO overnight, EOD trailing 4% DD, 6% target, 90/10 split, 40% consistency funded, $129.50/50K)
- **MyFundedFutures** (AUTO_SUPPORTED, candidato per il primo live test)

Dettagli completi in `docs/ADR/ADR-013-versioned-prop-firm-rule-catalog.md` + memory `propfirm-rules.md`.

---

## 3. Architettura Living (post ADR-008)

### 3.1 Forma reale
Modular monolith Python in evoluzione, NON microservizi. Le chiamate in-process dominano la hot path; NATS è trasporto asincrono per audit/fan-out, NON bus universale (ADR-001 SUPERSEDED da ADR-008). PostgreSQL è source-of-truth per ledger/OMS/account; Parquet+DuckDB per research; QuestDB e Qdrant sono DEFERRED (in config ma non runtime).

### 3.2 Quattro piani (target ARCHITECTURE.md §4)

1. **Intelligence plane** — LLM, analysts, Eliza, GA producono "decision contract" versionato con confidence/scadenza/provenance. Non possiedono credenziali broker. Non calcolano hard risk.
2. **Safety control plane** — mode guard, rule profile resolution, quantity da ContractSpec, hard risk, intent/order durevoli, idempotency/outbox, reconciliation, cancel/flatten. NON dipende da LLM/Eliza/dashboard/GA.
3. **Research plane** — dataset PIT, backtest discovery+qualification, WFA/holdout/stress, experiment registry, strategy promotion. NON scrive nel ledger operativo.
4. **Operations plane** — API auth, dashboard read-model, metrics/tracing, DR.

### 3.3 Data flow (come scorre un trade, ADR-010 sequence)

1. LLM/Strategy emette `PortfolioPlan`/`TradeIntent`
2. Application valida mode, schema, expiry, snapshot IDs
3. Rule+Risk genera pre-trade context
4. Risk kernel ritorna `ALLOW` o `DENY` con `reason + profile_version`
5. Se DENY/uncertain → `NO_TRADE`/`PAUSE`
6. Se ALLOW → OMS persiste intent + idempotency key
7. OMS submit → Broker port
8. Broker ritorna ack/fill/reject
9. OMS persiste evento
10. Ledger/Reconciliation persiste event e riconcilia broker
11. Ledger ritorna `AccountSnapshot` autorevole ad Application

Dopo commit, transactional outbox pubblica eventi asincroni su NATS per audit/metrics/external integrations. NATS **non** sta nella hot path mode→risk→OMS→broker.

### 3.4 Regola di dipendenza (inward-only)
- `core/domain` — value object, enum, eventi, invarianti; NESSUN import da apps/agents/analytics/execution/policy
- `application/contracts` — `PortfolioPlan`, `TradeIntent`, `AccountSnapshot`, `RuleDecision`
- `application/services` — use case deterministici
- `adapters` — broker, database, data provider, NATS, LLM
- `apps` — composition root CLI/API/worker

Violazioni note (`docs/ARCHITECTURE.md:30-55`):
- execution importa contratti dal package agents
- policy importa tipi da execution
- analytics e market si importano in entrambe le direzioni
- analytics importa execution
- genetics dipende da analytics; agents dipende da genetics

### 3.5 State authority matrix
| Dato | SoT target | Dev/test | Non autorevole |
|---|---|---|---|
| Account/balance/equity/margin | PostgreSQL ledger | SQLite | Redis, NATS, dashboard |
| Order e fill | PostgreSQL OMS | SQLite | process memory, JSON |
| Position | Ledger riconciliato | SQLite | agent state |
| Rule profile | Versioned immutable catalog | Fixture file | pagina web live |
| Raw market/news | Immutable dataset/object store | file fixture | cache |
| Feature research | Parquet + metadata catalog | Parquet | Redis |
| Experiment | Registry PG/SQLite + artifact manifest | SQLite | filename |
| Prompt/model run | Audit store | SQLite | log console |
| Cache | Redis/in-memory | in-memory | MAI source of truth |

### 3.6 Componenti aspirational vs in_use vs deferred
| Componente | Stato | Note |
|---|---|---|
| PostgreSQL | IN_USE (G3 attivo dal 25-lug) | OMS/ledger/outbox; solo con `--storage=postgres` |
| Redis | IN_USE (Compose) | cache, ricostruibile |
| SQLite | IN_USE (default dev) | path in-memory ancora default |
| Parquet + metadata catalog | IN_USE | feature research SoT |
| NATS | IN_USE ma non universale | fan-out audit/integration; non sostituisce DB; non in hot path |
| QuestDB | DEFERRED | in Compose solo config; adottato solo se benchmark SLO fallisce su Parquet/DuckDB+PG |
| Qdrant | DEFERRED | nessun retrieval semantico in hot path risk/execution; use case intelligence richiede ADR |
| Rust core (PyO3 order book) | DEFERRED/ASPIRATIONAL | non implementato; paper broker è Python puro |
| ElizaOS bridge (TS) | IN_USE (bridge) | dashboard React + FastAPI + CLI dominano |
| Loki/Prometheus | ASPIRATIONAL | in config Compose, non costituiscono runtime autorevole |

---

## 4. Stato Gate-by-Gate (G0-G9)

> Fonte autoritativa: `docs/ORACLE_AUTOPILOT_STATUS.md:35-45`. ADR-012 ha sostituito le "Phase 0-6" con capability gate G0-G9 basati su evidenza.

| Gate | Stato | Evidenza | Limite noto |
|---|---|---|---|
| G0 baseline | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan, warning budget (42/350 locale) | — |
| G1 autorità/ambienti | ✅ PASSED | mode guard, startup fail-closed, credential isolation, CLI guard | `OrderManager` ammetteva `risk_manager=None` (BL-040) — ora RISOLTO (`execution/order_manager/manager.py:30` rifiuta None) |
| G2 contract data | 🟡 PARTIAL | ContractSpec, CME calendars, roll, PIT detection; BL-301 lake operativo; BL-307 lineage completo (68.975 partizioni, 0 dangling) | BL-052: intraday futures 1m/5m/15m mancanti (lake ha solo ~8 giorni) |
| G3 ledger/OMS | ✅ PASSED | PostgreSQL path attivo dal 25-lug (`ffe91b4`); RecoveryService + ReconciliationWorker + idempotency; restart senza perdita/dup | persistenza Postgres solo con `--storage=postgres`; default memory |
| G4 hard risk | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit | `PropFirmOrderRiskAdapter` cablato in CLI; paper harness non lo usa pienamente |
| **G5 research truth** | ❌ **REJECTED** | run ufficiale ADR-016 (Fase 5, 48 obs): median Sharpe **−0.251** < 0.5; 0 hard breach; `luck p=1.0` → nessun edge statistico. Canonico `m31-rerun-final`: median Sharpe **−2.51**, N=8 < 48. 8/8 candidati Fase 5c REJECTED. 0/9 multi-asset walk-forward battono buy&hold | **α residuo trend +2-6% lordo → ~0 netto costi (BL-093/BL-094)** |
| **G6 paper ops** | 🟡 **REJECTED** | M32a originale 23/30 (77%); post-fix 30/30 ma con **0 trade, 0 P&L, Sharpe 0** (BL-024); Sprint 1 AdaptiveEnsemble: pass rate 10% (peggio) | manca run qualificante trade-producing |
| G6-I feedback loop | 🟡 PARTIAL | Factor Timing v1 (26 test), Lorentzian causal-fix (6 test), Regime Ensemble (14 test) | nessun gate end-to-end; Lorentzian mai trigger dominante; ML classifier 36,5% accuracy |
| G7 programm prop-firm | ⚪ NOT_STARTED | block su G5+G6 | ADR-015 Topstep AUTO_SUPPORTED solo se local-only, no VPS; MFF = candidato |
| G8 funded limited | ⚪ NOT_STARTED | — | — |
| G9 continuous ops | ⚊ NOT_STARTED | — | — |

> **NOTA G5 (aggiornamento S0)**: l'autopsia BL-093 + modello economico BL-094 hanno stabilito che l'α misurato è ≈0 netto costi (beta scambiato per alpha) e che la lane daily è economicamente morta. Prima di G5/G6 serve un cambio di canale (multi-asset, sweep candidati, orizzonte >1d), non tuning.

### 4.1 Risultati M32a WP2 (verifica 25-lug)
Eseguito: `python scripts/run_g6_wp2_paper_sessions.py --sessions 30 --data data/ohlcv/ES_1d.parquet --storage memory`

| Metrica | Target | Risultato |
|---|---|---|
| pass_rate | ≥ 0.90 | **0.77** (23/30) ❌ |
| mean_sharpe | ≥ −0.5 | −0.31 ✅ (borderline) |
| mean_max_dd | ≤ 3.0% | 1.54% ✅ |
| reconcile_clean_rate | = 1.0 | 1.00 ✅ |

Decisione: REJECTED. Causa: regime choppy-biased (29/30 mean_rev per default `_sma_regime_heuristic`).

### 4.2 Distribuzione regime (M32a)
| Regime | n sessioni | Specialist attivo | Pass rate |
|---|---|---|---|
| choppy | 29 | mean_rev | 21/29 (72%) |
| volatile | 1 | breakout | 1/1 (100%) |

---

## 5. Sintesi ADR (16 decisioni normative)

> Indice normativo: `docs/ADR/README.md`. 12/16 ADR REALITY (verificati su codice); 4 parzialmente ASPIRATIONAL.

### 5.1 Inventario
| ADR | Titolo | Status | Data | Asp/Reale | Decisione chiave |
|---|---|---|---|---|---|
| 001 | NATS event bus universale | SUPERSEDED | 2026-07-06 | Reale | NATS come bus unico → ridotto a trasporto asincrono di boundary da ADR-008 |
| 002 | QuestDB tick storage | SUPERSEDED | 2026-07-06 | Reale (DEFERRED) | QuestDB come TSDB primario → adozione benchmark-driven, PostgreSQL SoT production |
| 003 | Policy engine embedded | ACCEPTED | 2026-07-06 | Reale | Libreria in-process invece di microservizio; `policy/prop_firm/` esiste |
| 004 | Plugin-first universale | SUPERSEDED | 2026-07-06 | Reale | Plugin lifecycle → ridotto a extension point non safety-critical da ADR-008 |
| 005 | Monorepo apps/services/libraries/plugins | SUPERSEDED | 2026-07-06 | Aspirational | Struttura 4-dir → repo reale usa package coesi; nessuna dir `services/` o `libraries/` |
| 006 | Genome pipeline (6 moduli) | ACCEPTED, RESEARCH-ONLY | 2026-07-06 | Parziale | Genome = universe/feature/signal/filter/risk/execution; `genetics/` esiste ma non autorizza promotion |
| 007 | Experiment registry | ACCEPTED | 2026-07-06 | Parziale | Schema YAML/PG/SQLite dichiarato; realtà: registry multipli frammentati, non un record centrale |
| 008 | Modular monolith + authority boundaries | ACCEPTED | 2026-07-18 | Reale | Supersede 001/004/005; mode→risk→OMS→broker in-process |
| 009 | Data e state storage strategy | ACCEPTED | 2026-07-18 | Reale | PostgreSQL SoT per ledger/OMS; Parquet+DuckDB per research; QuestDB/Qdrant DEFERRED |
| 010 | Deterministic execution safety boundary | ACCEPTED | 2026-07-18 | Reale | LLM produce evidence/Intent; mode guard, risk, OMS obbligatori; live bloccato fino a G7 |
| 011 | Discovery vs qualification backtest | ACCEPTED | 2026-07-18 | Parziale | Lane vectorized per discovery, nautilus candidato per qualification; PyBroker DEPRECATED ma ancora presente |
| 012 | Capability gates replace phases | ACCEPTED | 2026-07-18 | Reale | Gate G0-G9 con entry/exit evidence; piani Phase archiviati come storico non normativo |
| 013 | Versioned prop-firm rule catalog | ACCEPTED | 2026-07-18 | Reale | Profili immutabili per firm/program/stage/platform/vintage; default UNSUPPORTED |
| 014 | M31 evidence loss | ACCEPTED | 2026-07-23 | Reale | regime.py mai committato; hash dataset divergente; G5 dichiarato NOT_STARTED; data hash nel report header |
| 015 | Topstep automation policy | ACCEPTED | 2026-07-25 | Reale | Topstep = AUTO_SUPPORTED solo con local-only deployment, single-tenant, no VPS; default RESEARCH_ONLY |
| 016 | G5 re-spec stop ATR 1x, qty 1, N onesto | ACCEPTED | 2026-08-03 | Reale | Stop ATR 1x (period 14), qty 1-only, daily primario, 6 regimi, `luck_p_value` nel gate, Sharpe ≥ 0.5, DD ≤ 4% |

### 5.2 Shift direzionali maggiori
- **NATS-as-universal-bus → modular monolith** (ADR-008 supersede 001/004/005): il reset del 18-lug riconosce che forzare ogni interazione su NATS aumenterebbe failure mode. NATS resta trasporto, non source of truth.
- **QuestDB-primario → PostgreSQL SoT + TSDB DEFERRED** (ADR-009 supersede 002): autorità transazionale = una sola (PostgreSQL). TSDB adozione benchmark-driven.
- **Phase plans → Capability gates G0-G9** (ADR-012): il vecchio master backlog (39 milestone, 975 task) era "falsa completezza" senza ledger o contract math. I gate sono basati su evidenza.
- **LLM-in-hot-path → LLM-produces-evidence-only** (ADR-010): separazione hard tra intelligence (LLM/Eliza/GA) e execution deterministica. "Zero bypass, fail-closed".
- **Beta-as-alpha → anti-beta benchmark** (ADR-016): la lezione di G5 REJECTED porta a un re-spec esplicito dei parametri di qualifica.

### 5.3 ADR-016 parametri esatti (anti-beta benchmark)
- **Stop**: ATR 1x (period 14, point-in-time, calcolato sul prefix, mai lookahead). Fixed 30pt resta disponibile con qty 2.
- **Qty**: 1-only con stop ATR. N onesto = regimi × finestre × qty.
- **Timeframe primario**: daily (ES 1d, 6522 bar, 2913 ≥ 2015). ES 1h solo come holdout cross-check.
- **Soglie**: Sharpe ≥ 0.5; `luck_p_value` entra nel gate; DD ≤ 4% ridefinito con liquidazione al primo hard breach.
- **Regimi**: 6/6 (bull/bear/sideways/high_vol/liq_shock/macro_surprise).
- **N onesto**: top-3 finestre per regime × 1 qty = 18 curve uniche.
- **Risultato run ufficiale (Fase 5, 48 obs)**: median Sharpe **−0.251**, 0 hard breach, luck p=1.0 → **nessun edge statistico**.

### 5.4 Verdetto governance
L'ADR set è sano. Tre ADR fondativi (001/002/004/005) SUPERSEDED da un ADR-008 autocosciente; un ADR-014 di incident-response che dichiara REGRESSED il proprio claim di riproducibilità senza giustificare o nascondere; un ADR-016 di re-spec che rende espliciti i parametri anti-beta. 12/16 ADR verificati REALITY su codice.

Gap tra ADR e codice (4 ADR): ADR-005 (struttura apps/services/libraries/plugins), ADR-006 (genome non autorizza promotion), ADR-007 (registry multipli frammentati), ADR-011 (PyBroker deprecato ma presente in `experiments/scripts/run_ga_pybroker.py`).

**Ricaduta su 5%/mese**: la governance NON è il blocker. Il blocker è l'edge.

---

## 6. Sintesi Piani (18 documenti strategici)

### 6.1 Inventario
| Piano | Scope | Status | Deliverable | Blocker |
|---|---|---|---|---|
| `plans/README.md` | Indice archivio | CANONICAL | Mappa phase→gate, regole archivio | — |
| `oracle-autopilot-atomic-backlog-v1.md` | M00-M38, 950+ task | DEPRECATED (ADR-012) | Backlog storico non eseguibile | Sostituito da gate-backlog-v2 |
| `oracle-autopilot-gate-backlog-v2.md` | G0-G9 | SUPERSEDED (stale) | Matrice gate/stato | Dice G5 PASSED — in realtà REJECTED |
| `phase0-plan.md` ... `phase6-plan.md` | Foundation, analytics, backtest, GA, MAS, exec, dashboard | DEPRECATED | Moduli `analytics/`, `agents/`, `execution/`, `apps/` | Sostituiti da gate G0-G9 |
| `phase3.5/3.5.1-plan.md` | Signal optimization, GA convergence fix | DEPRECATED | Fix KNN, GA wiring | — |
| `plan-expression-alpha.md` | GP expression alpha + intraday crypto + pair trading | DEPRECATED | 3 direttrici parallele | — |
| `testing-report.md` | Test coverage, CI pipeline | STORICO (2026-07-19) | 105 test file, ratio 0.78 | analytics 0.31, api 0.06, integration 0 |
| `BL-023-m31-g5-recovery.md` | Diagnosi G5 REJECT + fix runner M31 | DRAFT→ADR-014/016 | 4 fix misura, re-spec G5 | 0 trade post-fix |
| `plan-production-grade.md` | S0-S6 production-grade | **APPROVED** 2026-08-05 | Diagnosi, governance, gate, DX | 3 gap infra + α ≈ 0 |
| `plan-profitable-system.md` | Lane A/B/C strategic pivot | DRAFT 2026-08-10 | PAC core + turnaround + scalping subordinato | Dati intraday + universo azionario + pessimistic-fill |

### 6.2 Critical path (presente → 5%/mese)
1. **Presente → G5 onesto**: il run `18a6836` è INVALIDO (stop 5pt su MES=$25, warmup dopo il periodo, 8 varianti identiche, 6° regime inesistente). Fix F1-F5 + 11bis (contabilità futures) completati, ma ensemble v2 min_conf=0.5 produce 0 trade nelle finestre M31 → **G5 REJECTED onesto**. Re-spec ADR-016.
2. **G5 → G6**: nessun paper run su segnali già falsificati. BL-024 rivisto: 250 sessioni, guardia zero-trade FATAL, mean_sharpe > 0 (non ≥ −0.5), per-window guard + floor totale, `_verify_pin_hash` FATAL.
3. **G6 → G7**: vertical slice esecuzione prop-firm presto (S3.3) SENZA pretendere che validi α; ADR-015 Topstep automation policy ACCEPTED.
4. **Bloccanti trasversali**: (i) FRED lookahead + fondamentali senza vintage — invalidano qualunque verdetto macro-conditional; (ii) cvxpy installato ma 0 import — necessario per Lane A sizing; (iii) fill-on-touch senza queue position.
5. **Setup manuale operatore**: BL-097 backfill IBKR (login gateway) + BL-098 Databento (API key) per dati intraday; BL-099 equities intraday o daily yahoo/polygon per universo azionario Lane B.

### 6.3 Piani attivi vs obsoleti
**Vivi al 2026-08** (3 soli):
- `plan-production-grade.md` (APPROVED 2026-08-05) — piano S0-S6 corrente, 58 decisioni audit-trail
- `plan-profitable-system.md` (2026-08-10) — strategic pivot Lane A/B/C
- `BL-023-m31-g5-recovery.md` — chiuso nei fix F1-F5 e negli ADR-014/016

**Obsoleti** (15, con header "ARCHIVIO STORICO"):
- Tutti i `phase{0..6}-plan.md` + `phase3.5/3.5.1` + `phase4-tasks` + `plan-expression-alpha` + `oracle-autopilot-atomic-backlog-v1` — deprecati da ADR-012
- `oracle-autopilot-gate-backlog-v2.md` — stale: dice "G5 ✅ PASSED M31" (line 49, 192-210) ma BL-023 ha dimostrato che il run era INVALIDO

### 6.4 Contraddizione principale
`gate-backlog-v2.md:49` dice "G5 ✅ PASSED M31" mentre `plan-production-grade.md:5-7` dice "G5 REJECTED" — il gate-backlog è stale e non aggiornato post-BL-023.

---

## 7. Sintesi Report Sperimentali (evidenza)

### 7.1 Inventario
| Report | Data | Scope | Verdetto | Metriche chiave |
|---|---|---|---|---|
| `quant-finance-analysis.md` | 2026-07-30 | Audit stack quant | RESEARCH-GRADE | Sharpe 207.84 su 10 bar = artefatto; embargo non cablato; parity test vuoto |
| `live-readiness-gap-analysis.md` | 2026-08-10 | 5 falle paper→live | 3/3 chiusi | FRED vintage ✓, pessimistic-fill ✓, cvxpy KEEP |
| `s0-1-bl023-autopsy.md` | 2026-08-05 | Autopsia BL-023 | REJECTED | 6 assi analizzati; causa principale = beta scambiato per alpha |
| `s0-2-economic-model.md` | 2026-08-05 | Modello economico prop-firm | LANE DAILY MORTA | €3K/mese richiede 5-16× il soffitto |
| `m31-rerun-final/m31.{json,md}` | 2026-08-10 | M31 canonico (ensemble v2, N onesto) | REJECTED | median Sharpe **−2.51**, N=8 < 48, 1 curva unica |
| `m31-rerun/m31.md` | 2026-08-04 | M31 re-run regime ribilanciato | REJECTED | Sharpe −0.314, DD 5.63%, luck p 1.0, N=136/17 curve |
| `m31-historical-replay-qualification.md` | 2026-07-30 | Primo replay M31 | REJECTED | Sharpe −1.15, DD 12.7%, 48 hard breach |
| `2026-07-19-m31-closeout.md` | 2026-07-19 | Closeout M31 (invalidato) | APPROVED→INVALID | Sharpe 1.013 poi smentito da ADR-014 |
| `candidates/*.md` (8) | 2026-08-04 | Sweep 8 candidati Fase 5c | 8/8 REJECTED | migliore donchian Sharpe +0.216, 16 breach, DD 4.77% |
| `multiasset/walkforward.{json,md}` | 2026-08-04 | WF multi-asset ES/SPY/BTC | 0/9 vs buy&hold | S_test +0.74..+1.33 < BH_S; α +2.3-6.1% lordo |
| `g6-wp2-final/g6-wp2-final.md` | 2026-07-25 | Paper post-fix 30 sessioni | PARTIAL→REJECTED | 30/30 pass, ma 0 trade, 0 P&L, Sharpe 0 |
| `2026-07-23-m32a-post-beta.md` | 2026-07-23 | M32a post-beta OMS/ledger | TECHNICAL PASS | 20/20 pass, DD 0.21%, P&L +$293 (non edge) |
| `edge-portfolio/edge-portfolio.md` | 2026-07-25 | Probe 16 strategie (BL-200) | PROBE | roc_momentum_12 mc=41% ma 100% WR (overfit sospetto) |
| `signal-candidates/signal-candidates.json` | 2026-08-03 | Probe 8 candidati train/holdout | 8/8 VIABLE | holdout WR 0.61-0.75 (probe, non gate) |
| `import-graph-analysis-20260730.md` | 2026-07-30 | Audit dipendenze | 22 violazioni | 7 HIGH, 12 MEDIUM, 1 ciclo reale analytics↔market |
| `s0-2/eval_economics.json` | 2026-08-05 | MC sintetico p(pass) | base rate 30% | α=0/σ=1.2% → 30.1%; α=6%/σ=1.2% → 33.7% |
| `s0-2/eval_simulation.json` | 2026-08-05 | Replay empirico p(pass) ES 1d | REJECTED | 23-30% vs 60% richiesto; CI sup 40% |

### 7.2 Risultati chiave (REJECTED/PASSED)
- **G5 REJECTED (4 fasi indipendenti)**: M31 closeout 19-lug APPROVED (Sharpe 1.013) invalidato da ADR-014; re-run canonico 30-lug REJECTED (Sharpe −1.15, DD 12.7%, 48 hard breach); Fase 5 onesto REJECTED (Sharpe −0.251, return −1.22%, luck p 1.0); Fase 5b REJECTED (17 curve, Sharpe −0.31, DD 5.63%); Fase 5c 8/8 REJECTED (migliore donchian Sharpe +0.216, 16 breach, DD 4.77%).
- **M31 rerun-final canonico REJECTED**: median Sharpe **−2.51** (soglia ≥0.5), N=8 osservazioni vs ≥48 richieste, 1 curva unica.
- **Walk-forward multi-asset 0/9**: nessun segnale batte buy&hold su ES/SPY/BTCUSDT (test ≥2023); S_test +0.74..+1.33 vs BH_S +1.35/+1.40/+0.86; α +2.3-6.1% lordo/anno.
- **G6 REJECTED (BL-024)**: 30/30 sessioni passano il gate tecnico ma generano **0 trade, 0 P&L, Sharpe 0** — risk adapter blocca tutto.
- **Modello economico**: €3K/mese netti richiede α ≥ 118,9%/anno su singolo account 50K, o 5-20 account concorrenti a α 6%; soffitto misurato = +2-6% lordo → gap 5-16×.
- **Eval simulation empirica**: p(pass) 23-30% su ES 1d (CI 95% sup 40%) vs requisito pre-registrato ≥60%; buy&hold 23,2% (sotto random-walk 30,1%).
- **M32a post-beta (technical only)**: 20/20 pass, DD 0,21%, P&L +$293, Sharpe +0.11 — non è edge validation, solo smoke OMS/ledger.

---

## 8. Edge Status — Verità Onesta

### 8.1 Quanto vale l'edge misurato
**Zero netto costi.** L'α lordo residuo dei segnali trend è **+2.3-6.1%/anno** (medesimo ordine del buy&hold nello stesso periodo), ma i costi di esecuzione (0.23-0.79% per finestra) lo portano verso **zero netto**. Il walk-forward multi-asset conferma che tutti i segnali stanno sotto il buy&hold. La family mean-reversion su ES daily è archiviata (4/4 candidati negativi, luck p=1.0 in ogni regime).

### 8.2 Da dove veniva l'illusione di α
1. **Benchmark non anti-beta**: per mesi abbiamo misurato Sharpe assoluto su un back-test proxy di ES daily in finestre rialziste 2023-26, scambiando beta per alpha. Il closeout M31 del 19-lug (Sharpe 1.013, APPROVED) era fatto della stessa sostanza.
2. **Matrice 2×2×2 "intelligenza"** che produceva curve byte-identiche (N reale 17, non 136).
3. **Classificatore di regime M32a biased**: 29/30 sessioni "choppy" con confidence 0.91 → specialist `mean_rev` sempre selezionato → zero diversificazione. Cause: `_sma_regime_heuristic` ha soglia `vol_ratio>1.6` mai raggiunta su 250 bar daily ES; `trend_strength>0.02` spesso non superato; choppy è il fallback.

### 8.3 Root-cause analyses sintesi
- **SWEEP_ROOT_CAUSE_ANALYSIS (2026-07-28, 2.471 trade su 19 asset×TF)**: Pattern A (bull→trend, Sharpe +2→+4 su ES/SPY/NQ/QQQ) è **beta, non alpha** — long-biased in bull market 2009-26. Pattern B (choppy/bear→mean-rev, GC 1d +5.84 Sharpe 84.6% WR, EURUSD +2.37) è l'unico possibile edge reale ma va confermato con dati più lunghi. Pattern C (volatile→breakout, CL +0.16) è nullo. Pattern D (crypto 1h mean-rev) distrugge capitale: BTC 1h −$9.719, SOLUSDT tutto negativo — le code grasse cancellano le piccole vincite.
- **G6-PAPER-ANALYSIS (2026-07-30)**: 23/30 (77%) vs target 90% — causa primaria: regime detector choppy-biased. Soluzione tentata: AdaptiveEnsemble (weight blending + PyTorch 8-regime classifier Kairos-v2, accuracy 36,5%). Sprint 1 Results: **10% pass rate (peggio del 77%)**, mean Sharpe −1.0652, DD 4.01% — tutti gli specialisti hanno IC negativo/nullo su ES 1d finestre 217 bar (trend +0.008, mean_rev −0.091, breakout −0.220).

### 8.4 Verdetto
Il sistema non produce edge perché:
1. l'edge osservato su trend-following equities era **beta scambiato per alpha** (mercato bull 2009-2026)
2. la mean-reversion daily ES era **rumore** (luck p=1.0)
3. il regime detector è choppy-biased e non discrimina bene i regimi
4. l'orizzonte daily è **incompatibile col canale prop-firm** (volatilità troppo bassa per passare 6%/4% trailing DD)
5. i costi ($8.4/RT) consumano l'α residuo 2-6% portandolo a ~0 netto

---

## 9. Debito Tecnico (verificato 2026-08-15)

### 9.1 Gap di live-readiness (3/3 chiusi il 2026-08-10)
| Gap | Verdetto | Fix | File |
|---|---|---|---|
| #1 FRED lookahead | **RISOLTO** | `fetch_series`/`fetch_multiple` accettano `vintage=` → `vintage_dates` (ALFRED PIT). Test dedicati | `analytics/macro/fred.py:120,154-156,200,209` |
| #2 cvxpy morto | **KEEP documentato** | transiva obbligatoria di `pyportfolioopt` (`pyproject:37`); cablarla in S1.2 per Lane A sizing | — |
| #3 pessimistic-fill | **RISOLTO** | `paper_limit_penetration_ticks` + `paper_tick_size`: limit/stop si riempiono solo se il mercato sfonda il trigger di N tick. Default 0 = legacy | `execution/brokers/paper.py:374,381` |

### 9.2 Verifiche codice
- **`OrderManager`** (`execution/order_manager/manager.py:30`): rifiuta `risk_manager=None` con `ValueError` → BL-040 RISOLTO
- **`PropFirmOrderRiskAdapter`** (`policy/prop_firm/order_rirm.py:20`): cablato in CLI, NON in paper harness
- **LLM researcher** (`analytics/strategy/researcher.py:99,199`): `LLMStrategyResearcher.propose()` + `run_research_rounds()` working end-to-end
- **FRED vintage test** (`tests/unit/test_macro.py`): 11 test passed incluso `test_vintage_sends_vintage_dates`
- **Paper broker pessimistic-fill test** (`tests/execution/test_paper_broker.py`): 93 test passed incluso `TestPessimisticFill`

### 9.3 Deviazioni P0/P1/P2 (ARCHITECTURE.md §9)
| Priorità | Deviazione | Stato reale |
|---|---|---|
| P0 | risk opzionale e bypass composition root | **RISOLTO** (`manager.py:30` rifiuta None) |
| P0 | API production fail-open senza key | risolto (G0 P0.2 — fail-closed); warning startup |
| P1 | OMS/ledger in-memory di default (PG solo con `--storage=postgres`) | parzialmente aperto — Postgres path attivo, default resta memory |
| P1 | contratti execution nel package agents | aperto |
| P1 | cicli analytics/market/execution | aperto |
| P1 | Docker non riproducibile e non-root assente | aperto |
| P1 | motore qualification non certificato | aperto — Nautilus wrapper ha fallback, equity models non futures-grade |
| P1 | config environment non rappresenta replay/paper/shadow/evaluation/funded | parzialmente — `OracleMode` enum esiste ma env non lo propaga ovunque |
| P2 | NATS/QuestDB/Qdrant descritti oltre l'uso reale | documentato in ARCH §2.4 |
| P2 | dashboard read model basato anche su file/checkpoint | aperto |

### 9.4 Import graph (22 violazioni, 2026-07-30)
- 7 HIGH: dipendenze che violano authority boundary
- 12 MEDIUM: cicli soft o import cross-layer
- 1 ciclo reale: analytics↔market
- Dettagli in `docs/reports/import-graph-analysis-20260730.md:140-295`

### 9.5 Stub/placeholder noti (non bloccanti)
- `agents/orchestrator/graph.py:126-133`: macro e sentiment placeholder in MAS graph (TODO: GDP, CPI, unemployment integration)
- `analytics/regime/detector.py:160`: macro placeholder (fed from M8 in production)
- `policy/prop_firm/__init__.py:66`: Lucid sector-typical placeholder (site returned HTTP 403)

### 9.6 Debito di test
- 163 file di test, 2.697 test passati (2697 al 2026-08-10 pre-fix; il run finale post-fix S0 conferma il totale)
- 3 failure pre-esistenti: talib absent × 2, network test legacy cache path
- Coverage per package: analytics 0.31, api 0.06, integration 0
- 12 lint errori residui, 7 test LLM falliti (documentati in `task-list-prossimi-passi.md`)

---

## 10. Fattibilità 5%/Mese — Analisi Critica

### 10.1 Il numero, onesto
Per raggiungere **€3.000/mese netti** (soglia minima vitale), il modello economico S0.2 (`docs/reports/s0-2-economic-model.md`) quantifica:
- **Singolo account 50K**: richiede α ≥ **118,9%/anno**
- **5-7 account 150-200K cumulati**: richiede α ≥ **39,6-59,5%/anno**
- **Soffitto misurato della lane daily**: +2-6% lordo annuo (≈0 netto costi)
- **Gap**: 5-16× sotto il requisito

### 10.2 Simulazione empirica
Replay su 26 anni di ES 1d (`docs/reports/s0-2/eval_simulation.json`):
- p(pass) eval: **23-30%** (CI 95% sup 40%) vs requisito pre-registrato ≥60%
- buy&hold: 23,2% (sotto random-walk 30,1%)
- Tutti i candidati trend sotto il buy&hold

### 10.3 Monte Carlo sintetico
`docs/reports/s0-2/eval_economics.json`:
- α=0/σ=1.2% → p(pass) 30,1%
- α=6%/σ=1.2% → p(pass) 33,7%
- Per p(pass) ≥80% serve σ ≤ 0.8% (volatilità molto bassa) + α ≥ 6%

### 10.4 Implicazione strutturale
La family di segnali TA pubblici su futures daily è in uno spazio istituzionalmente affollato. Il base rate atteso di 0/9 (non sfortuna) conferma che non è il caso di "lavorare più duro" sullo stesso canale. La lane daily è chiusa per meta-kill rule del piano production-grade.

### 10.5 Vie residue (in ordine di probabilità di successo)
1. **Lane A — Core PAC multi-asset** (`plan-profitable-system.md` §4): buy&hold multi-asset (SPY/QQQ/TLT/GLD/XLE/FX) con tilt regime/momentum/vol-target + ribilanciamento mensile. EV **più alto** perché profittevole anche senza alpha (beta gestito con meno DD di buy&hold naive). Costruibile OGGI sui daily esistenti. **Cvxpy da cablare** per pesi Markowitz/Kelly.
2. **Lane B — Direzionale turnaround** (`plan-profitable-system.md` §5): tesi formalizzata su paniere (20-30 titoli in depressione di multipli + catalizzatore + orizzonte ~1 anno), sizing satellite 2-3%, invalidation predefinita. **Questa è l'intuizione INTC/Xiaomi dell'operatore formalizzata come processo**. Richiede universo azionario (oggi solo AAPL/MSFT) + fondamentali PIT.
3. **Lane C — Scalping/intraday** (`plan-profitable-system.md` §6): subordinata, richiede dati intraday nuovi (IBKR/Databento) + pessimistic-fill + walk-forward + gate. **8/8 candidati REJECTED, 0 trade G6** — non è una priorità oggi.

### 10.6 Linea temporale realistica
- **2-3 mesi di lavoro focalizzato** per G5+G6 verdi su una lane nuova (A o B)
- **1-2 settimane per il setup operatore** (login IBKR su localhost:7497 per futures 1m, API key Databento, account MyFundedFutures)
- **1 mese per G7 cert** (vertical slice prop-firm presto, non aspettare G6 verde completo)
- **3-6 mesi di osservazione funded** prima di scalare a 5-20 account

### 10.7 Numero riparametrato
Se l'edge intraday/multi-asset si materializza (big if), il target sostenibile realisticamente riparametrato è **€1.000-1.500/mese netti con 2-3 account 150-200K**, non €3K. Per €3K serve α ≥ 6% netto confermato su 250+ sessioni paper indipendenti con pass rate ≥90%.

---

## 11. Refactor vs Redesign — Domanda Chiave

### 11.1 Tesi architetturale
**L'architettura NON va ridisegnata.** È sostanzialmente sana nei componenti core:
- PostgreSQL ledger con idempotency key ✅ (G3)
- OMS durevole ✅ (G3)
- RecoveryService idempotente (5 test verdi) ✅
- ReconciliationWorker periodico (7 test verdi) ✅
- Policy prop-firm versionato con fixture Topstep 50K ✅ (G4)
- Risk kernel deterministico ✅ (G4)
- Boundary safety-critical definiti da ADR-008/009/010 ✅
- Separazione deterministico/LLM rispettata ✅
- Dual-engine backtest (vectorbt discovery + Nautilus qualification) ✅

### 11.2 Perché NON redesign architetturale
1. I 3 gap di live-readiness sono chiusi
2. I 16 ADR sono coerenti e 12/16 verificati REALITY
3. Il risk kernel è anti-bypass (`manager.py:30` rifiuta None)
4. I componenti aspirazionali (QuestDB, Qdrant, Rust core, Loki/Prom) sono DEFERRED per scelta, non per mancanza di capacità
5. Redesign architetturale consumerebbe 6-12 mesi senza risolvere il blocker reale (l'edge)

### 11.3 Però serve "redesign logico" (strategia)
Non refactor del codice, ma **ridefinizione della lane attiva**:
- **DA** "daily ES trend-following" (falsificato da 0/9 walk-forward + Sharpe −0.251 in Fase 5 onesto)
- **A** "Lane A (PAC multi-asset) + Lane B (turnaround su paniere) + Lane C (intraday subordinato)"

Questo è il cuore del piano profittevole (`docs/plan-profitable-system.md`) ed è già scritto.

### 11.4 Refactor tecnico vero (limitato, 1-2 settimane)
Non redesign — solo igiene:
1. **Cablare cvxpy per Lane A sizing** (Markowitz o Kelly con vincoli) — gap #2 documentato
2. **Rimuovere PyBroker deprecato** da `experiments/scripts/run_ga_pybroker.py` + `analytics/backtest/pybroker_integration.py` — ADR-011 richiede rimozione
3. **Risolvere ciclo analytics↔market** (1 ciclo reale, `import-graph-analysis-20260730.md`)
4. **Unificare experiment registry** (ADR-007 parziale: `agents/genetic/registry.py`, `core/plugin/registry.py`, `experiments/registry/` frammentati)
5. **Spostare contratti execution fuori dal package agents** (P1 aperto)
6. **Default Postgres** invece di `--storage=postgres` (P1 aperto, opzionale per ora)

### 11.5 Loop di apprendimento chiuso (NON cablato oggi)
Il gap di sistema più grave: il **loop chiuso LLM→mutation→sandbox→backtest→promote→paper→decay→replace NON è cablato**. I componenti esistono isolati (FactorTimingEngine, Lorentzian causal-fix, RegimeEnsemble, genetics/gates, LLM researcher) ma non sono orchestrati. Questo è un refactor strutturale che serve fare, ma è di **orchestrazione** (1-2 mesi), non di redesign architetturale.

### 11.6 Cosa non serve
- Non serve un nuovo broker adapter (paper, IBKR, MetaApi, CCXT già esistono)
- Non serve un nuovo backtest engine (vectorbt + Nautilus sufficienti)
- Non serve un nuovo OMS (PostgreSQL path attivo e idempotente)
- Non serve un nuovo policy engine (`policy/prop_firm/` versionato e funzionante)
- Non serve un nuovo MAS (LangGraph multi-agent working)

### 11.7 Verdetto
**Refactor mirato + redesign strategico della lane, NON redesign architetturale.** La distinzione è critica: il consulente deve sapere che l'infrastruttura è pronta per il live quando l'edge esiste; il lavoro da fare è sulla strategia/edge, non sui mattoni.

---

## 12. Question per il Consulente Esterno

Le domande chiave da portare alla consulenza:

1. **Sul canale**: data la diagnosi (α ≈ 0 netto su daily futures, lane daily morta), su quale canale un operatore singolo con stack Python/Nautilus/vectorbt ha la massima probabilità di produrre edge statisticamente onesto nei prossimi 6 mesi? Opzioni sul tavolo: (a) Lane A PAC multi-asset (beta gestito, non pretende alpha); (b) Lane B turnaround su paniere azionario (intuizione operatore INTC/Xiaomi); (c) Lane C intraday futures (subordinata, dati mancanti); (d) altro (es. option selling, vol arbitrage, cross-asset stat arb).

2. **Sul sizing e meta-kill**: il modello economico dice €3K/mese richiede α ≥ 118,9%/anno su singolo account, o 5-20 account a α 6%. Ha senso perseguire 5-20 account concorrenti (modello "many small bets") o è meglio un account più grande con α più alto? Come si gestisce il rischio di blowup cross-account (correlazione, stesso giorno, stessa strategia)?

3. **Sull'intuizione turnaround (Lane B)**: l'operatore ha documentato (chat con collega) un'intuizione di "value investing + turnaround + management quality + innovazione prodotto" che ha funzionato su INTC (+400% YTD) e Xiaomi. Come si formalizza questa intuizione in un processo ripetibile? Universo: 20-30 titoli in depressione di multipli + catalizzatore identificabile. Universo azionario disponibile oggi: solo AAPL/MSFT. Serve IBKR/polygon per espandere. Vale la pena?

4. **Sulla regola anti-beta (ADR-016)**: la regola dice "test anti-beta: S_test > Sharpe buy&hold, N onesto, luck_p_value nel gate". È abbastanza? Servono altri test di robustezza (deflated Sharpe ratio, PBO, CPCV)? Il consulente conosce il work di López de Prado / Bailey?

5. **Sulla consulenza tecnica**: il loop di apprendimento (GA→paper→reconcile→decay→replace) NON è cablato. Serve progettazione architetturale di questo loop? È fattibile per un operatore singolo o serve team? Quanto tempo realisticamente?

6. **Sulla prop-firm scelta**: The5ers Bootcamp (MT5/CFD, overnight OK) vs Lucid LucidPro (futures, intraday-only, EOD trailing) vs MyFundedFutures (AUTO_SUPPORTED). Per la Lane A (PAC multi-asset, overnight necessario), The5ers è l'unica compatibile. Per la Lane C (scalping intraday), Lucid. Strategia: concentrarsi su una firm o mantenerne multiple in parallelo?

7. **Sul timing capitale reale**: quando ha senso investire il primo € (entry fee ~$95 per The5ers, $129.50 per Lucid)? Subito dopo G7 o aspettare G8 (funded limited rollout)? Qual è il tradeoff tra "imparare dal vivo" (paper→live gap) e "non bruciare capitale su edge non validato"?

8. **Sull'operatore singolo**: il rischio principale identificato è la diluizione di focus (data engineering + research + dev + ops + risk da una persona sola). Ha senso assumere/collaborare con qualcuno? Per quali ruoli? O automizzare al massimo e restare solo?

9. **Sull'orizzonte temporale**: l'operatore ha detto "5%/mese, possibilmente di più". È disposto a 2-3 anni di lavoro prima di vedere il primo € netto consistente? Oppure ha bisogno di reddito nel breve (3-6 mesi)? Questo cambia radicalmente la strategia.

10. **Sull'LLM researcher**: `LLMStrategyResearcher` è cablato e funziona (vsllm/opencode endpoint). Ha senso continuare a usarlo come "researcher in the loop" o è un lusso? Qual è il valore atteso reale di un LLM che propone strategie vs un operatore umano che le propone?

---

## 13. Question per il Deep-Research Successivo

Dopo la consulenza, il deep-research dovrebbe rispondere a (in ordine di priorità):

1. **Mappa del panorama "retail + prop-firm 2026"**: quanti operatori singoli riescono a passare challenge prop-firm con sistematico? Qual è il base rate reale (non marketing)? Fonti: Reddit r/Forex_Trading, r/Forex_Trading_Life, prop-firm payout reports, MyForexFunds (defunct) post-mortem.

2. **Canali con edge reale documentato per retail 2026**: oltre il "daily trend-following" (falsificato da Oracle), quali canali mostrano edge statisticamente significativo su operatore singolo? Es: option selling (SPX/ES), vol arbitrage (VIX futures term structure), cross-asset stat arb (gold/DXY, yields/stocks), intraday futures (ES/NQ open range breakout), crypto funding rate arb. Per ognuno: edge documentato, skill richiesta, capitale minimo, prop-firm compatibilità.

3. **Formalizzazione del turnaround su paniere**: come strutturare un processo di screening su 20-30 titoli in depressione di multipli (P/E < X, P/B < Y, drawdown > Z% da massimi) con catalizzatore identificabile (buyback, cambio management, prodotto nuovo)? Fonti: academic literature (Lakonishok, value momentum), Joel Greenblatt "The Little Book That Beats the Market", Piotroski F-Score, Magic Formula.

4. **Work di López de Prado / Bailey**: test di robustezza avanzati (Deflated Sharpe Ratio, Probability of Backtest Overfitting, Combinatorial Purged CV, Bayesian backtest). Quale implementare oltre `luck_p_value`? Esiste codice open-source di riferimento?

5. **Implementazione del loop di apprendimento chiuso**: pattern di orchestrazione per "GA evolution → paper session → reconcile → fitness feedback → mutation". Esistono implementazioni di riferimento? (Inalpha/stratevo pattern, FinClaw, FinRL). Quanto costa implementare per un operatore singolo?

6. **Universo azionario per Lane B**: quale fonte dati per daily equity con fondamentali PIT? yfinance (gratis, ma limitato), polygon.io ($29/mo), IBKR (gratis con paper account). Per fondamentali PIT: Alpha Vantage, FMP, SEC EDGAR. Costo vs copertura.

7. **Confronto con il lavoro "ai-hedge-fund" (14K⭐)**: pattern multi-agent LLM (CEO+Analyst+Trader+Risk) con voting invece di routing binario. È applicabile a Oracle? Qual è il gap reale vs Oracle's `agents/`?

8. **Confronto con FinClaw (12.1K⭐)**: 484 fattori built-in vs 69 di Oracle. È un "force multiplier" reale o un catalogo gonfiato? Quali fattori vale la pena portare nel catalogo Oracle?

9. **Confronto con pysystemtrade**: vol target, forecast scaling, IDM (Instrument Diversification Multiplier), forecast combination. È il framework di riferimento per commodity trading advisors (CTA). Vale la pena integrarlo come Lane A backbone?

10. **Stima realistica di effort per Lane A (PAC multi-asset)**: 13gg stimati dal integration blueprint. È realistico per un operatore singolo? Quali sono i task concreti? Qual è la sequenza minima per produrre un report paper onesto entro fine settembre 2026?

---

## 14. Riferimenti Completi (per il consulente)

### 14.1 Documentazione living
- `docs/ARCHITECTURE.md` — architettura corrente e target (post ADR-008)
- `docs/SPECIFICATION.md` — FROZEN storico v1.0
- `docs/DOMAIN_MODEL.md` — entità, attributi, relazioni, invarianti
- `docs/POLICY_ENGINE.md` — design policy engine
- `docs/PLUGIN_API.md` — contratto plugin (ADR-004 superseded)
- `docs/EVENTS.md` — schema eventi NATS (FROZEN, superseded)
- `docs/GOVERNANCE.md` — gerarchia canonica docs
- `docs/RUNBOOK.md` — operatività
- `docs/DATA_SOURCES.md` — coverage matrix reale (35 futures CME, FX Dukascopy, crypto Binance)
- `docs/CREDENTIALS.md` — MetaApi/LLM key
- `docs/SECURITY.md` — threat model, incident response
- `docs/AUDIT_FINDINGS.md` — audit secco 2026-07-25

### 14.2 ADR
- `docs/ADR/README.md` — indice normativo
- `docs/ADR/ADR-008-modular-monolith-authority-boundaries.md` (KEY)
- `docs/ADR/ADR-009-data-state-storage-strategy.md` (KEY)
- `docs/ADR/ADR-010-deterministic-execution-safety-boundary.md` (KEY)
- `docs/ADR/ADR-012-capability-gates-replace-phases.md` (KEY)
- `docs/ADR/ADR-014-m31-evidence-loss.md` (incident)
- `docs/ADR/ADR-016-g5-respec-stop-atr-qty1.md` (anti-beta benchmark)

### 14.3 Piani strategici (vivi)
- `docs/plan-production-grade.md` — S0-S6 APPROVED 2026-08-05
- `docs/plan-profitable-system.md` — Lane A/B/C 2026-08-10
- `docs/plans/BL-023-m31-g5-recovery.md` — chiuso in ADR-014/016

### 14.4 Piani archiviati (storici)
- `docs/plans/phase0-plan.md` ... `phase6-plan.md`
- `docs/plans/phase3.5-plan.md`, `phase3.5.1-plan.md`
- `docs/plans/plan-expression-alpha.md`
- `docs/plans/oracle-autopilot-atomic-backlog-v1.md` (950+ task M00-M38)
- `docs/plans/oracle-autopilot-gate-backlog-v2.md` (STALE: dice G5 PASSED)
- `docs/plans/testing-report.md` (snapshot 2026-07-19)

### 14.5 Report sperimentali (evidenza)
- `docs/reports/README.md` — indice per gate
- `docs/reports/s0-1-bl023-autopsy.md` — autopsia BL-023 (KEY: beta mistaken for alpha)
- `docs/reports/s0-2-economic-model.md` — €3K/mese modello (KEY: gap 5-16×)
- `docs/reports/s0-2/eval_economics.json` — MC p(pass)
- `docs/reports/s0-2/eval_simulation.json` — replay empirico ES 1d
- `docs/reports/m31-rerun-final/m31.md` — canonico M31 (Sharpe −2.51)
- `docs/reports/m31-rerun/m31.md` — Fase 5b (Sharpe −0.314)
- `docs/reports/multiasset/walkforward.md` — 0/9 vs buy&hold (KEY)
- `docs/reports/candidates/*.md` — 8/8 REJECTED Fase 5c
- `docs/reports/g6-wp2-final/g6-wp2-final.md` — 30/30 pass, 0 trade
- `docs/reports/live-readiness-gap-analysis.md` — 3 gap chiusi
- `docs/reports/quant-finance-analysis.md` — Sharpe 207.84 artefatto
- `docs/reports/edge-portfolio/edge-portfolio.md` — probe 16 strategie
- `docs/reports/signal-candidates/signal-candidates.json` — probe 8 candidati
- `docs/reports/import-graph-analysis-20260730.md` — 22 violazioni architetturali
- `docs/reports/2026-07-19-m31-closeout.md` — APPROVED poi invalidato
- `docs/reports/m31-historical-replay-qualification.md` — Sharpe −1.15, 48 breach
- `docs/reports/2026-07-23-m32a-post-beta.md` — technical pass, non edge

### 14.6 Status + ROADMAP
- `ROADMAP.md` — vision G0-G14, principi
- `BACKLOG.md` — task atomiche BL-NNN
- `PROJECT.md` — perimetro, repo layout
- `README.md` — identità pubblica, stack, roadmap G0-G9
- `ANALYSIS_REPORT.md` — analysis import graph, fail-open, ADR-010, NATS
- `docs/ORACLE_AUTOPILOT_STATUS.md` — matrice gate/stato autoritativa
- `docs/PROP_FIRM_READINESS_ROADMAP.md` — policy prop-firm, support mode

### 14.7 Docs specializzati
- `docs/analisi-completa-20260729.md` — sintesi globale
- `docs/G6-PAPER-ANALYSIS.md` — regime choppy-biased
- `docs/G6-SPRINT1-RESULTS.md` — Sprint 1 AdaptiveEnsemble 10% pass
- `docs/SWEEP_ROOT_CAUSE_ANALYSIS.md` — 2.471 trade, 4 pattern
- `docs/BL-301-data-lake-audit-and-integration-plan.md` — lake audit + QLib/Inalpha/PyPortfolioOpt/pysystemtrade
- `docs/research-miracoli.md` — FinClaw, Kairos-v2, FinRL, ai-hedge-fund
- `docs/free-1m-data-strategy.md` — 4 tier fonti 1m zero-cost
- `docs/task-list-prossimi-passi.md` — 23 task, ~30gg, priorità P0-P5

### 14.8 Integration blueprints
- `docs/integration-blueprint-4-frameworks.md` — QLib/Inalpha/PyPortfolioOpt/pysystemtrade (2026-07-28)
- `docs/plan-integration-inalpha-varrd.md` — 5 pilastri (Factor Timing, Strategy Gen, Memory, HMM+Lorentzian, VARRD)
- `docs/plan-integrazione-kairos-finclaw.md` — TradingMLP PyTorch + 484 fattori FinClaw

### 14.9 Codice chiave (per verifica rapida)
- `execution/order_manager/manager.py:30` — rifiuta `risk_manager=None`
- `policy/prop_firm/order_risk.py:20` — `PropFirmOrderRiskAdapter`
- `policy/prop_firm/governor.py` — `PropFirmRiskGovernor`
- `policy/prop_firm/profile.py` — `FirmProgramProfile`, THE5ERS, LUCID, TOPSTEP
- `analytics/macro/fred.py:120,154-156,200,209` — `vintage=` parameter
- `execution/brokers/paper.py:374,381` — pessimistic-fill
- `analytics/strategy/researcher.py:99,199` — LLM researcher
- `analytics/strategy/catalog/alpha101.py:180,202,241` — α044/050/063
- `core/domain/mode.py:25-68` — `OracleMode` enum (RESEARCH→REPLAY→PAPER→SHADOW→EVALUATION→FUNDED)
- `analytics/qualification/models.py:12` — `ReplayRegime` enum (4 regimi canonici)

### 14.10 Memory cross-session
- `~/.claude/projects/-home-alin--repos-oracle-trading/memory/MEMORY.md` — indice
- Memory file individuali: propfirm-goal, propfirm-roadmap, propfirm-rules, propfirm-mc-findings, modo-a-llm-researcher, r0-r5-multiasset-plan, r2-multi-tf, r3-unified-evaluator, r5-hard-mode-search, g6-m32-progress, oracle-audit-25lug, live-readiness-assessment, awesome-systrade-reuse, mt5-linux-execution-path

---

## 15. Appendice — Metriche del Progetto

### 15.1 Dimensioni codice
- File Python (escluse .venv, node_modules, .omx, build, legacy, __pycache__): ~916
- Righe totali: ~131K
- File di test: 163
- Test passati: 2.697 (2697 al 2026-08-10)

### 15.2 Per package
| Package | File | Note |
|---|---|---|
| analytics | 114 | backtest/strategy/regime/technical/macro/sentiment/fundamental |
| core | 71 | domain/events/config/plugin/logging/data + oms/ledger postgres |
| agents | 42 | analysts/committee/debate/decision/oracle/orchestrator/genetic |
| genetics | 41 | GA island model, NSGA-II |
| market | 30 | ingestion/store/data_config |
| execution | 29 | brokers (paper/ibkr/metatrader/ccxt) + order_manager + session_guards |
| apps | 22 | api/dashboard/cli |
| policy | 6 | prop_firm (governor/profile/order_risk) |
| application | 2 | contracts |
| research | 1 | — |
| orchestration | 1 | — |

### 15.3 Stack istituzionale installato (verificato 2026-08-10)
- nautilus_trader 1.230 — `analytics/backtest/engines/nautilus.py`
- vectorbt 1.1 — `analytics/backtest/engines/vectorized.py`
- polars 1.43
- ccxt — `execution/brokers/ccxt_broker.py`
- ib_insync — `execution/brokers/ibkr.py`
- numba
- Dukascopy source — `market/ingestion/sources.py:786`
- Databento (API da setup)
- PostgreSQL (G3 attivo dal 25-lug)
- NATS/JetStream (trasporto asincrono)
- Redis (cache, ricostruibile)
- React 18 + FastAPI + LangGraph + ElizaOS bridge

### 15.4 Lake data
- 496 serie / 101 simboli / 344.548.291 righe totali
- 68.975 partizioni tracciate, 0 dangling (BL-307)
- Asset class coperti: FX 25+ coppie (1m 2003→), crypto 10+ coin (1m dal listing), metalli XAU/XAG (1m 2003→), futures 5 core (ES/NQ/GC/CL/YM daily + 1h parziale), equities 9 (SPY/QQQ/IWM/DIA/AAPL/MSFT/GLD/TLT/DBA daily)
- Gap critico: ~8 giorni di 1m/5m/15m futures (BL-052) — requisito 5-30m per canale prop-firm non testabile

---

## 16. Closing Note

Questo report è la verità onesta del progetto al 2026-08-15. Non nasconde i REJECTED (G5, G6, 0/9 walk-forward, 8/8 candidati Fase 5c, alpha ≈ 0 netto). Non gonfia i PARTIAL. I 3 gap di live-readiness sono chiusi. L'architettura è pronta per il live quando l'edge esiste. L'edge non esiste oggi, ma la diagnosi è chiara sul perché e sulle vie d'uscita.

**Per il consulente**: la domanda non è "ridisegnare l'architettura". La domanda è "trovare un canale dove l'edge esiste, cablare i mattoni esistenti in un loop chiuso, e validare onestamente con N onesto e anti-beta benchmark". L'operatore ha costruito una macchina istituzionale ma sta facendo lavoro da trading firm completa da solo. La sfida non è tecnica, è di focus e di strategia.

**Per il deep-research successivo**: mappare il panorama retail + prop-firm 2026, identificare canali con edge documentato per operatore singolo, valutare il turnaround su paniere come formalizzazione dell'intuizione operatore, stimare effort realistico per Lane A PAC multi-asset entro fine settembre 2026.

**Per l'operatore**: 5%/mese costante è fuori portata della famiglia di segnali TA pubblici su daily futures in spazio istituzionalmente affollato. Il modello economico è chiaro: serve α ≥ 6% netto confermato su 250+ sessioni paper indipendenti con pass rate ≥90% per 5-20 account funded, e anche lì il target realistico riparametrato è €1.000-1.500/mese, non €3K. La buona notizia: l'architettura è pronta, i 3 gap sono chiusi, il piano profittevole Lane A/B/C è scritto. La via è aperta, ma richiede 2-3 anni di lavoro focalizzato, non settimane.

---

*Fine report. ~28K tokens. Generato 2026-08-15 da Claude Opus 4.7 sulla base di 5 subagent sintesi parallele (ADR, piani, report, architettura, status+specializzati) + scansione codice diretta.*
