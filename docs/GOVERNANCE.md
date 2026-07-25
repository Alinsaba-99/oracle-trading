# Oracle Trading — Canonical Documentation Hierarchy

**Ultimo aggiornamento:** 2026-07-25
**Regola:** ogni documento ha autorità su un solo dominio. Nessuna tabella gate/stato in più di un file.

## La gerarchia

```
PROJECT.md       (perimetro, regole non negoziabili, single intro)
ROADMAP (perché) → root/ROADMAP.md
STATUS (cosa)    → docs/ORACLE_AUTOPILOT_STATUS.md (unica tabella gate/stato)
BACKLOG (come)   → BACKLOG.md (single source of task atomiche)
ARCH (corrente)  → docs/ARCHITECTURE.md (corrente + target)
RUNBOOK (oper)   → docs/RUNBOOK.md
DATA (fonti)     → docs/DATA_SOURCES.md
POLICY (firm)    → docs/PROP_FIRM_READINESS_ROADMAP.md
ADR              → docs/ADR/  (decisioni normative immutabili)
REPORTS          → docs/reports/ (evidenza verificata, hashata)
PLANS (archivio) → docs/plans/ (Phase 0-7, vecchi backlog, non eseguibili)
```

## 1. PROJECT.md (root)

- Vision, scope, principio di autorità, stack tecnico essenziale
- **Non** contiene la matrice gate/stato (vedi STATUS)
- **Non** contiene task atomiche (vedi BACKLOG)
- Modifiche: nessun vincolo speciale (è documentazione informale)

## 2. ROADMAP.md (root)

- Gate G0–G9, obiettivi, deliverable minimi, exit evidence, sequenza
- Principi non negoziabili e workstream (S, D, I, O)
- Link a STATUS, BACKLOG, ADR, PLAN archivio
- Modifiche: richiedono ADR

## 3. STATUS.md — docs/ORACLE_AUTOPILOT_STATUS.md

- Checkpoint operativo con HEAD, working tree, gate status e baseline verificata
- **Unico** documento con la matrice gate/stato fresca
- Rischi residui e "stato reale vs dichiarato"
- Aggiornato a ogni sessione di lavoro significativa
- La tabella gate/stato qui è **autoritativa**

## 4. BACKLOG.md (root)

- Task atomiche organizzate per gate, ID stabile **BL-NNN**
- Ogni task ha: priorità, AC, owner suggerito, link al gate
- DoD globale definito qui
- **Non** contiene tabelle gate/stato
- Note su milestone chiuse in coda

## 5. ADR — docs/ADR/

- Decisioni normative immutabili: contesto, alternative, conseguenze, enforcement
- Lifecycle: PROPOSED → ACCEPTED → SUPERSEDED
- L'indice `docs/ADR/README.md` è la mappa normativa

## 6. Reports — docs/reports/ (futuro)

- Evidenza verificata di gate/milestone chiusi
- Path proposto: `docs/reports/{gate}/{milestone}.md`
- Immutabili dopo la pubblicazione (hash commit in header)

## File archiviati o ruolo nuovo

| File | Ruolo | Sostituito da |
|------|-------|---------------|
| `PROJECT.md` | **ROOT single source of truth** perimetro + regole non negoziabili | (mantenuto) |
| `docs/SPECIFICATION.md` | **FROZEN** — solo storico | ARCHITECTURE.md + ADR |
| `docs/EVENTS.md` | **FROZEN** — solo storico | ADR-008 + NATS docs |
| `docs/plans/oracle-autopilot-atomic-backlog-v1.md` | **ARCHIVIO** | BACKLOG.md (root) |
| `docs/plans/oracle-autopilot-gate-backlog-v2.md` | **ARCHIVIO** | BACKLOG.md (root) |
| `phase0-plan.md` … `phase5-plan.md`, `phase3.5*.md`, `phase4-tasks.md` | **ARCHIVIO** (spostati in docs/plans/) | ROADMAP.md |
| `docs/phase6-plan.md` | **ARCHIVIO** (spostato in docs/plans/) | ARCHITECTURE.md sezione Operations |
| `docs/plan-expression-alpha.md` | **ARCHIVIO** (spostato in docs/plans/) | lane research dopo G5 |
| `docs/plan-integration-inalpha-varrd.md` | valido ma da ridurre | vedi [BACKLOG.md G6-I](../BACKLOG.md) |
| `docs/ORACLE_AUTOPILOT_MASTER_ROADMAP.md` | rimosso dalla docs/ (è ora root ROADMAP.md) | root ROADMAP.md |
| `docs/ORACLE_AUTOPILOT_BACKLOG.md` | rimosso (è ora root BACKLOG.md) | root BACKLOG.md |
| `testing-report.md` | **ARCHIVIO** | STATUS.md + reports/ |
