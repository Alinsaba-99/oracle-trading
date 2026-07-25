# Deprecated Phase Plans Archive

> Tutti i documenti in questa directory sono **storici e non eseguibili**.

La roadmap canonica è [`../../ROADMAP.md`](../../ROADMAP.md); il checkpoint
corrente è [`../ORACLE_AUTOPILOT_STATUS.md`](../ORACLE_AUTOPILOT_STATUS.md);
il backlog eseguibile è [`../../BACKLOG.md`](../../BACKLOG.md).

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
| Atomic backlog v1/v2 | Archivio dei vecchi backlog, non eseguibile |

## File in root (anch'essi archiviati)

- `phase0-plan.md` … `phase5-plan.md` (spostati qui il 25-lug)
- `phase3.5-plan.md`, `phase3.5.1-plan.md` (spostati qui)
- `phase4-tasks.md` (spostato qui)
- `docs/phase6-plan.md` — dashboard v1, superato
- `docs/plan-expression-alpha.md` — expression plan deprecato
- `docs/plan-integration-inalpha-varrd.md` — G6-I source plan (alcune parti
  rimaste valide, vedi [BACKLOG.md G6-I](../../BACKLOG.md))
