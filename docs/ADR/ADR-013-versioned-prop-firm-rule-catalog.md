# ADR-013: Versioned Prop-Firm Rule Catalog

**Data:** 2026-07-18
**Status:** ACCEPTED
**Related:** ADR-010

## Context

Le prop firm cambiano regole per programma, stage, piattaforma, account size e
vintage. Percentuali generiche non rappresentano trailing lock, daily reset,
contract tier, automation, device o news policy.

## Decision drivers

- fail-closed su regole incerte;
- supportare account legacy;
- audit di ogni allow/deny;
- distinguere capacità tecnica e termini consentiti;
- demotion rapida dopo cambiamenti.

## Decision

Ogni profilo è immutabile e indicizzato da firm, program, stage, platform,
account_size, account_vintage, rule_version ed effective_from.

Il profilo include fonti, normalized hash, checked_at, support mode,
automation/device policy, economics, risk e trading restrictions.

Support mode ammessi:

- AUTO_SUPPORTED;
- ASSISTED_ONLY;
- RESEARCH_ONLY;
- UNSUPPORTED.

Default: UNSUPPORTED. Un campo necessario UNKNOWN impedisce AUTO_SUPPORTED.
LLM non interpreta pagine o termini nella hot path.

## Consequences

### Positive

- decisioni riproducibili;
- legacy account protetti;
- automazione e regole modellate separatamente.

### Negative

- costo continuo di source review;
- molte fixture e migration;
- serve owner legale/operativo.

## Enforcement

- golden test da esempi ufficiali;
- source freshness e hash;
- quarterly review e demotion;
- decision contract con reason code/profile version;
- G4 e G7.
