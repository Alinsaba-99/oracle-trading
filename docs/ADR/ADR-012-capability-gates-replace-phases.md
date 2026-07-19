# ADR-012: Capability Gates Replace Phase Plans

**Data:** 2026-07-18
**Status:** ACCEPTED

## Context

I piani Phase mescolano tempo, feature e stato dichiarato. Il precedente master
backlog conteneva 39 milestone e 975 task, esattamente 25 per milestone: dettaglio
difficile da mantenere e non proporzionale al rischio. Alcune Phase risultavano
“complete” pur senza ledger, contract math o enforcement non bypassabile.

## Decision drivers

- stato basato su evidenza;
- regressione esplicita;
- separare safety da feature opzionali;
- ridurre document drift;
- consentire lavoro parallelo senza saltare prerequisiti.

## Decision

- usare gate G0-G9 con entry/exit evidence;
- mantenere soltanto work package immediatamente eseguibili;
- archiviare i piani Phase come storico non normativo;
- LLM, Eliza e GA sono lane parallele, non prerequisiti della safety;
- ogni gate può tornare REGRESSED;
- issue tracker/report di milestone contiene task atomiche, non la roadmap.

## Consequences

### Positive

- priorità guidata da rischio e outcome;
- meno falsa completezza;
- roadmap leggibile e riprendibile.

### Negative

- vecchi riferimenti Phase devono essere rimossi;
- serve disciplina nel produrre verification report;
- task storiche non hanno mapping uno-a-uno.

## Enforcement

- banner di deprecazione su ogni piano storico;
- plans/README.md come indice archivio;
- PROJECT e STATUS mostrano solo gate;
- nessun nuovo file denominato phaseN-plan.
