# ADR-005: Monorepo Structure

**Data:** 2026-07-06
**Status:** SUPERSEDED by ADR-008

---

## Context

Oracle ha componenti multipli: servizi, librerie, plugin, applicazioni, documentazione. Diverse strategie di organizzazione del repository.

## Decision

Usare **monorepo** con struttura `apps/` / `services/` / `libraries/` / `plugins/`.

## Rationale

- Vista unificata di tutto il sistema
- Modifiche cross-component in un solo commit
- CI/CD centralizzato
- Refactoring coordinato tra servizi e librerie
- Plugin vivono accanto al core
- Facile estrarre servizi in futuro quando necessario

## Structure

```
oracle/
├── apps/           # Deployable applications
├── services/       # Microservices
├── libraries/      # Shared libraries
├── plugins/        # Plugins
├── infra/          # Infrastructure
├── experiments/    # Experiment output
├── tests/          # Integration tests
└── docs/           # Documentation
```

## Conseguences

- `pyproject.toml` alla root con workspace configuration
- Ogni libreria in `libraries/` ha il proprio `pyproject.toml`
- Dipendenze interne risolte via `-e libraries/../` in dev mode
- Git hooks per lint su tutto il monorepo
- Build pipeline ottimizzata per cambiamenti incrementali
