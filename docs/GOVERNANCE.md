# Oracle Trading — Canonical Documentation Hierarchy

**Ultimo aggiornamento:** 2026-07-22
**Regola:** ogni documento ha autorità su un solo dominio. Nessuna tabella gate/stato in più di un file.

## La gerarchia

```
ROADMAP (perché)
  ↓
STATUS (cosa — checkpoint)
  ↓
BACKLOG (come — work package)
  ↓
ADR (decisioni normative)
  ↓
Reports (evidenza verificata)
```

## 1. Roadmap — docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md

- Descrive i gate G0–G9, obiettivi, deliverable minimi, exit evidence e sequenza
- Definisce i principi non negoziabili e i workstream (S, D, I, O)
- **Non contiene** stati aggiornati al minuto — quelli sono in STATUS
- **Non contiene** task atomiche — quelle sono in BACKLOG
- Modifiche: richiedono ADR

## 2. Status — docs/ORACLE_AUTOPILOT_STATUS.md

- Checkpoint operativo con HEAD, working tree, gate status e baseline verificata
- **Unico** documento con la matrice gate/stato fresca
- Deve essere aggiornato a ogni sessione di lavoro significativa
- Contiene la tabella `Gate | Stato | Evidenza sintetica` — autoritativa

## 3. Backlog — docs/ORACLE_AUTOPILOT_BACKLOG.md

- Task atomiche organizzate per gate, con criteri di done e dipendenze
- **Non contiene** tabelle gate/stato — quelle sono in STATUS
- Include note tecniche sulle milestone chiuse

## 4. ADR — docs/ADR/

- Decisioni normative immutabili: contesto, alternative, conseguenze, enforcement
- Ogni ADR ha un lifecycle (PROPOSED → ACCEPTED → SUPERSEDED)
- L'indice in docs/ADR/README.md è la tabella di marcia normativa

## 5. Reports — docs/reports/

- Evidenza verificata di gate/milestone chiusi
- Immutabili dopo la pubblicazione (hashati)

## File non più autoritativi

| File | Ora | Sostituito da |
|------|-----|---------------|
| `PROJECT.md` | Nota introduttiva informale | STATUS.md |
| `docs/SPECIFICATION.md` | **FROZEN** — solo storico | ARCHITECTURE.md + ADR |
| `docs/EVENTS.md` | **FROZEN** — solo storico | ADR-008 + nats docs |
| `docs/plans/oracle-autopilot-atomic-backlog-v1.md` | **ARCHIVIO** | BACKLOG.md |
| `docs/plans/oracle-autopilot-gate-backlog-v2.md` | **ARCHIVIO** | BACKLOG.md |
| `phase*-plan.md` (root) | **ARCHIVIO** | ROADMAP.md + ADR |
| `testing-report.md` | **ARCHIVIO** | STATUS.md + reports/ |
