# ADR-011: Separate Backtest Discovery from Qualification

**Data:** 2026-07-18
**Status:** ACCEPTED

## Context

Oracle include vectorbt, PyBroker, un wrapper Nautilus e logica custom. Le
semantiche non sono ancora equivalenti; il wrapper Nautilus usa modelli equity,
fallback e ricostruzione P&L non certificati per futures. PyBroker non è
installato dall'extra omonimo e introduce un terzo percorso.

## Decision drivers

- velocità durante la ricerca;
- realismo durante la promotion;
- parity con paper/live;
- portabilità e licenza;
- ridurre motori sovrapposti.

## Decision

- mantenere una lane vectorized per discovery e screening;
- certificare un solo motore event-driven per qualification;
- PyBroker è DEPRECATED e non fa parte del percorso canonico;
- Nautilus è candidato, non decisione irrevocabile;
- il candidato deve usare ContractSpec, sessioni, costi, sizing e risk condivisi;
- ogni strategia promossa passa da parity, leakage, WFA, holdout e stress;
- vectorbt resta RESEARCH_ONLY finché portabilità macOS x86 e Commons Clause non
  ricevono decisione legale/tecnica;
- la licenza LGPL del candidato Nautilus entra nell'inventario e nella review
  della modalità di distribuzione.

## Consequences

### Positive

- ricerca veloce senza confondere discovery e prova economica;
- un solo standard di promotion;
- meno drift tra backtest e paper.

### Negative

- serve riscrivere o isolare adapter esistenti;
- parity test hanno costo;
- alcuni risultati storici non saranno confrontabili.

## Enforcement

- report indica discovery_engine e qualification_engine;
- nessun risultato vectorized autorizza paper da solo;
- G5 non passa finché il motore event-driven non è certificato;
- license inventory e platform matrix in CI/release.
