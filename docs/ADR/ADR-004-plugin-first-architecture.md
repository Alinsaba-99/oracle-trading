# ADR-004: Plugin-First Architecture

**Data:** 2026-07-06
**Status:** ACCEPTED

---

## Context

Oracle deve essere estensibile senza modificare il core. Nuovi indicatori, broker, agenti, modelli di rischio, algoritmi di execution, strategie devono poter essere aggiunti da chiunque senza toccare il codice base.

## Decision

Adottare architettura **Plugin-First** con ciclo di vita standardizzato.

## Rationale

- Separation of concerns: il core non sa cosa fanno i plugin, solo che seguono il contratto
- Community contributions senza modifiche al core
- Ogni plugin è testabile indipendentemente
- E' possibile disabilitare plugin senza effetti collaterali
- Il GA produce strategie come plugin, che entrano nel ciclo di vita standard

## Plugin Lifecycle

```python
register()      # Plugin manager scopre e registra il plugin
validate()      # Verifica configurazione e dipendenze (fail fast)
initialize()    # Alloca risorse, connette API, carica modelli
start()         # Avvia processing (subscribe a eventi NATS)
stop()          # Ferma processing gracefulmente
dispose()       # Rilascia risorse
```

## Plugin Contract

Ogni plugin deve esporre:

```python
class OraclePlugin(BasePlugin):
    name: str                      # Nome univoco
    version: str                   # Semver
    description: str               # Descrizione
    dependencies: list[str]        # Altri plugin richiesti
    subjects_in: list[str]         # NATS subjects consumati
    subjects_out: list[str]        # NATS subjects emessi
    config_schema: dict            # JSON Schema per validazione config
```

## Plugin Discovery

I plugin sono scoperti automaticamente da `plugins/` directory + package entry points.

## Consequences

- Tutti i plugin seguono lo stesso ciclo di vita
- Core non ha dipendenza dai plugin specifici, solo dal BasePlugin
- Plugin possono essere in Python, futuro Rust via PyO3
- Documentazione plugin obbligatoria per la registrazione
- Vedi PLUGIN_API.md per il contratto completo
