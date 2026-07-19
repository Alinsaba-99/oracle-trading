# Deprecated Phase Plans Archive

> Tutti i documenti in questa directory sono **storici e non eseguibili**.

La roadmap canonica è
[../ORACLE_AUTOPILOT_MASTER_ROADMAP.md](../ORACLE_AUTOPILOT_MASTER_ROADMAP.md);
il checkpoint corrente è
[../ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).

## Perché sono deprecati

I piani Phase:

- mescolavano calendario, feature e readiness;
- contenevano decisioni duplicate o contraddittorie;
- usavano “completato” senza evidenza end-to-end;
- assumevano stack e directory non corrispondenti al repository;
- rendevano LLM, GA e UI prerequisiti della safety;
- non avevano una regola di regressione.

ADR-012 sostituisce questo modello con capability gate G0-G9.

## Regole archivio

- non aggiornare checkbox o stato;
- non aggiungere nuovi phaseN-plan;
- non usare decisioni locali come ADR;
- non citare metriche storiche come baseline corrente;
- mantenere il file soltanto per contesto e git archaeology.

## Mapping orientativo

| Piano storico | Gate attuali |
|---|---|
| Phase 0 Foundation | G0-G1 |
| Phase 1 Analytics | G2 e G5 |
| Phase 2 Backtesting | G5 |
| Phase 3/3.5 Genetics | Lane research dopo G5 |
| Phase 4 Multi-Agent | Lane intelligence dopo G1/G5 |
| Phase 5 Execution | G3-G4 |
| Phase 6 Dashboard | Lane operations |
| Phase 7 Autopilot | G6-G9 |
| Expression Alpha plan | Lane research dopo G5 |
| Atomic backlog v1 | Archivio della roadmap precedente, non backlog |

## File fuori dalla directory

Anche [../phase6-plan.md](../phase6-plan.md) e
[../plan-expression-alpha.md](../plan-expression-alpha.md) sono deprecati e
mantengono il percorso storico per non rompere link esterni.
