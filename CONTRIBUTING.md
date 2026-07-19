# Contribuire a Oracle

## Requisiti

- **Python 3.12.x** per il runtime applicativo. Verifica con `cat .python-version`.
- **Node 24.x** per dashboard ed Eliza bridge.
- **uv** per installazione e lock Python; non usare `pip install -e` come fonte
  della CI riproducibile.

## Setup iniziale

```bash
# Clona il repo
git clone <repo-url> oracle-trading && cd oracle-trading

# Installa Python 3.12 e sincronizza esattamente uv.lock
uv python install 3.12
uv sync --frozen --all-extras --all-groups

# Verifica l'ambiente
./scripts/check_env.sh
```

## Comandi principali

I target Make usano l'ambiente del progetto; in alternativa usare `uv run`.

| Comando | Descrizione |
|---------|-------------|
| `make test` | Suite di test completa |
| `make test-fast` | Test esclusi gli slow |
| `make test-unit` | Solo unit test |
| `make test-integration` | Solo integration test |
| `make test-cov` | Test con coverage |
| `make lint` | Ruff check |
| `make format` | Ruff format |
| `make typecheck` | Mypy |
| `make precommit` | Pre-commit su tutti i file |

### Verifica ambiente

```bash
./scripts/check_env.sh
```

Verifica Python 3.12 e pacchetti critici (talib, vectorbt, deap, langgraph, polars, lightgbm). Fai fallire subito se l'ambiente è sbagliato.

## Dipendenze opzionali

Alcune funzionalità richiedono pacchetti non sempre installabili:

- **TA-Lib**: libreria C nativa. Su Arch Linux richiede build da AUR (`ta-lib` + `python-ta-lib`). Il progetto ha fallback Polars-native in `analytics/technical/polars_indicators.py`.
- **PyBroker**: percorso deprecato e solo storico/research. Non aggiungere nuove
  integrazioni; i test legacy in `tests/genetics/test_pybroker_integration.py`
  vengono skippati automaticamente se la libreria non è disponibile.
- **ib_insync**: richiede IB Gateway o TWS in esecuzione per i test live.

## Convenzioni

- **Style**: ruff + mypy strict. Ogni ignore deve essere minimo, motivato e
  tracciato; non ampliare gli override per nascondere regressioni.
- **Test**: pytest con marker (`unit`, `integration`, `slow`, `e2e`). I test slow vanno marcati `@pytest.mark.slow`.
- **Commit**: formato convenzionale (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`). Guarda `git log --oneline -10` per esempi.
- **Documentazione**: italiano per documenti di progetto; inglese per codice e
  docstring. Non creare nuovi piani Phase: usare capability gate e work package.
- **ADR**: ogni decisione architetturale significativa va documentata in
  `docs/ADR/` e indicizzata in `docs/ADR/README.md`.

## Workflow

1. Crea un branch: `git checkout -b feat/descrizione`
2. Implementa con test
3. Verifica: `make lint && make typecheck && make test`
4. Commit atomici, un concetto per commit
5. PR con descrizione del cambiamento e risultati dei test
