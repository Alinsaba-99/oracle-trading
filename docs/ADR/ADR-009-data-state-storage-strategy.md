# ADR-009: Data and State Storage Strategy

**Data:** 2026-07-18
**Status:** ACCEPTED
**Supersedes:** ADR-002
**Related:** ADR-007

## Context

Il repository usa SQLite, JSON, Parquet e memoria. Compose include PostgreSQL,
QuestDB, Redis e Qdrant, ma nessuno è ancora il source of truth production.
Dichiarare QuestDB primario senza benchmark crea lock-in e documentazione
aspirazionale.

## Decision drivers

- distinguere stato economico da dataset research;
- durabilità e transazioni per ordini/fill/ledger;
- riproducibilità point-in-time;
- operabilità semplice;
- evitare infrastruttura non giustificata.

## Decision

- PostgreSQL è il source of truth production per ledger, OMS, account,
  reconciliation, rule metadata, decision e audit index.
- SQLite è ammesso per dev/test e inbox locali, con schema compatibile dove
  ragionevole.
- Parquet con DuckDB/Polars è lo storage primario dei dataset e feature research.
- NATS/JetStream è trasporto e delivery, non autorità.
- Redis è cache ricostruibile.
- Object/filesystem storage conserva raw data e artifact immutabili.
- QuestDB è DEFERRED finché un benchmark reale non prova SLO non raggiungibili.
- Qdrant è DEFERRED a un use case intelligence con ADR e retention review.

## Consequences

### Positive

- una sola autorità transazionale;
- separazione OLTP/research;
- failure Redis/NATS non perde stato economico;
- adozione TSDB guidata da misure.

### Negative

- PostgreSQL richiede migrazioni, backup e operations;
- dataset e metadata necessitano lineage esplicito;
- eventuale QuestDB futuro richiederà adapter e dual-write controllato.

## Enforcement

- state authority matrix in ARCHITECTURE.md;
- test restart/reconciliation G3;
- nessun saldo o posizione ricostruito da NATS, Redis o dashboard;
- benchmark ADR prima di introdurre QuestDB/Qdrant nel runtime.
