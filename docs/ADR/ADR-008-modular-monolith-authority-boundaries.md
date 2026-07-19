# ADR-008: Modular Monolith and Authority Boundaries

**Data:** 2026-07-18
**Status:** ACCEPTED
**Supersedes:** ADR-001, ADR-004, ADR-005

## Context

Gli ADR iniziali descrivevano comunicazione universale via NATS, plugin-first e
una struttura apps/services/libraries/plugins. Il repository reale usa package
Python coesi, molte chiamate in-process e un solo ciclo di deploy. Forzare ogni
interazione su NATS o estrarre servizi prima di avere ledger e risk durevoli
aumenterebbe failure mode e complessità operativa.

## Decision drivers

- provare che il percorso safety-critical è non bypassabile;
- transazioni e failure esplicite;
- mantenere cambiamenti cross-domain atomici;
- separare intelligence, research ed execution;
- consentire una futura estrazione senza progettare microservizi prematuri.

## Options considered

### Event-driven microservices immediati

Buon isolamento futuro, ma transazioni distribuite, più deployment e maggiore
superficie di recovery prima di avere requisiti di scala.

### Plugin-first universale

Estensibile, ma inadatto a confini hard-risk: plugin dinamici e discovery non
devono poter cambiare la hot path live.

### Modular monolith con ports and adapters

Mantiene un deployment, dipendenze inward e porte esplicite. Eventi asincroni
restano disponibili alle boundary.

## Decision

Adottare un modular monolith come control plane iniziale.

- core/domain e application/contracts non dipendono da adapter;
- apps sono composition root;
- broker, database, NATS, LLM e provider dati sono adapter;
- mode → risk → OMS → broker usa chiamate deterministiche in-process;
- eventi esterni partono da transactional outbox;
- plugin dinamici sono ammessi solo in extension point non safety-critical;
- un servizio viene estratto soltanto con ADR basato su ownership, SLO o
  isolamento di failure misurato.

## Consequences

### Positive

- risk e transazioni più verificabili;
- meno failure distribuiti;
- dependency graph testabile;
- NATS resta utile senza diventare source of truth.

### Negative

- scaling indipendente limitato;
- richiede disciplina sui package boundary;
- il refactor dei contratti oggi in agents ha costo.

## Enforcement

- architecture dependency test;
- nessun import execution → agents;
- nessun import policy → implementazione execution;
- outbox test prima di pubblicare eventi autorevoli;
- G1 e G3 della master roadmap.
