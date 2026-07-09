# ADR-001: NATS come Event Bus

**Data:** 2026-07-06
**Status:** ACCEPTED
**Deciders:** (architect)

---

## Context

Oracle richiede comunicazione asincrona tra tutti i componenti: data ingestion, analytics, agent system, execution engine, dashboard. Nessun componente deve chiamare direttamente un altro.

Requisiti:
- Basse latenza (μs per messaggi semplici)
- Persistenza opzionale per eventi critici (order, trade)
- Pattern pub/sub per broadcast + request/reply per RPC
- Cloud Native (Kubernetes-ready)
- Supporto multi-language (Python, futuro Rust)

## Decision

Usare **NATS** come event bus unico.

## Rationale

- Latenza sub-millisecondo (2-5μs vs Kafka 2-5ms)
- Supporto nativo pub/sub, queue groups, request/reply
- JetStream per persistenza quando serve
- Semplice da operare (singolo binary 20MB)
- Eccellente client Python (nats-py)
- Cloud Native: deployabile su K8s con NATS Operator
- Più semplice di Kafka per il nostro carico (non siamo un data lake)

## Consequences

- Tutti gli eventi seguono schema versionato (vedi EVENTS.md)
- Ogni servizio dichiara `subjects` in ingresso e `subjects` in uscita
- Eventi critici (order, trade, fill) usano JetStream per persistenza
- Eventi non critici (tick, bar) in modalità fire-and-forget
- I plugin possono solo consumare/produrre eventi, mai chiamate dirette

## Alternatives Considerate

- **Kafka**: Overhead operativo e di latenza per il nostro use case. Sarebbe stato giusto se Oracle avesse dovuto processare petabyte di dati.
- **Redis Pub/Sub**: Non offre persistenza, garanzie di delivery o queue groups.
- **RabbitMQ**: Buono ma meno performante di NATS, e non Cloud Native.
- **ZeroMQ**: Embeddabile ma senza persistenza nativa.
