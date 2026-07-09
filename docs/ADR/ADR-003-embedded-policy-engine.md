# ADR-003: Policy Engine Embeddato (Libreria, non Microservizio)

**Data:** 2026-07-06
**Status:** ACCEPTED

---

## Context

Oracle richiede un sistema di policy per:
- Risk limits (max loss, max exposure, max leverage)
- Compliance (regole SEC/MiFID/broker-specifiche)
- Market condition filters (no trade in certi regimi)
- Governance (approvazione umana sopra soglie)

Opzioni:
1. **Microservizio separato** (`services/policy/`) con API HTTP/gRPC
2. **Libreria embeddata** (`libraries/policy/`) chiamata in-process

## Decision

Usare **libreria embeddata** per v1.0.

## Rationale

- Il Policy Engine non ha dati propri, non scala indipendentemente, non ha ciclo di vita separato
- È una funzione pura: `PolicyResult = evaluate(portfolio, signal, market_state)`
- La latenza di HTTP/RPC/NATS request/reply per ogni valutazione è overhead inutile
- I test unitari sono triviali: `assert policy.evaluate(...) == Approved`
- Le policy sono configurabili via YAML/JSON, non richiedono deploy separato
- In futuro si potrà estrarre a microservizio se Oracle cresce (interfacce già pulite)

## Consequences

- Policy Engine in `libraries/policy/`
- API: `PolicyEngine.evaluate(context: PolicyContext) → PolicyResult`
- Policy definite in YAML (vedi POLICY_ENGINE.md)
- Le policy sono caricate all'avvio e possono essere ricaricate a caldo
- Decision Orchestration Engine chiama policy engine prima di ogni execution

## Alternatives

- **Microservizio**: Giustificato solo se Oracle avesse più nodi indipendenti con policy diverse.
