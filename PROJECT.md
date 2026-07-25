# Project Oracle — Systematic Trading Intelligence Platform

> **Stato 2026-07-25**: research-grade con paper test parziali. Live/funded
> non autorizzato. Per lo stato gate-per-gate autorevole vedi
> **[STATUS.md](docs/ORACLE_AUTOPILOT_STATUS.md)**. Per il backlog eseguibile
> vedi **[BACKLOG.md](BACKLOG.md)**. Per la roadmap canonica vedi
> **[ROADMAP.md](ROADMAP.md)**.

## Visione

Oracle combina analytics, ricerca alpha, sistemi multi-agente e
infrastruttura di esecuzione. L'obiettivo non è delegare il broker a un
LLM, ma costruire un sistema in cui:

- LLM e agenti propongono analisi e target di portafoglio;
- dati, contract math, risk e execution restano deterministici;
- ogni ordine attraversa un OMS durevole e un risk kernel non bypassabile;
- ogni decisione è riproducibile da codice, dati, configurazione e regole;
- la promozione procede per replay, paper, shadow, evaluation e funded.

Nessun rendimento, payout o superamento di challenge è garantibile.

## Tabella operativa (sintesi — fonte autorevole: STATUS.md)

| Area | Stato | Limite |
|---|---|---|
| Foundation e CI | ✅ verde locale | 321 warnings; CI remota e SBOM ancora da cablare |
| Analytics | research-grade | Point-in-time OK; intraday futures non disponibile |
| Backtesting | discovery + replay v1 | G5 REGRESSED — M31 da rifare post-BL-022 |
| Factor timing | v1 (26 test verdi) | port cross-asset non ancora |
| Genetic research | research-only | nessuna promotion in attesa di G5 |
| Multi-Agent / ElizaOS | read-only | LLM mai in hot path esecutiva |
| Prop policy | versioned fixtures | Topstep TC 50K certificato solo per replay storico; **scegliere una firm per G7 ancora da fare** (BL-100) |
| OMS e ledger | PostgreSQL path attivo | Postgres obbligatorio per production; memoria ancora default |
| Broker | Paper realistico + adattori sperimentali | Nessuno certificato per live |
| API + dashboard | funzionanti in DEV | hardening prod ancora da certificare |
| Autopilot | gate G6 REJECTED | blocca su [BL-020..024](BACKLOG.md) (regime rebalance + 100 sessioni paper) |

## Architettura sintetica

```text
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
```

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

## Stack tecnico (essenziale — vedi ADR per le decisioni)

| Area | Scelta | Ruolo |
|---|---|---|
| Runtime | Python 3.12 | versione applicativa |
| API | FastAPI + Pydantic 2 | control/read API; prod auth fail-closed |
| Dashboard | React 18 + Vite 8 + TS | UI operativa; Node 24 |
| Agent orchestration | LangGraph + LiteLLM | intelligence plane, fuori hot path |
| DataFrames | Polars (preferito), Pandas, NumPy | — |
| Research store | Parquet + DuckDB/Polars | dataset research, non account authority |
| Transactional state | PostgreSQL production; SQLite dev/test | ADR-009 |
| Event transport | NATS/JetStream | integrazione e audit, non source of truth |
| Backtest discovery | vectorbt | research-only |
| Qualification engine | Oracle event-driven paper v1 | unico engine certificato; Nautilus candidato non ancora |
| Genetic engine | DEAP | research-only |
| Broker | Paper, IBKR, CCXT, MT5/MetaApi | sperimentali; nessun live adapter |
| TSDB | QuestDB | DEFERRED (ADR-009) |
| Vector DB | Qdrant | DEFERRED (ADR-009) |

Decisioni e supersessioni: [docs/ADR/README.md](docs/ADR/README.md).

## Roadmap canonica

| Gate | Nome | Stato corrente |
|---|---|---|
| G0 | Baseline veritiera e riproducibile | ✅ PASSED |
| G1 | Autorità, ambienti e confini | ✅ PASSED |
| G2 | Verità futures e PIT data | 🟡 PARTIAL |
| G3 | Ledger, OMS e reconciliation durevoli | ✅ PASSED |
| G4 | Hard risk non bypassabile | ✅ PASSED |
| G5 | Research truth e strategy qualification | ❌ REGRESSED |
| G6 | Paper e shadow operations | 🟡 REJECTED |
| G7 | Certificazione programma prop-firm | ⚪ NOT_STARTED |
| G8 | Funded limited rollout | ⚪ NOT_STARTED |
| G9 | Continuous operations | ⚪ NOT_STARTED |

Stato autorevole, evidenza e rischi residui:
[docs/ORACLE_AUTOPILOT_STATUS.md](docs/ORACLE_AUTOPILOT_STATUS.md).

## Prop-firm policy

Oracle distingue:

- `AUTO_SUPPORTED`: automazione esplicitamente consentita e certificata;
- `ASSISTED_ONLY`: analisi e controlli, ordine manuale;
- `RESEARCH_ONLY`: regole modellate, nessuna execution;
- `UNSUPPORTED`: dati o termini insufficienti; fail closed.

Profili sono versionati per firm, programma, stage, piattaforma, account,
vintage ed effective date. Regole e fonti:
[docs/PROP_FIRM_READINESS_ROADMAP.md](docs/PROP_FIRM_READINESS_ROADMAP.md).

## Per partire da qui

1. Leggi [STATUS.md](docs/ORACLE_AUTOPILOT_STATUS.md) per lo stato gate-by-gate.
2. Apri [BACKLOG.md](BACKLOG.md), prendi il primo BL-001 (pin ES_1d).
3. Per cambiare il piano settimanale, parti dagli ADR rilevanti prima di toccare il codice.
4. Per operare, vedi [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Cose che NON vanno fatte senza approval

- Modificare il profilo versionato di una prop-firm senza ADR.
- Inviare ordini live senza G7 PASSED.
- Cambiare regole del risk kernel senza ADR-010.
- Aggiungere servizi (NATS, Qdrant, …) senza ADR che dimostri il bisogno.
- Trattare l'edge osservato (RSI mean-rev in choppy) come universalmente
  valido: è **regime-conditional** (vedi
  [docs/AUDIT_FINDINGS.md](docs/AUDIT_FINDINGS.md) §3.3).
