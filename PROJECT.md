# Project Oracle — Systematic Trading Intelligence Platform

> Piattaforma di ricerca quantitativa e trading automation safety-first.
> Stato corrente: **research-grade con paper test; live/funded non autorizzato**.

## Visione

Oracle combina analytics, ricerca alpha, sistemi multi-agente e infrastruttura
di esecuzione. L'obiettivo non è delegare il broker a un LLM, ma costruire un
sistema in cui:

- LLM e agenti propongono analisi e target di portafoglio;
- dati, contract math, risk e execution restano deterministici;
- ogni ordine attraversa un OMS durevole e un risk kernel non bypassabile;
- ogni decisione è riproducibile da codice, dati, configurazione e regole;
- la promozione procede per replay, paper, shadow, evaluation e funded.

Nessun rendimento, payout o superamento di challenge è garantibile.

## Stato operativo

| Area | Stato verificato | Limite principale |
|---|---|---|
| Foundation e CI | Verde localmente | Working tree storica non consolidata |
| Analytics | Research-grade | Data quality e point-in-time coverage incompleti |
| Backtesting | Research-only | Nessun motore event-driven certificato per qualification |
| Genetic research | Research-only | Non riaprire promotion finché G5 non è chiuso |
| Multi-Agent System | Prototipo avanzato | Confini e contratti ancora accoppiati al package agents |
| ElizaOS | Bridge read-only | Plugin hardening e advisory low ancora aperti |
| Prop policy | Modello e fixture iniziali | Enforcement live non ancora non-bypassabile |
| OMS e ledger | Parziali/in-memory | Nessuna durabilità o source of truth account |
| Broker | Adapter sperimentali | Nessun adapter futures certificato |
| API e dashboard | Funzionanti | API auth production e osservabilità reale da chiudere |
| Autopilot | Bloccato | Richiede i gate G0-G7 |

La CLI pubblica rifiuta ora l'invio a broker non-paper. Questo riduce un bypass,
ma non sostituisce il lavoro necessario per rendere risk, OMS e ledger
obbligatori in ogni composition root.

## Architettura sintetica

~~~text
Intelligence plane
  Analyst / LLM / Eliza / GA
           |
           v
Decision contracts
  PortfolioPlan -> TradeIntent
           |
           v
Safety control plane
  Mode guard -> Rule profile -> Hard risk -> Durable OMS
           |
           v
Execution adapters
  Paper / sandbox / certified broker
           |
           v
Authoritative state
  Ledger -> reconciliation -> audit
~~~

### Regola di autorità

| Componente | Può proporre | Può autorizzare | Può inviare |
|---|---:|---:|---:|
| Analyst, LLM, Eliza, GA | Sì | No | No |
| Portfolio compiler | Sì | No | No |
| Rule catalog e hard risk | No | Sì/No | No |
| OMS | No | Solo dopo risk | Sì |
| Broker adapter | No | No | Solo richieste OMS |
| Ledger riconciliato | No | Fonte di stato | No |

L'architettura corrente e il target sono descritti in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Stack tecnico

| Area | Scelta corrente | Ruolo e decisione |
|---|---|---|
| Runtime Python | Python 3.12 | Versione applicativa supportata |
| API | FastAPI + Pydantic 2 | Control/read API; production auth deve diventare fail-closed |
| Dashboard | React 18 + Vite 8 + TypeScript | UI operativa; Node 24 in CI |
| Agent orchestration | LangGraph + LiteLLM | Intelligence plane, fuori dalla hot path esecutiva |
| DataFrames | Polars, Pandas, NumPy | Polars preferito per nuovi path; conversioni esplicite |
| Research store | Parquet; DuckDB/Polars | Dataset e feature research, non account authority |
| Transactional state | SQLite oggi | PostgreSQL target per ledger/OMS production |
| Event transport | NATS/JetStream | Integrazione e audit delivery; non source of truth |
| Cache | In-memory; Redis previsto | Solo dati ricostruibili |
| Backtest discovery | vectorbt | Research-only; portabilità/licenza sotto review |
| Qualification engine | Nautilus candidate | Non certificato; PyBroker deprecato |
| Genetic engine | DEAP | Research-only |
| Broker | Paper, IBKR, CCXT, MT/MetaApi | Sperimentali; nessun live adapter certificato |
| Time-series DB | QuestDB in Compose | Deferred: adozione solo dopo benchmark e use case |
| Vector DB | Qdrant in Compose | Deferred: nessun requisito production provato |

Decisioni e supersessioni sono in [docs/ADR/README.md](docs/ADR/README.md).

## Baseline verificata il 18 luglio 2026

| Verifica | Risultato |
|---|---|
| Pytest | 1.605 passed, 2 skipped, 319 warning |
| Ruff | Pass |
| Ruff format | 397 file conformi |
| mypy strict | 261 source file, con override espliciti per genetics/PyBroker |
| uv lock --check | Pass |
| Python dependency audit | Nessuna vulnerabilità nota nell'ambiente installato; gate CI/SBOM ancora assente |
| Dashboard | 15 test passati; build Vite 8 riuscita |
| Dashboard audit | 0 vulnerability dopo upgrade Vite |
| Eliza bridge | Typecheck, build e 2 test passati |
| Eliza audit | 5 low, 0 moderate/high/critical |
| Clean install | uv sync --frozen riuscito in virtualenv temporanea |

Questi risultati dimostrano riproducibilità locale, non production readiness.
La CI è stata aggiornata per usare uv.lock e auditare entrambe le applicazioni
Node; serve ancora evidenza da un run remoto pulito.

## Rischi bloccanti

1. Risk manager opzionale in più composition root.
2. OMS, paper broker e account state in-memory.
3. API authentication disabilitata quando la key è assente.
4. ContractSpec, calendari futures e contract roll non certificati.
5. Backtest con fallback silenziosi e motori non equivalenti.
6. Docker/Compose non ancora production-grade.
7. Dependency e license policy Python incompleta.
8. Working tree con molte modifiche storiche non separate.

La review completa e le evidenze sono in
[docs/reviews/2026-07-18-project-review.md](docs/reviews/2026-07-18-project-review.md).

## Roadmap canonica

| Gate | Risultato |
|---|---|
| G0 | Baseline veritiera e riproducibile |
| G1 | Autorità, ambienti e confini applicativi |
| G2 | Verità futures e point-in-time data |
| G3 | Ledger, OMS e reconciliation durevoli |
| G4 | Hard risk non bypassabile |
| G5 | Research truth e strategy qualification |
| G6 | Paper e shadow operations |
| G7 | Certificazione di uno specifico programma |
| G8 | Funded limited rollout |
| G9 | Continuous operations |

Dettaglio e dipendenze:
[docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md](docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md).

## Prop-firm policy

Oracle distingue:

- AUTO_SUPPORTED: automazione esplicitamente consentita e certificata;
- ASSISTED_ONLY: analisi e controlli, ordine manuale;
- RESEARCH_ONLY: regole modellate, nessuna execution;
- UNSUPPORTED: dati o termini insufficienti; fail closed.

I profili sono versionati per firm, programma, stage, piattaforma, account,
vintage ed effective date. Regole e fonti:
[docs/PROP_FIRM_READINESS_ROADMAP.md](docs/PROP_FIRM_READINESS_ROADMAP.md).

## Prossimo lavoro eseguibile

1. consolidare la working tree e creare una baseline immutabile;
2. chiudere G0 con CI remota, warning budget, secret scan e SBOM;
3. eliminare i restanti bypass risk/API;
4. definire ambienti replay/paper/shadow/evaluation/funded;
5. implementare ContractSpec e calendari su un micro future;
6. progettare ledger, OMS, outbox e reconciliation;
7. certificare un motore event-driven prima di riaprire GA promotion.
