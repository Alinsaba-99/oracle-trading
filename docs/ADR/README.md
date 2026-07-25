# Architecture Decision Records

Gli ADR catturano decisioni normative, alternative e conseguenze. La living
architecture è in [../ARCHITECTURE.md](../ARCHITECTURE.md).

## Lifecycle

- PROPOSED
- ACCEPTED
- REJECTED
- DEPRECATED
- SUPERSEDED

Un ADR ACCEPTED non viene riscritto per cambiare decisione: un nuovo ADR lo
supersede e l'indice viene aggiornato.

## Indice

| ADR | Titolo | Stato | Relazione |
|---|---|---|---|
| [001](ADR-001-nats-event-bus.md) | NATS come event bus universale | SUPERSEDED | ADR-008 limita NATS alle boundary asincrone |
| [002](ADR-002-questdb-tick-storage.md) | QuestDB come TSDB primario | SUPERSEDED | ADR-009 rende l'adozione benchmark-driven |
| [003](ADR-003-embedded-policy-engine.md) | Policy engine embedded | ACCEPTED | Rafforzato da ADR-010 |
| [004](ADR-004-plugin-first-architecture.md) | Plugin-first universale | SUPERSEDED | ADR-008 limita plugin alle extension boundary |
| [005](ADR-005-monorepo-structure.md) | Monorepo apps/services/libraries/plugins | SUPERSEDED | ADR-008 conserva monorepo ma adotta bounded packages reali |
| [006](ADR-006-genome-pipeline-architecture.md) | Genome pipeline | ACCEPTED, RESEARCH-ONLY | Non autorizza promotion |
| [007](ADR-007-experiment-registry.md) | Experiment registry | ACCEPTED | Storage governato da ADR-009 |
| [008](ADR-008-modular-monolith-authority-boundaries.md) | Modular monolith e authority boundary | ACCEPTED | Supersede 001, 004, 005 |
| [009](ADR-009-data-state-storage-strategy.md) | Data e state storage strategy | ACCEPTED | Supersede 002 |
| [010](ADR-010-deterministic-execution-safety-boundary.md) | Deterministic execution safety boundary | ACCEPTED | Completa 003 |
| [011](ADR-011-backtest-discovery-qualification.md) | Discovery vs qualification backtest | ACCEPTED | PyBroker deprecated; Nautilus candidate |
| [012](ADR-012-capability-gates-replace-phases.md) | Capability gate al posto delle Phase | ACCEPTED | Depreca i piani Phase |
| [013](ADR-013-versioned-prop-firm-rule-catalog.md) | Rule catalog prop-firm versionato | ACCEPTED | Support mode fail-closed |
| [014](ADR-014-m31-evidence-loss.md) | M31 replay/regime evidence loss | ACCEPTED | G5 dichiarato REGRESSED, dataset lineage GAP |
| [015](ADR-015-topstep-automation-policy.md) | Topstep automation / VPS / device policy | ACCEPTED | Local-only deployment; vedi BL-071 |
| [015 - proposto](template.md) | (placeholder) | — | superseded dalla riga precedente |

## Come creare un ADR

1. Copiare [template.md](template.md).
2. Assegnare il prossimo numero.
3. Dichiarare driver, alternative, reversibilità e failure mode.
4. Collegare work package e test di enforcement.
5. Aggiornare questo indice.

## Review checklist

- problema e perimetro sono specifici;
- almeno due alternative reali sono considerate;
- conseguenze negative sono esplicite;
- source of truth e ownership sono definite;
- security, failure e rollback sono considerati;
- esiste un test o un gate che rende la decisione verificabile.

## ADR proposti (PROPOSED → da accettare o rigettare)

Chi prende in mano il backlog deve:

1. Per ogni "MUST BE ADR" nel [BACKLOG.md](../../BACKLOG.md), scrivere un
   nuovo file `ADR-NNN-titolo.md` da `template.md` e aggiungerlo qui con
   stato PROPOSED.
2. Ottenuto il consenso (reviewer + approver nel log), promuovere a
   ACCEPTED con `git mv`-style update dell'indice (commit + CHANGELOG
   header).
