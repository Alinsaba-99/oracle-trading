> **ARCHIVIO STORICO.** Documento del modello Phase, deprecato da ADR-012
> e sostituito dai capability gate G0-G9. Roadmap canonica:
> [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).
> **Non aggiornare** — solo git archaeology.

# Testing, CI/CD & Qualification Report

**Project:** Oracle — Systematic Trading Intelligence Platform
**Date:** 2026-07-19
**Scope:** Test coverage, CI pipeline, backtest qualification, infrastructure quality

---

## 1. Test Coverage by Package

| Package | Test Files | Test Lines | Prod Lines | Ratio | Assessment |
|---------|-----------|-----------|-----------|-------|-----------|
| **core/**  | 8 (in unit)  | ~1,200  | ~2,539 | 0.47 | Buona copertura domain model, eventi, errori, config, logging |
| **market/** | 5 (in unit) | ~800   | ~1,464 | 0.55 | Data sources, normalizer, converters, feature store testati |
| **analytics/** | 15 (in unit) | ~2,800 | ~9,152 | 0.31 | **Copertura piu bassa** — tanti moduli, pochi test per modulo |
| **execution/** | 12 | ~2,559 | ~1,970 | 1.30 | Ottima copertura — broker, order manager, algos, bridge testati |
| **genetics/** | 22 | ~5,285 | ~6,503 | 0.81 | Buona — engine, genome, popolazione, operatori, fitness testati |
| **agents/** | 20 | ~3,914 | ~3,483 | 1.12 | Molto buona — tutti i componenti principali hanno test |
| **policy/** | 4 | ~649 | ~1,207 | 0.54 | Adeguata — governor + golden test + order risk adapter |
| **api/** | 4 | ~235 | FastAPI | — | **Minima** — solo endpoint base, nessun test auth/error |
| **integration/** | 1 (empty) | 0 | — | — | **ASSENTE** |
| **TOTAL** | **105** | **~20,508** | **~26,318** | **0.78** | |

### Coverage Heatmap

```
core      ████████████████░░░░  0.47  ⚠️  need more domain model tests
market    ██████████████████░░  0.55  ⚠️
analytics ████████████░░░░░░░░  0.31  🔴 CRITICAL — largest codebase, least tested
execution ████████████████████  1.30  ✅
genetics  ████████████████████  0.81  ✅
agents    ████████████████████  1.12  ✅
policy    ██████████████████░░  0.54  ⚠️  adeguato ma piccolo
api       ██████░░░░░░░░░░░░░░  0.06  🔴 CRITICAL — 4 test files, 235 lines
```

---

## 2. Test Infrastructure Quality

### Strengths
- **Fixtures**: `@pytest.fixture` pattern diffuso. `conftest.py` in `tests/execution/` e `tests/api/`
- **Autouse fixtures**: 3 total (`_patch_db_path`, `_mock_asyncio_sleep`, `reset_structlog`) — targeting, non invasive
- **Async support**: `asyncio_mode = "auto"` in `pyproject.toml` — async test functions work without decorators
- **Mocking**: `AsyncMock`/`MagicMock` usati sistematicamente in execution e agents
- **tmp_path**: Usato per test isolati da filesystem (store, registry, experiment)
- **Markers**: 4 definiti (`unit`, `integration`, `slow`, `e2e`); `@pytest.mark.slow` usato in genetics/pybroker
- **Descriptive naming**: `TestSubmitHappy.test_creates_order_with_correct_fields` — nomi parlanti

### Weaknesses
- **Nessun conftest.py a livello radice** — nessun fixture condiviso tra tutti i test
- **Parametrize sottoutilizzato**: solo 4 suite (`test_bridge`, `test_operators_causal`, `test_fundamental`, `test_signals_r1`)
- **Test segregation assente**: marker `integration` ed `e2e` definiti ma MAI usati nei test
- **Nessun test property-based** (Hypothesis), nessun golden/snapshot testing esteso
- **tests/integration/ e vuoto** — zero test cross-component
- **API test minimi**: 235 linee, nessun test di autenticazione fallita, nessun test di error path

### Framework Configuration (pyproject.toml)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
markers = ["unit", "integration", "slow", "e2e"]

[tool.coverage.run]
source = ["oracle"]
branch = true
```

---

## 3. CI Pipeline Analysis

### Current Pipeline (`.github/workflows/ci.yml`)

```
CI Pipeline
├── lint (ubuntu-latest)
│   ├── uv sync --frozen --all-extras --all-groups
│   ├── uv lock --check
│   ├── ruff check .
│   ├── ruff format --check .
│   └── mypy --strict core/ market/ analytics/ execution/ genetics/ ...
│
├── test (ubuntu-latest, py3.12)
│   ├── uv sync --frozen --all-extras --all-groups
│   ├── pytest tests/ -q --cov=core --cov-report=xml
│   └── codecov/codecov-action (fail_ci_if_error: false)
│
├── frontend (apps/dashboard)
│   ├── npm ci
│   ├── npm run build
│   ├── npm run test -- --run
│   └── npm audit --audit-level=high
│
└── eliza-intelligence (integrations/eliza-intelligence)
    ├── npm ci
    ├── npm run typecheck
    ├── npm run test
    ├── npm run build
    └── npm audit --audit-level=high
```

### Strengths
- **uv-based**: Fast dependency resolution, built-in caching, lockfile verification
- **Multi-language**: Python + frontend (Node 24) + Eliza integration
- **Pre-commit hooks**: Ruff, mypy, trailing-whitespace, EOF fixer, YAML/TOML/JSON check, large files, private key detection, merge conflict check, LF line endings, uv lock check
- **Concurrency**: `cancel-in-progress: true` — non spreca run su push multipli

### Gaps (Prioritized)

| Priority | Gap | Impatto |
|----------|-----|---------|
| **P0** | `fail_ci_if_error: false` | Coverage degradation passa inosservato |
| **P0** | `--cov=core` solo, non `--cov=analytics` | 9k linee analytics NON monitorate in CI |
| **P1** | Nessuna segregazione test lenti (`-m "not slow"`) | CI prende tutto il tempo, anche per test lenti di genetics |
| **P1** | Nessun security scanning (bandit, SAST, trufflehog) | Dipendenze e secrets non scansionati |
| **P1** | Nessun benchmark/performance regression test | Degradazione backtest passa inosservata |
| **P2** | Nessun Docker-in-CI test (integration) | Dipendenza da NATS/Redis/QuestDB non testata |
| **P2** | Singola versione Python (3.12) | Regressioni su altre versioni non scoperte |
| **P2** | Nessun matrix OS | Dipende da ubuntu-latest |

---

## 4. Backtest Qualification: Discovery vs Event-Driven Parity

### Current Architecture (ADR-011)

```
Qualification Pipeline (Target)
├── Discovery (VectorizedEngine → vectorbt)
│   ├── Fast, vectorized, screening
│   ├── Tests: test_vectorbt_engine.py (325 lines)
│   └── Test signal strategies: AlwaysLong, AlwaysShort, AlwaysFlat, SineWave
│
├── Qualification (NautilusEngine → nautilus-trader)
│   ├── Event-driven, ContractSpec, shared risk/cost
│   ├── Candidate, NOT certified per ADR-011
│   ├── Uses Equity model + cash account (not futures-grade)
│   ├── Silent exception swallowing in close/extract/account
│   └── Cross-engine parity test: test_cross_engine.py (141 lines)
│
├── PyBroker (DEPRECATED per ADR-011)
│   ├── Still has @pytest.mark.slow integration tests
│   └── Not part of canonical qualification path
│
└── Challenge Simulator
    ├── ChallengeSimulator (analytics/backtest/challenge.py)
    ├── Intraday-honest: challenge_intraday.py (R0.6)
    ├── Tests: test_challenge_simulator.py (87 lines)
    └── Tests: test_challenge_intraday.py (80 lines)
```

### Cross-Engine Parity Test Findings

The `TestCrossEngineConsistency` in `test_cross_engine.py` is the **only test** comparing discovery vs qualification engines. Key observations:

- **Uses 0% commission/slippage** because "the two engines apply costs differently" — vectorbt subtracts from returns, nautilus deducts from cash
- **Tolerances**: Sharpe ±10%, Final Equity ±5%
- **Both engines produce >0 trades**: verified
- **Equity curve lengths verified**: both match input data length
- **Systematic divergence acknowledged** but not quantified in metrics breakdown

### What's NOT Tested

- P0: **No qualification engine certification** — NautilusEngine fails silently in edge cases
- P0: **No point-in-time data lineage tests** — critical for backtest integrity
- P0: **No holdout set validation tests** — no verification that holdout data stays untouched
- P0: **No leakage detection tests** — train/test snooping could go undetected
- P1: **No cost model parity tests** — different cost models cause systematic divergence
- P1: **No multi-asset qualification tests**
- P1: **No test comparing qualification results with execution paper path**
- P2: **No scenario with realistic costs** (slippage, commission, market impact)

### G5 Gate Status: **BLOCKED**

Per `ORACLE_AUTOPILOT_STATUS.md`:
```
| G5 | BLOCKED | Motore qualification non certificato |
```

Il motore candidate (Nautilus) ha fallback riconosciuti e la parity non e certificata.

---

## 5. Experiments Registry

### Structure
```
experiments/
├── experiments.db          160KB SQLite
├── registry/
│   ├── __init__.py
│   └── schema.py           GARunRecord, GenomeSnapshot, ParetoFrontRecord
├── scripts/
│   ├── run_ga.py           7.6KB — GA evolution runner
│   ├── run_ga_production.py 6.0KB — production-grade GA
│   ├── run_ga_demo_seed.py  4.5KB — demo with seed
│   ├── run_ga_pybroker.py   5.2KB — PyBroker GA
│   ├── run_mas.py           4.6KB — Multi-agent system run
│   ├── analyze_mas.py       3.6KB — MAS analysis
│   ├── analyze_results.py   3.3KB — Result analysis
│   ├── run_wave2.py         3.6KB — Wave 2 experiment
│   ├── fetch_intraday.py    1.9KB — Intraday data fetch
│   ├── launcher.py          0.7KB — Launcher
│   └── launch_wave2.sh      0.8KB — Shell wrapper
└── results/
    ├── benchmark_*.json     GA benchmark results
    ├── ga_intraday_final.json
    ├── ga_pair_final.json
    ├── ga_expression_final.json
    ├── wave2_*.json
    └── ga_prod_run.log
```

### Registry Schema
- `GARunRecord`: run_id, timestamp, config hash, generation count, result_summary
- `GenomeSnapshot`: generation number, population snapshot
- `ParetoFrontRecord`: per-generation Pareto front

### Tests
- `test_experiment.py`: 61 lines — base ExperimentContext e Registry (sync)
- `test_experiment_sqlite.py`: 122 lines — SQLite-backed async Register + List + Get + Parent Tracking

---

## 6. Critical Testing Gaps

### 🔴 P0 — Blocking for Production Readiness

| Gap | Location | Impact | Evidence |
|-----|----------|--------|----------|
| **Nessun motore qualification certificato** | `analytics/backtest/engines/nautilus.py` | G5 gate BLOCKED | Silent fallback, Equity model, parity test usa 0 costi |
| **Zero integration tests** | `tests/integration/` (empty) | Nessuna verifica cross-component | 1 file __init__.py vuoto |
| **Nessun test leakage/holdout** | `analytics/backtest/` | Risultati backtest non affidabili | Feature richieste in G5 mai testate |
| **Nessun test point-in-time** | `market/data/` | Snooping storico non rilevabile | ADR-011 richiede, non implementato |

### 🟠 P1 — High Impact

| Gap | Location | Impact | Evidence |
|-----|----------|--------|----------|
| **Copertura analytics insufficiente** | `analytics/` (9,152 lines) | Moduli critici non testati | Ratio 0.31 — il piu basso |
| **Risk manager opzionale e non testato per bypass** | `execution/order_manager/manager.py` | Bypass risk possibile | `risk_manager=None` in constructor |
| **API tests insufficienti** | `tests/api/` (235 lines) | Regressioni API non rilevate | No auth test, no error path |
| **Nessun security scanning in CI** | `.github/workflows/ci.yml` | Secrets e dipendenze non scansionati | No bandit, no trufflehog, no dependabot config |
| **Coverage non monitorato per analytics** | CI `--cov=core` solo | Degrado copertura passa inosservato | `fail_ci_if_error: false` |

### 🟡 P2 — Should Address

| Gap | Location | Impact | Evidence |
|-----|----------|--------|----------|
| **Nessun conftest.py root** | `tests/` | Fixture ripetuti tra moduli | Solo execution/ e api/ hanno conftest |
| **Parametrize sottoutilizzato** | Tutti i test | Casi edge non coperti sistematicamente | Solo 4 suite lo usano |
| **Markers `integration`/`e2e` mai usati** | `pyproject.toml` → test files | Segregazione non funzionante | Definita ma non applicata |
| **Nessun test di benchmark** | `tests/` | Degrado performance non rilevabile | No timing/regression baselines |
| **showcase.py non in CI** | `showcase.py` | Demo funzionante non verificata in CI | Richiede yfinance (internet) |
| **Nessun test Docker/infrastruttura** | `infra/docker/` | Setup infrastruttura non testato | docker-compose definito, mai testato in CI |

---

## 7. Makefile Quality Assessment

```
Available Targets:
  install          uv sync --frozen --all-extras --all-groups
  dev              uv sync --frozen --all-groups
  lint             ruff check .
  lint-fix         ruff check --fix .
  format           ruff format .
  typecheck        mypy --strict core/ market/ analytics/ ...
  test             pytest tests/ -v
  test-venv        pytest via .venv (fallback)
  test-cov         pytest con --cov=core --cov=market --cov=analytics
  test-fast        pytest -m "not slow"
  test-unit        pytest tests/unit/
  test-integration pytest tests/integration/
  clean            rm -rf build dist ...
  fresh            clean + install
  precommit        pre-commit run --all-files
  docker-up        docker compose up
  docker-down      docker compose down
```

### Missing Targets
| Target | Why Needed |
|--------|-----------|
| `test-genetics` | Run speedy genetics tests without `-m slow` |
| `test-execution` | Isolate broker tests |
| `test-agents` | Run agent tests independently |
| `test-api` | Fast API test feedback loop |
| `test-core` | Core domain model tests |
| `test-policy` | Prop firm policy tests |
| `benchmark` | Performance regression detection |
| `security-scan` | Run security tooling (bandit, etc.) |

---

## 8. Recommendations

### P0 — Immediate (Pre-Production Gate)

1. **Certificare qualification engine**: Rimuovere fallback silenziosi da NautilusEngine, aggiungere cost model, futures-grade account type, e test di parity con costi realistici
2. **Aggiungere integration tests**: Popolare `tests/integration/` con test che connettono backtest → challenge simulator → prop-firm governor
3. **Aggiungere leakage/holdout tests**: Verificare che train/test split sia point-in-time corretto, holdout non contaminato
4. **Fix CI coverage monitoring**: Cambiare `--cov=core` in `--cov=analytics --cov=execution --cov=genetics --cov=agents --cov=policy` e impostare `fail_ci_if_error: true` con soglia minima

### P1 — High Priority (Next Sprint)

5. **Aumentare copertura analytics**: Test per `providers.py`, `orchestrator.py`, `benchmarks.py`, `splitters.py`, `portfolio.py`, `data.py`
6. **Test risk manager non-bypassability**: Verificare che `risk_manager=None` non sia possibile in produzione
7. **API test expansion**: Auth failure, error paths, validation errors, rate limiting
8. **CI security scanning**: Aggiungere bandit (Python SAST), trufflehog (secrets), dependabot config
9. **Segregare test lenti in CI**: Aggiungere `pytest tests/ -q -m "not slow"` come job separato prima dei test completi

### P2 — Important (Technical Debt)

10. **Aggiungere root conftest.py**: Fixture condivise per tutta la test suite
11. **Estendere uso di parametrize**: Coprire edge case sistematicamente in tutti i moduli
12. **Usare marker `integration`/`e2e`**: Applicare ai test esistenti che testano cross-component
13. **Aggiungere test di benchmark**: Baseline performance per backtest engine, WFA, GA
14. **Makefile targets per package**: `test-genetics`, `test-execution`, `test-agents`, `test-api`, `test-policy`
15. **Python version matrix in CI**: Testare almeno Python 3.12 + 3.13

---

## 9. Summary Dashboard

```
┌────────────────────────────────────────────────────────────────┐
│                 ORACLE — TESTING HEALTH DASHBOARD               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  TEST RATIO:            20,508 / 26,318  (0.78)  🟢            │
│  TEST FILES:            105                                    │
│  INTEGRATION TESTS:     0                     🔴              │
│  CI STEPS:              4 (lint,test,frontend,eliza)           │
│  SECURITY SCANS:        0 (npm audit escluso)    🔴            │
│  G5 GATE:               BLOCKED                 🔴              │
│  SHOWCASE IN CI:        NO                      🟡              │
│  COVERAGE MONITORED:    core only               🔴              │
│  CONFTEST FILES:        2 (execution, api)      🟡              │
│  PARAMETRIZE SUITES:    4                       🟡              │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  OVERALL:              🟡  NEEDS ATTENTION                      │
│  Production Readiness:  RESEARCH-GRADE                          │
└────────────────────────────────────────────────────────────────┘
```
