# Oracle Architecture — Current State and Target Boundaries

> Stato: living architecture
> Data: 2026-07-18; aggiornamenti mirati al 25-lug-2026 (post audit-remediation-beta)
> Aggiornamento 2026-08-19: chiusura fail-open API/risk e cicli core↔execution,
> market↔analytics (fase P0 — chore/p0-architecture-hygiene)
> Decisioni normative: [ADR/README.md](ADR/README.md)
> Stato gate-by-gate: [STATUS.md](../ROADMAP.md) / [ORACLE_AUTOPILOT_STATUS.md](ORACLE_AUTOPILOT_STATUS.md)
> Audit secco: [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md)

## 1. Perimetro

Oracle è oggi un monorepo con:

- control plane Python;
- API FastAPI;
- dashboard React;
- bridge ElizaOS TypeScript;
- analytics, backtest e genetic research;
- adapter broker e policy prop-firm;
- storage locale SQLite/JSON/Parquet;
- infrastruttura Compose (`infra/docker/docker-compose.yml`) con PostgreSQL,
  Redis, API e Dashboard. NATS, QuestDB, Loki, Prometheus e Qdrant restano
  aspirazionali/DEFERRED: presenti solo in configurazione, NON in Compose.

La forma reale è un **modular monolith in evoluzione**, non un insieme di
microservizi. Le chiamate in-process dominano; NATS è implementato ma non è il
mezzo universale di comunicazione descritto dagli ADR storici.

## 2. Problemi osservati

### 2.1 Confini di dipendenza

L'import graph contiene dipendenze che puntano verso l'esterno o creano cicli:

- execution importa contratti dal package agents;
- policy importa tipi da execution;
- analytics e market si importano in entrambe le direzioni;
- analytics importa execution;
- genetics dipende da analytics e agents dipende da genetics.

Questi accoppiamenti rendono difficile provare che il percorso risk/execution
sia indipendente da research e LLM.

### 2.2 Fonti di stato multiple

Oggi esistono SQLite separati, JSON/checkpoint, Parquet e dizionari in-memory.
Nessuno è ancora un ledger account autorevole.

### 2.3 Fail-open

- ~~OrderManager accetta risk_manager assente~~ → chiuso (ValueError, commit 6c8c280);
- la CLI aveva un percorso verso broker live senza risk, ora bloccato;
- ~~API authentication è disabilitata quando ORACLE_API_KEY è vuota~~ → chiuso il
  2026-08-19 (P0): bind default loopback + `verify_auth_bind_safety()` blocca
  all'avvio un'API senza chiave su interfaccia non-loopback
  (`apps/api/config.py`, opt-in esplicito `ORACLE_ALLOW_OPEN_BIND`);
- alcuni backtest e feature read ignorano eccezioni o usano fallback;
- ~~il grafo MAS usa assessment permissivi quando componenti mancano~~ → chiuso
  il 2026-08-19 (P0): il nodo risk senza risk_manager è fail-closed
  (`approved=False`, reason esplicita) in `agents/orchestrator/graph.py`.

### 2.4 Architettura aspirazionale

QuestDB, Qdrant, Redis, PostgreSQL, NATS JetStream e osservabilità sono presenti
in configurazione o Compose, ma non costituiscono ancora il runtime autorevole.
La documentazione deve distinguere IN_USE, EXPERIMENTAL e DEFERRED.

## 3. Target: modular monolith con ports and adapters

~~~mermaid
flowchart TB
    UI[CLI / API / Dashboard] --> APP[Application services]
    INTEL[LLM / Analysts / Eliza / GA] --> CONTRACTS[Decision contracts]
    CONTRACTS --> APP

    APP --> MODE[Mode and authority guard]
    MODE --> RISK[Deterministic risk kernel]
    RISK --> OMS[Durable OMS]
    OMS --> PORTS[Broker ports]
    PORTS --> BROKER[Paper / Sandbox / Certified broker]

    BROKER --> REC[Reconciliation]
    REC --> LEDGER[Authoritative ledger]
    LEDGER --> APP

    APP --> OUTBOX[Transactional outbox]
    OUTBOX --> NATS[NATS / JetStream]
    NATS --> OBS[Audit / Metrics / External integrations]
~~~

### 3.1 Regola di dipendenza

Dipendenze ammesse, dall'esterno verso l'interno:

1. **core/domain** — value object, enum, eventi e invarianti; nessun import da
   apps, agents, analytics, execution o policy;
2. **application/contracts** — PortfolioPlan, TradeIntent, AccountSnapshot,
   RuleDecision e porte;
3. **application/services** — use case deterministici;
4. **adapters** — broker, database, provider dati, NATS, LLM;
5. **apps** — composition root CLI/API/worker.

Il package agents non possiede contratti usati da execution. Policy non importa
implementazioni OrderManager: entrambi dipendono da una porta inward.

### 3.2 Regola sincrono/asincrono

- La hot path mode → risk → OMS → broker è sincrona/in-process nel primo
  deployment, così errori e transazioni sono espliciti.
- Eventi asincroni partono da un transactional outbox dopo il commit.
- NATS trasporta integrazione, audit e fan-out; non sostituisce il database
  autorevole.
- La separazione in servizi è ammessa solo dopo benchmark, ownership distinta o
  isolamento di failure dimostrato.

## 4. Piani architetturali

### 4.1 Intelligence plane

Responsabilità:

- acquisire evidence;
- produrre analisi e target;
- dichiarare confidence, scadenza, provenance e invalidation;
- non possedere credenziali broker;
- non calcolare hard risk nella hot path.

Output ammesso: decision contract versionato. Un output invalido o scaduto è
NO_TRADE.

### 4.2 Safety control plane

Responsabilità:

- validare modalità e account;
- risolvere il rule profile;
- calcolare quantity da ContractSpec e stop;
- applicare hard risk;
- creare intent/order durevoli;
- gestire idempotenza e outbox;
- riconciliare broker e ledger;
- eseguire cancel/flatten.

Non dipende da LLM, Eliza, dashboard o GA.

### 4.3 Research plane

Responsabilità:

- dataset e feature point-in-time;
- backtest discovery e qualification;
- WFA, holdout, stress ed experiment registry;
- strategy promotion.

Non può scrivere nel ledger operativo o inviare ordini.

### 4.4 Operations plane

Responsabilità:

- API autenticata;
- dashboard read-model;
- metriche, tracing e alert;
- deployment, backup, DR e incident response.

La dashboard non legge direttamente database runtime o checkpoint per
ricostruire lo stato live: usa API/read model derivati dal ledger.

## 5. State authority matrix

| Dato | Source of truth target | Dev/test | Non autorevole |
|---|---|---|---|
| Account, balance, equity, margin | PostgreSQL ledger | SQLite | Redis, NATS, dashboard |
| Order e fill | PostgreSQL OMS | SQLite | process memory, JSON |
| Position | Ledger riconciliato | SQLite | agent state |
| Rule profile | Versioned immutable catalog | Fixture file | pagina web live |
| Raw market/news | Immutable dataset/object store | file fixture | cache |
| Feature research | Parquet + metadata catalog | Parquet | Redis |
| Experiment | Registry PostgreSQL/SQLite + artifact manifest | SQLite | filename |
| Prompt/model run | Audit store | SQLite | log console |
| Cache | Redis/in-memory | in-memory | mai source of truth |

### Decisione QuestDB

QuestDB resta DEFERRED. Si adotta soltanto se un benchmark con volume reale
dimostra che Parquet/DuckDB e PostgreSQL non soddisfano ingest/query SLO.
La presenza in Compose non equivale ad adozione.

### Decisione Qdrant

Qdrant resta DEFERRED. Nessun retrieval semantico entra nella hot path di risk o
execution. Un use case intelligence può proporlo con ADR e data-retention review.

## 6. Execution sequence target

~~~mermaid
sequenceDiagram
    participant L as LLM/Strategy
    participant A as Application
    participant R as Rule+Risk
    participant O as Durable OMS
    participant B as Broker
    participant G as Ledger/Reconciliation

    L->>A: PortfolioPlan / TradeIntent
    A->>A: Validate mode, schema, expiry, snapshot IDs
    A->>R: Pre-trade context
    R-->>A: ALLOW or DENY with reason/profile version
    alt DENY or uncertain
        A-->>L: NO_TRADE / PAUSE
    else ALLOW
        A->>O: Persist intent + idempotency key
        O->>B: Submit
        B-->>O: Ack / fill / reject
        O->>G: Persist event
        G->>B: Reconcile
        G-->>A: Authoritative account snapshot
    end
~~~

## 7. Backtest architecture

- **Discovery engine:** veloce e vectorized; consente screening e ricerca.
- **Qualification engine:** event-driven, usa gli stessi ContractSpec, sizing,
  session/risk e cost model del paper path.
- **Parity:** stessa strategia di riferimento, stesso dataset e tolleranze
  predefinite.
- **Promotion:** nessun risultato discovery viene promosso senza qualification.
- **Stato corrente:** vectorbt è research-only; PyBroker è deprecato; il wrapper
  Nautilus è candidato ma non certificato perché contiene fallback, modelli
  equity e ricostruzione P&L non ancora futures-grade.

## 8. Deployment target iniziale

Un singolo deployment applicativo è preferito finché non esistono motivi
misurati per distribuire servizi:

- API/control worker Python non-root;
- PostgreSQL privato;
- NATS privato;
- Redis privato e ricostruibile;
- storage dataset separato;
- dashboard statica;
- ingress autenticato;
- secrets manager;
- backup, health/readiness e resource limits.

Porte database e message bus non devono essere pubblicate su interfacce esterne.
Il Compose attuale è development scaffolding, non produzione.

## 9. Deviazioni da chiudere

| Priorità | Deviazione |
|---|---|
| ~~P0~~ ✅ | ~~risk opzionale e bypass composition root~~ — chiuso (OrderManager ValueError + MAS risk node fail-closed) |
| ~~P0~~ ✅ | ~~API production fail-open senza key~~ — chiuso 2026-08-19 (`verify_auth_bind_safety`, bind loopback default) |
| P1 | OMS/ledger in-memory di default (Postgres disponibile solo con `--storage=postgres`; G3 attivo dal 25-lug) |
| P1 | contratti execution nel package agents |
| P1 | cicli analytics/market/execution — parzialmente chiuso 2026-08-19: core↔execution e market↔analytics risolti (tipi broker in `core/domain/broker.py`, `IngestionError` in `core/errors/data_errors.py`); restano analytics→execution/policy e genetics↔analytics (porte previste in P2) |
| P1 | Docker non riproducibile e non-root assente |
| P1 | motore qualification non certificato |
| P1 | config environment non rappresenta replay/paper/shadow/evaluation/funded |
| P2 | NATS/QuestDB/Qdrant descritti oltre l'uso reale |
| P2 | dashboard read model basato anche su file/checkpoint |

## 10. ADR collegati

- ADR-008 — modular monolith e confini di autorità;
- ADR-009 — strategia storage e source of truth;
- ADR-010 — execution safety boundary;
- ADR-011 — separazione discovery/qualification backtest;
- ADR-012 — capability gate al posto delle Phase;
- ADR-013 — rule catalog prop-firm versionato;
- ADR-014 — M31 evidence loss (G5 REGRESSED, dataset lineage GAP);
- ADR-015 — Topstep automation / VPS / device policy;
- ADR-016 — G5 re-spec: stop ATR 1.0, qty 1, N onesto (anti-beta benchmark).
