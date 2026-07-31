# ADR-007: Experiment Registry

**Data:** 2026-07-06
**Status:** ACCEPTED

---

## Context

Ogni esecuzione del Genetic Engine, backtest, o training modello deve essere riproducibile. Senza un registro centrale, dopo mesi diventa impossibile:
- Confrontare due strategie su basi oggettive
- Ricreare un risultato passato
- Tracciare quale versione del codice ha prodotto quali metriche
- Identificare regressi nel tempo

## Decision

Introdurre **Experiment Registry** obbligatorio per ogni esecuzione.

## Schema

```yaml
experiment_id: str              # "exp_20260706_ga_047"
type: "backtest | ga_run | training | paper_trade"
timestamp: datetime
git_commit: str                 # Commit esatto
status: "running | completed | failed"

# Versioning
dataset_version: str            # Versione dati (es: "yahoo_v20260701")
feature_version: str            # Versione feature (es: "features_v2.3")
oracle_version: str             # Versione Oracle

# Experiment
genome_hash: str                # SHA256 del genoma (se GA)
genome_path: str                # Path al genoma (se GA)
config_hash: str                # SHA256 della configurazione
random_seed: int

# Risultati
metrics: dict                   # Sharpe, Sortino, Calmar, MaxDD, WinRate, etc.
artifacts: list[str]            # Path ai file generati (parquet, json, plots)
duration_seconds: float
```

## Storage

- PostgreSQL: record strutturato per ogni experiment
- Filesystem (`experiments/`): artefatti (backtest results, strategie, plot)
- `experiments/experiments.db` come SQLite locale per sviluppo
- Ogni experiment ha una directory: `experiments/{experiment_id}/`

## Retrieval API

```python
registry.search(metric="sharpe", min=1.5, max_dd=-0.2)
registry.compare(["exp_001", "exp_047"])
registry.reproduce("exp_047")  # Ricrea esattamente lo stesso esperimento
registry.latest(type="ga_run")
```

## Consequences

- Ogni esecuzione di backtest o GA DEVE passare dal Registry
- Se manca dataset_version → errore, non si esegue
- Se working directory non è pulita (uncommitted changes) → warning
- Gli artefatti sono referenziati ma non versionati nel registro (path-based)
- Metriche sono indicizzate per query (Sharpe > 1.5 AND MaxDD > -0.2)
