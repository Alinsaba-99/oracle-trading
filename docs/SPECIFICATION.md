# Oracle Architecture Specification v1.0

> Piattaforma di Ricerca Quantitativa — Motore Decisionale Deterministico con Consulenza LLM
> Data: 2026-07-06 | Status: **FROZEN** (modifiche via ADR)

Questa specifica descrive il perimetro research v1.0. Non certifica execution
live, profitability o prop-firm readiness. Il percorso verso una v2 automatica
è governato da
[PROP_FIRM_READINESS_ROADMAP.md](PROP_FIRM_READINESS_ROADMAP.md);
la rimozione della supervisione umana o l'estensione del perimetro production
richiederanno una nuova versione della specifica e ADR dedicati.

---

## 1. Vision

Costruire una piattaforma di ricerca quantitativa end-to-end che integri:

- **Motore quantitativo deterministico** per backtesting, execution e risk management
- **Evoluzione genetica** di pipeline decisionali complete (non solo strategie)
- **Sistema multi-agente** dove gli LLM agiscono come consulenti specializzati, non come decisori
- **Policy Engine** separato per compliance, risk limits e governance
- **Riproducibilità totale** tramite Experiment Registry e Data Versioning
- **Architettura a plugin** per estensione senza modifica del core

### 1.1 Dichiarazione di Intent

Oracle **non** è un "AI trading bot". Oracle è una **piattaforma di ricerca quantitativa** nella quale gli LLM sono:
- **Consulenti**: analizzano, sintetizzano, dibattono, suggeriscono
- **Mai decisori**: ogni decisione numerica passa attraverso codice deterministico validato

---

## 2. Goals

1. Fornire un framework per scoprire, validare e mandare in produzione strategie quantitative
2. Supportare asset class multiple: equities, crypto, FX, options (come hedging)
3. Evolvere geneticamente pipeline decisionali complete (universe → feature → signal → filter → risk → execution)
4. Mantenere riproducibilità totale di ogni esperimento attraverso Experiment Registry
5. Separare policy (compliance/rischio) dalle strategie in un Policy Engine embeddato
6. Rendere ogni componente estensibile tramite plugin senza modificare il core
7. Garantire che gli LLM siano consulenti, non decisori — ogni decisione numerica è deterministica

---

## 3. Non Goals (v1.0)

Oracle v1.0 **NON** è:

- Un HFT engine o sistema di market making
- Un framework di arbitraggio a bassa latenza
- Un broker o OMS enterprise
- Un sistema che lascia decisioni finanziarie agli LLM
- Un sistema auto-modificante in produzione (supervisione umana richiesta)
- Un sostituto di Bloomberg Terminal (obiettivo di lungo termine, non v1.0)
- Una piattaforma di execution institutionale
- Un sistema di trading di volatilità o options complesse (solo hedging base)

---

## 4. Principi Architetturali (Immutabili)

| # | Principio | Descrizione |
|---|-----------|-------------|
| 1 | **LLM = Consulente** | Ogni decisione numerica passa attraverso codice deterministico. Gli LLM sintetizzano e dibattono ma non decidono. |
| 2 | **Event-Driven** | Nessuna comunicazione diretta tra componenti. Solo eventi NATS con schema versionato. |
| 3 | **Plugin-First** | Ogni estensione è un plugin registrato. Il core non si modifica mai per aggiungere funzionalità. |
| 4 | **Riproducibilità** | Experiment Registry + Data Versioning per ogni esecuzione. Un backtest del 2026 deve essere ricreabile identico nel 2028. |
| 5 | **Policy Separate** | Le policy di compliance/rischio sono un layer indipendente dalle strategie e dal decision-making. |
| 6 | **Separazione Deterministico/LLM** | Calcoli numerici: codice deterministico. Sintesi e pattern recognition: LLM. Nessun LLM in hot path esecutivo. |
| 7 | **Fail Closed** | Se un componente fallisce, il sistema non prende decisioni non validate. "No Trade" è la risposta di default. |

---

## 5. Architettura a Layer

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        DECISION ORCHESTRATION ENGINE (DOE)                   │
│  Coordina · Monitora · Applica Policy · Gestisce ciclo di vita              │
├──────────────────────────────────────────────────────────────────────────────┤
│                               AGENT SYSTEM                                   │
│  ANALYST: Macro · Tech · Fundamental · Sentiment · Options/Flow · OnChain   │
│  DEBATE: Bull → Bear → Devil's Advocate (1 round)                           │
│  DECISION: Risk Manager (score) → Portfolio Manager (final)                  │
│  "No Trade" è una decisione valida.                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│       POLICY ENGINE                  QUANT RESEARCH LAB                      │
│  HardLimit · SoftLimit              Feature Engineering · Alpha Factors      │
│  Compliance · Governance            PCA · Clustering · SHAP · Bayesian      │
│  MarketCondition                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                         GENETIC ENGINE                                       │
│  Genoma: Universe → Feature → Signal → Filter → Risk → Execution            │
│  9-stage pipeline: Mut → BT → WF → MC → Bootstrap → Reality → Paper        │
│  → Shadow → Production                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                          EXECUTION ENGINE                                    │
│  [RUST] Order Book · Simulator · Event Engine · Fill Validation             │
│  [PYTHON] Order Manager · Broker Connectors · Execution Algos (VWAP/TWAP)   │
├──────────────────────────────────────────────────────────────────────────────┤
│                    BACKTESTING & VALIDATION                                  │
│  Experiment Registry · Metriche · Bias Correction · Walk-Forward            │
├──────────────────────────────────────────────────────────────────────────────┤
│                    ANALYTICS & REGIME                                        │
│  Ensemble: HMM + BOCD + PELT + Vol Cluster + Corr Matrix + Macro State     │
│  Feature Store (versionata, calcolata una volta, riusata ovunque)          │
├──────────────────────────────────────────────────────────────────────────────┤
│                    DATA & INFRASTRUCTURE                                     │
│  Event Bus (NATS) · DB: QuestDB, PG, Redis, Loki, Prom, Qdrant             │
│  Data Version Manager · Knowledge Base (RAG per agenti)                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Repository Structure (Monorepo)

```
oracle/
├── apps/                          # Applicazioni deployabili
│   ├── dashboard/                 # UI (Streamlit → FastAPI → React)
│   ├── api/                       # REST API pubblica
│   └── cli/                       # CLI tool
├── services/                      # Microservizi (quando necessario)
│   ├── ingestion/                 # Data ingestion pipeline
│   ├── execution/                 # Order execution engine
│   ├── backtest/                  # Backtesting service
│   ├── genetic/                   # Genetic algorithm engine
│   ├── agents/                    # Multi-agent orchestration
│   └── policy/                    # Policy engine (futuro microservizio)
├── libraries/                     # Librerie condivise
│   ├── core/                      # Fondamenta: config, log, errors
│   ├── events/                    # NATS event schemas e helpers
│   ├── domain/                    # Domain models (Asset, Order, etc.)
│   ├── analytics/                 # TA-Lib wrapper, regime detection
│   ├── indicators/                # Indicator plugins
│   ├── risk/                      # Risk metrics (VaR, Greeks, etc.)
│   ├── feature_store/             # Feature Store versionato
│   └── policy/                    # Policy Engine embeddato
├── plugins/                       # Plugin registrati
│   ├── indicators/
│   ├── brokers/
│   ├── risk_models/
│   ├── execution_algos/
│   ├── agents/
│   ├── strategies/
│   └── features/
├── infra/                         # Infrastruttura
│   ├── docker/                    # Docker Compose + Dockerfiles
│   ├── k8s/                       # Kubernetes manifests
│   └── terraform/                 # Terraform scripts
├── experiments/                   # Experiment output (gitignored)
├── tests/                         # Test di integrazione
├── docs/                          # Documentazione
│   ├── ADR/                       # Architecture Decision Records
│   ├── SPECIFICATION.md           # Questo documento
│   ├── DOMAIN_MODEL.md            # Modello di dominio
│   ├── EVENTS.md                  # Schema eventi NATS
│   ├── PLUGIN_API.md              # Plugin API contract
│   └── POLICY_ENGINE.md           # Policy Engine design
├── pyproject.toml                 # Python project config
├── Cargo.toml                     # Rust project config (future)
└── Makefile                       # Comandi comuni
```

---

## 7. Tech Stack (v1.0)

| Componente | Tecnologia | Motivazione |
|------------|-----------|-------------|
| Linguaggio Core | Python 3.12+ | Ecosistema quant, ML, agent framework |
| Hot Path | Rust (via PyO3) | Order book, event engine, fill validation |
| Agent Framework | LangGraph | Orchestrazione agenti con persistenza |
| GA Engine | DEAP | Maturo, flessibile, Python puro |
| Backtesting | nautilus_trader + vectorbt | HFT-grade + vectorized exploration |
| Event Bus | NATS | Leggero, persistente, Cloud Native |
| Tick Storage | QuestDB | High-throughput time-series |
| Metadata | PostgreSQL | Relazioni, audit, policy |
| Cache | Redis | Prezzi, feature cache |
| Logs | Loki | Log strutturati aggregati |
| Metrics | Prometheus | Monitoring e alerting |
| Vectors | Qdrant | Memoria semantica agenti, similarità |
| Dashboard (F1) | Streamlit | Rapid prototyping |
| API (F2) | FastAPI | Backend separation |
| UI (F3) | React/Next.js | Professional terminal |

---

## 8. Data Flow Principale

```
Market Data (WebSocket/REST)
    │
    ▼
┌─────────────────────┐
│   Ingestion Service  │──→ QuestDB (tick storage)
│   (NATS publisher)   │──→ Redis (live cache)
└─────────┬───────────┘
          │ event: market.tick / market.bar
          ▼
┌─────────────────────┐
│   Analytics Lib      │──→ Feature Store (versionato)
│   (regime, indicatori)│
└─────────┬───────────┘
          │ event: feature.updated / regime.updated
          ▼
┌─────────────────────┐
│   Genetic Engine     │──→ Experiment Registry
│   (solo backtest)    │
└─────────┬───────────┘
          │ event: strategy.evolved
          ▼
┌─────────────────────┐
│   Agent System       │──→ Knowledge Base (RAG)
│   (analyst→debate)   │
└─────────┬───────────┘
          │ event: signal.generated
          ▼
┌─────────────────────┐
│   Policy Engine      │──→ PostgreSQL (policy storage)
│   (embedded lib)     │
└─────────┬───────────┘
          │ event: policy.approved / policy.rejected
          ▼
┌─────────────────────┐
│   Execution Engine   │──→ Broker API
│   (Rust core)        │──→ QuestDB (trade storage)
└─────────────────────┘
          │ event: order.submitted / order.filled / trade.closed
          ▼
┌─────────────────────┐
│   Audit & Learning   │──→ PostgreSQL (audit) + Qdrant (similarità)
└─────────────────────┘
```

---

## 9. Plugin Architecture

Ogni plugin segue il ciclo di vita:

```python
register() → validate() → initialize() → start() → stop() → dispose()
```

Plugin types v1.0:

- `indicators`: Calcolano feature da dati di mercato
- `brokers`: Connettori a broker/exchange
- `risk_models`: Modelli di position sizing e risk metrics
- `execution_algos`: Algoritmi di execution (VWAP, TWAP, etc.)
- `agents`: Agenti LLM specializzati
- `strategies`: Strategie finite/evolute salvate come plugin
- `features`: Trasformazioni e alpha factors

Vedi `docs/PLUGIN_API.md` per il contratto completo.

---

## 10. Policy Engine

Libreria embeddata in `libraries/policy/`. Policy types:

- **HardLimit**: Blocca l'esecuzione (max loss, max exposure, max leverage)
- **SoftLimit**: Allerta senza bloccare (concentration warning, vol warning)
- **Compliance**: Regole SEC/MiFID/broker-specifiche
- **MarketCondition**: No trade in certi regimi di mercato
- **Governance**: Richiesta approvazione umana sopra certe soglie

Le policy sono valutate in catena. Ogni policy restituisce `Approved | Rejected | Warning`.

Vedi `docs/POLICY_ENGINE.md` per il design completo.

---

## 11. Genoma — Pipeline Decisionale

Il genoma definisce una pipeline decisionale completa, non una singola strategia:

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Universe  │──▶│ Feature  │──▶│  Signal  │──▶│  Filter  │──▶│   Risk   │──▶│Execution │
│  Genes    │   │  Genes   │   │  Genes   │   │  Genes   │   │  Genes   │   │  Genes   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

Ogni modulo contiene geni che il GA può evolvere (pesi, soglie, selezioni, parametri).

---

## 12. Experiment Registry

Ogni esecuzione di backtest, GA, o training modello produce un record:

```yaml
experiment_id: str          # univoco
timestamp: ISO8601
git_commit: str              # esatto commit
dataset_version: str         # versione dati
feature_version: str         # versione feature
genome_hash: str             # sha256 del genoma
random_seed: int
model_params: dict
metrics: dict                # Sharpe, Sortino, DD, etc.
artifacts: list[str]         # path a risultati
```

---

## 13. Knowledge Base

Database tecnico consultabile dagli agenti via RAG:

- Descrizione degli indicatori e fattori alpha
- Documentazione dei modelli di rischio
- Formule matematiche e riferimenti
- Note su anomalie di mercato
- Plugin documentation
- ADR e decisioni architetturali

PostgreSQL per contenuti strutturati, Qdrant per retrieval semantico.

---

## 14. Versioni e Governance della Specifica

- **v1.0**: 2026-07-06. **FROZEN come specifica research storica**.
- La living architecture è mantenuta in [ARCHITECTURE.md](ARCHITECTURE.md).
- La roadmap production/autopilot è mantenuta in
  [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md).
- Ogni modifica normativa richiede un nuovo ADR; gli ADR accettati vengono
  superseded, non riscritti.
- I principi safety-critical prevalgono sulle intenzioni v1 quando un ADR più
  recente lo dichiara esplicitamente.

---

## 15. Architecture Decision Records

L'indice normativo, inclusi status e supersessioni, è in
[ADR/README.md](ADR/README.md). Gli ADR 001, 002, 004 e 005 sono stati
superseded perché descrivevano una topologia aspirazionale diversa dal
repository e dai confini safety richiesti.
