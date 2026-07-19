# ADR-002: QuestDB per Tick Storage

**Data:** 2026-07-06
**Status:** SUPERSEDED by ADR-009

---

## Context

Oracle deve immagazzinare e interrogare grandi volumi di dati time-series:
- Tick data (milioni di righe/giorno)
- Bar OHLCV (1m, 5m, 1h, 1d, 1w)
- Feature calcolate
- Trade history

Requisiti:
- Ingest throughput > 1M righe/secondo
- Query analitiche su finestre temporali (SELECT * FROM trades WHERE timestamp IN RANGE)
- JOIN tra time-series diverse (confronto prezzi, indicatori)
- Retention policy configurabile
- SQL standard per interrogazioni

## Decision

Usare **QuestDB** come time-series database primario.

## Rationale

- Ingest throughput: 1.5M righe/secondo su hardware consumer
- SQL nativo con estensioni time-series (LATEST ON, WHERE timestamp IN RANGE)
- Nessuna dipendenza Java (scritto in Java ma binario standalone + client Python)
- Partitioning temporale automatico
- Colonnare: compressione 10x rispetto a storage row-based
- Più veloce di InfluxDB e TimescaleDB nei benchmark time-series
- Embeddabile via Docker Compose

## Consequences

- Schema unico per tick, bar e trade
- Uso di `SYMBOL` type per ticker/categorie (ottimizzato per cardinalità)
- Partizionamento per mese (`PARTITION BY MONTH`)
- WAL per ingest parallela senza lock
- Client Python `questdb` per scrittura/lettura

## Alternatives Considerate

- **InfluxDB v2**: Query con Flux (non SQL), più complesso da integrare.
- **TimescaleDB (PostgreSQL)**: Buono ma ingest throughput inferiore a QuestDB.
- **ClickHouse**: Eccellente per analytics ma overhead operativo più alto per il nostro volume.
- **DuckDB**: Ottimo per analytics embedded, ma non progettato per ingest streaming.
