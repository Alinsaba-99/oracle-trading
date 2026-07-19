# ADR-010: Deterministic Execution Safety Boundary

**Data:** 2026-07-18
**Status:** ACCEPTED
**Related:** ADR-003, ADR-008, ADR-013

## Context

Oracle contiene LLM, agenti, GA e più adapter broker. Alcune composition root
accettano risk assente o fallback. Un sistema live non può affidare hard limits
a prompt, convenzioni o componenti opzionali.

## Decision drivers

- zero bypass;
- comportamento fail-closed;
- audit e riproducibilità;
- isolamento delle credenziali;
- recovery prevedibile.

## Decision

- LLM, Eliza, analyst e GA producono solo evidence, PortfolioPlan o TradeIntent.
- Mode guard, rule resolver, hard risk e OMS sono deterministici e obbligatori.
- OrderManager non è eseguibile in modalità non-paper senza una risk dependency
  certificata e un ledger snapshot.
- Solo OMS possiede credenziali execution.
- Dato, profilo, calendario, clock o ledger incerti producono DENY/PAUSE/FLATTEN.
- Live resta disabilitato fino a G7.
- Kill switch è separato dal decision plane e verifica lo stato broker-side.

## Consequences

### Positive

- failure LLM non diventa trade;
- hard limit testabili con property e replay test;
- security scope minimo.

### Negative

- più contratti e snapshot da passare;
- impossibile usare fallback “convenienti” in demo live-like;
- composition root esistenti devono essere migrate.

## Enforcement

- bypass matrix CLI/API/MAS/adapter;
- property test G4;
- credential scope test;
- startup guard;
- submit pubblico CLI non-paper fail-closed come mitigazione parziale;
- fire drill cancel + flatten.
