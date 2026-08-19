> **ARCHIVIO STORICO.** Documento del modello Phase, deprecato da ADR-012
> e sostituito dai capability gate G0-G9. Roadmap canonica:
> [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).
> **Non aggiornare** — solo git archaeology.

# Phase 3 — Genetic Engine Implementation Plan

**Status:** DRAFT · **Mode:** RALPLAN-DR DELIBERATE
**Date:** 2026-07-09
**Target:** `master` · **Durability:** Artifact survives workspace reset

---

## 1. Strategic Summary

Phase 3 builds a genetic algorithm engine that evolves trading strategies using DEAP. The engine encodes strategy parameters as a typed genome, evolves populations across multiple islands, optimizes for 4 objectives simultaneously (NSGA-II), and logs every run to the Experiment Registry with checkpoint/restart support.

### Principles (5)

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | **Correctness first, performance second** | GA evaluation involves real backtests. A wrong fitness landscape converges on garbage silently. Verification gates before optimization. |
| P2 | **Every GA run must be reproducible** | Random seeds, genome snapshots, population state, and full hyperparameters logged to Experiment Registry. No stochastic black box. |
| P3 | **Isolation between GA engine and strategy execution** | The GA evolves parameter vectors; the `GenomeToSignal` adapter decodes them into `BacktestSignal` objects. These are separate concerns with a stable serialization contract. |
| P4 | **Favor proven algorithms over novelty** | NSGA-II (2002), DEAP (2009), tournament selection, SBX crossover — use what works. Novelty belongs in alpha factors, not optimization mechanics. |
| P5 | **Typed parameters, not flat vectors** | Every genome dimension is a typed `GenomeParameter` (Continuous, Int, or Categorical) with its own bounds, scaling, and mutation semantics. No silent type confusion. |

### Decision Drivers (Top 3)

1. **Drift risk**: GA + multi-objective + walk-forward + island model = many moving parts. Each dimension adds failure modes. Default to simpler subassemblies first.
2. **Reproducibility debt**: A stochastic optimizer without full state capture is a scientific liability. The genetic engine is the most reproducibility-critical component in the system. Checkpoint every generation.
3. **Computation cost**: Each fitness evaluation is a full backtest. With population=100, generations=50, islands=4, walk-forward=5 folds → ~100,000 backtests per run. Fitness caching, factor pre-computation, and parallelism are design requirements, not optimizations.

### Options Evaluated

#### D1: Genome Representation

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Typed parameter vector** (→ adopt) | ✅ **Primary** | `GenomeParameter` union type (Continuous, Int, Categorical) with per-dimension bounds, scaling, mutation semantics. Serializes trivially to JSON. |
| Expression-tree GP | ⏳ Phase 4 | WorldQuant-style alpha expressions (ts_rank, correlation, etc.) enable factor discovery. Requires operator library, tree crossover, bloat control. Too much scope for Phase 3. |
| Hybrid (vector kernel + GP leaf) | ❌ Phase 5+ | Premature. Start with one representation. |

**Why chosen:** Typed parameter vector prevents silent type errors (e.g. treating an integer `lookback` as continuous) and gives DEAP bounded operators everything they need for correct crossover/mutation.

#### D2: GA Framework

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **DEAP** (→ adopt) | ✅ **Primary** | Mature (15+ years), documented, NSGA-II built-in, `eaMuPlusLambda`/`eaSimple`, toolbox pattern. 2M+ downloads. |
| Custom from scratch | ❌ Rejected | Lot of work to match DEAP's NSGA-II, selTournamentDCD, cxSimulatedBinaryBounded. No benefit. |
| PyGAD | ❌ Rejected | Wrapper-oriented, less flexible for multi-objective + island model combo. Weaker DEAP ecosystem. |

**Why chosen:** DEAP has proven NSGA-II implementation and supports the island model via `deap.algorithms` composition.

#### D3: Multi-Objective Optimization

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **NSGA-II** (→ adopt) | ✅ **Primary** | DEAP `algorithms.eaMuPlusLambda` + `selTournamentDCD` + `selNSGA2`. Proven since 2002. Handles 4 objectives naturally. |
| SPEA2 | ❌ Rejected | Not built into DEAP; would need custom implementation. Marginal benefit over NSGA-II. |
| Weighted sum | ❌ Rejected | Collapses 4 objectives → 1 scalar. Loses Pareto frontier information. User can't see Sharpe/Sortino tradeoffs. |

**Why chosen:** NSGA-II is DEAP-native, handles our 4 objectives, and produces a Pareto frontier instead of a single point.

#### D4: Island Model

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Custom asyncio** (→ adopt) | ✅ **Primary** | DEAP's `deap.algorithms` is synchronous. Islands need parallel or concurrent execution. asyncio with `concurrent.futures.ProcessPoolExecutor` for per-island fitness eval. |
| DEAP built-in (`deap.tools.MultiProcessing`) | ❌ Rejected | Multiprocessing map only — no migration logic, no island isolation. We'd build the same machinery on top. |
| Ray | ❌ Not yet | Heavy dependency for Phase 3. Worth evaluating in Phase 4 if island count grows >16. |

**Why chosen:** asyncio + ProcessPoolExecutor gives parallel per-island evaluation with clean migration scheduling. Minimizes new dependencies.

#### D5: Alpha Factor Library

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Curated 50 high-quality factors** (→ adopt) | ✅ **Primary** | Domain experts (e.g. Kakushadze 2015 "101 Formulaic Alphas", WorldQuant top performers). Covers momentum, value, quality, volatility, correlation, seasonality. |
| 484 factors like FinClaw | ❌ Rejected | Too many — overfits on historical data, high compute cost per fitness eval. More factors ≠ better. |
| Expression-tree GP for factor discovery | ⏳ Phase 4 | GP-generated alpha factors require tree representation and operator library. |

**Why chosen:** Curated library gives sufficient search space without the brittleness of huge factor sets. 50 factors with 50 genome parameters = 2500 combinations per individual, enough to explore.

#### D6: Fitness Evaluation

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Walk-Forward inside fitness** (→ adopt) | ✅ **Primary** | 3-5 folds. Each fold = train on T−N..T−1, test on T..T+H. Average across folds. Avoids look-ahead bias baked into the fitness. |
| Single backtest | ❌ Rejected | Single train/test split is not robust against regime changes. Walk-forward is standard in quantitative finance. |
| Cross-validation (random folds) | ❌ Rejected | Time-series CV (expanding window or purge/embargo/purging) is appropriate. Random CV leaks future into past. |

**Why chosen:** Walk-forward with purge/embargo (no leakage between train/test folds) is the gold standard for time-series evaluation.

#### D7: Population Initialization

| Option | Verdict | Rationale |
|--------|---------|-----------|
| **Seeded from known strategies** (→ adopt) | ✅ **Primary** | Bootstrap population with ~10 known strategies encoded as genomes (MACD crossover, RSI<30, Bill Williams, etc.). Fill rest with random. Gives GA a head start. |
| Pure random | ❌ Rejected | Converges slower. In high-dim search spaces, random initialization wastes generations finding viable regions. |
| Hybrid (seeded + random) | ⚠️ How we implement it | 20% seeded, 80% random. Seeded genomes are also mutated randomly to explore neighborhood. |

**Why chosen:** Known strategies provide a fitness baseline and guide the GA toward promising regions. Random diversity ensures exploration.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Genetic Engine (Phase 3)                      │
│                                                                      │
│  ┌────────────────┐   ┌──────────────────┐   ┌───────────────────┐  │
│  │ Genetics/Genome │   │ Genetics/Opers   │   │ Genetics/Pop      │  │
│  │ - TypedParams   │   │ - Tournament     │   │ - Island[]        │  │
│  │ - Encode/Decode │   │ - SBX Crossover  │   │ - Migration       │  │
│  │ - GenomeToSignal│   │ - Polynomial Mut │   │ - Merge Pareto    │  │
│  │ - Bounds        │   │ - NSGA-II Select │   │ - Checkpoint      │  │
│  └───────┬─────────┘   └────────┬─────────┘   └─────────┬──────────┘  │
│          │                      │                       │            │
│          ▼                      ▼                       ▼            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Genetics/Fitness                           │   │
│  │  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐  │   │
│  │  │ GenomeToSig │  │ Walk-Forward     │  │ MetricsCalc:    │  │   │
│  │  │ → Backtest  │  │ Backtest (5 fold)│  │ .sharpe_ratio,  │  │   │
│  │  │ Signal      │  │ purge+embargo    │  │ .sortino_ratio  │  │   │
│  │  └─────────────┘  └──────────────────┘  └─────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ FactorPrecomputer: pre-compute factor exposures for    │  │   │
│  │  │ the data window, cache per (symbol, date_range)       │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Experiment Registry (GA extensions)             │  │
│  │  ┌─────────────┐ ┌──────────────────┐ ┌──────────────────┐  │  │
│  │  │ ga_runs     │ │ genome_snapshots │ │ pareto_fronts    │  │  │
│  │  │ - run_id    │ │ - run_id         │ │ - run_id         │  │  │
│  │  │ - config    │ │ - generation     │ │ - generation     │  │  │
│  │  │ - seed      │ │ - population     │ │ - individuals    │  │  │
│  │  │ - status    │ │ - fitnesses      │ │ - fitnesses      │  │  │
│  │  └─────────────┘ └──────────────────┘ └──────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### File Layout

```
oracle/
├── genetics/
│   ├── __init__.py              # Exports: GeneticEngine, GAConfig, Genome, GenomeToSignal
│   ├── config.py                # GAConfig, GenomeConfig, IslandConfig, WalkForwardConfig
│   ├── genome/
│   │   ├── __init__.py          # Genome dataclass, GenomeParameter types, encode/decode
│   │   ├── parameters.py        # TypedParameter: Continuous, Int, Categorical — bounds, scale, mutation specs
│   │   ├── codec.py             # normalize, denormalize, validate, clamp per parameter type
│   │   └── signal.py            # GenomeToSignal(genome) → BacktestSignal adapter
│   ├── operators/
│   │   ├── __init__.py          # DEAP toolbox builder, create_toolbox(GenomeConfig) → Toolbox
│   │   ├── selection.py         # selTournament, selTournamentDCD, selNSGA2 wrappers
│   │   ├── crossover.py         # cxSimulatedBinaryBounded with post-validation
│   │   └── mutation.py          # mutPolynomialBounded + per-typed-parameter mutation
│   ├── population/
│   │   ├── __init__.py          # initialize_population, HallOfFame wrapper
│   │   ├── seeding.py           # seeded_individuals — ~10 known strategies as genomes
│   │   ├── stats.py             # PopulationStats: mean/max/min per objective, diversity, Pareto size
│   │   └── migration.py         # MigrationPolicy, ring topology, best-M replacement
│   ├── alpha/
│   │   ├── __init__.py          # CuratedAlphaLibrary, factor_name → callable
│   │   ├── library.py           # 50 curated factors by category
│   │   ├── factors.py           # Individual factor implementations (vectorized, Polars/NumPy)
│   │   └── precompute.py        # FactorPrecomputer: batch compute + cache per (symbol, date_range)
│   ├── fitness/
│   │   ├── __init__.py          # FitnessEvaluator, caching layer
│   │   ├── evaluator.py         # WalkForward backtest → 4-objective fitness tuple
│   │   ├── cache.py             # LRU cache keyed by (genome_hash, fold_config_hash, data_hash)
│   │   └── interfaces.py        # Expected external interfaces: BacktestEngine, MetricsCalculator, WalkForwardEngine
│   ├── islands.py               # Island, IslandManager, parallel asyncio execution, checkpoint
│   ├── engine.py                # GeneticEngine.run() → GAResult with checkpoint/restart
│   └── serialize.py             # Genome ↔ dict, population snapshot, GAConfig ↔ dict, Experiment Registry helpers
├── experiments/
│   ├── registry/
│   │   ├── __init__.py          # Experiment Registry client
│   │   └── schema.py            # ga_runs, genome_snapshots, pareto_fronts table definitions
│   └── scripts/
│       ├── run_ga.py            # CLI: --config, --data, --pop-size, --generations, --seed, --resume
│       └── analyze_results.py   # Load experiment → Pareto frontier, diversity, convergence plots
├── tests/
│   ├── genetics/
│   │   ├── test_genome.py
│   │   ├── test_parameters.py
│   │   ├── test_codec.py
│   │   ├── test_signal.py
│   │   ├── test_operators.py
│   │   ├── test_population.py
│   │   ├── test_migration.py
│   │   ├── test_fitness.py
│   │   ├── test_cache.py
│   │   ├── test_islands.py
│   │   ├── test_serialize.py
│   │   ├── test_alpha_library.py
│   │   ├── test_precompute.py
│   │   ├── test_engine.py
│   │   └── conftest.py
│   └── integration/
│       └── test_ga_integration.py
└── pyproject.toml                # Add DEAP to deps
```

---

## 3. Detailed Task Flow

### Task 0: Foundation — Dependency + Project Scaffold

**Acceptance:**
- DEAP added to `pyproject.toml` (or `requirements.txt`): `deap>=1.4.1`
- Verify Python 3.14 compatibility: `pip install deap` in CI succeeds on 3.14 (use `--only-binary deap` or document source-build fallback)
- `genetics/` package scaffold created with `__init__.py` in each subdirectory
- `polars` confirmed as dependency for MetricsCalculator interface (returns typed Series)

**Files to create:** `pyproject.toml` (if missing), `genetics/__init__.py`, all `genetics/*/__init__.py`

**Risks:**
- DEAP may not ship 3.14 wheels at start of Phase 3. Mitigation: pin `deap>=1.4.1` with `--no-binary deap` fallback; DEAP is pure-Python + optional C extensions.
- Missing `pyproject.toml` blocks CI. Create one if absent.

---

### Task 1: Typed Parameter Taxonomy (`genetics/genome/parameters.py`, `codec.py`)

**Acceptance:**
- `GenomeParameter` union type with three variants:
  - `ContinuousParameter(name, low, high, init_range=(0.0, 1.0))` — float params (e.g. stop-loss, position size)
  - `IntParameter(name, low, high, init_range=(0, 1))` — integer params (e.g. lookback period, smoothing window)
  - `CategoricalParameter(name, categories, weights=None)` — discrete choices (e.g. entry logic selector, volatility model)
- Each parameter specifies: `name`, bounds/n categories, scaling (linear, log for Int/Continuous), mutation step size (or None for automatic)
- `ParameterConfig` class: holds list of `GenomeParameter` definitions → determines genome length
- `normalize(raw_value, param) → float`: map raw parameter → [0,1] normalized
- `denormalize(normalized, param) → raw_value`: reverse
- `validate(raw_value, param) → bool`: respect bounds and type
- `clamp(raw_value, param) → raw_value`: clip to valid range
- `random_value(param, rng) → raw_value`: type-aware random initialization
- All normalization respects log scaling for parameters that need it (e.g. lookback periods)

**Files to create:** `genetics/genome/__init__.py`, `genetics/genome/parameters.py`, `genetics/genome/codec.py`, `tests/genetics/test_parameters.py`, `tests/genetics/test_codec.py`

**Risks:**
- IntParameter normalization: integer range [1, 100] → normalized [0,1] → denormalized 37.6 → round to 38. Must handle rounding consistently.
- CategoricalParameter: mapping categorical → fixed vector position (one-hot or index). Use index encoding for GA simplicity.

---

### Task 2: Genome Core + Signal Adapter (`genetics/genome/`)

**Acceptance:**
- `Genome` dataclass: `parameters: NDArray[np.float64]` (normalized [0,1]), `param_defs: list[GenomeParameter]`, `names: list[str]`
- `GenomeConfig(n_params, param_defs)` — typed config that also carries parameter definitions
- `encode(raw_params_dict, param_defs) → Genome`: maps named raw params → normalized float vector
- `decode(genome) → dict[str, raw_value]`: reverse; applies denormalization per parameter type
- `mutate_gaussian(genome, sigma, prob) → Genome`: in-place gaussian mutation within normalized bounds
- `validate(genome) → bool`: all params ∈ [0,1], correct length
- **`GenomeToSignal(genome, param_defs) → BacktestSignal`**: decodes genome → raw params → builds `BacktestSignal` object with `.entry_logic`, `.exit_logic`, `.position_size`, `.stop_loss`, etc.
- `BacktestSignal` is a lightweight dataclass consumed by `BacktestEngine.run()`
- Serialize ↔ dict (via `genome_to_dict` / `dict_to_genome`)
- Bounds handle: normalized [0,1] space + denormalization to actual parameter range per type

**Files to create:** `genetics/genome/signal.py`, `tests/genetics/test_genome.py`, `tests/genetics/test_signal.py`

**Risks:**
- Silent bounds violation → invalid strategy. MUST validate on decode.
- Floating point drift across generations → cumulative error. Fix: periodic re-normalization.
- `BacktestSignal` must match the interface expected by BacktestEngine (see Task 4 interfaces).

---

### Task 3: Alpha Factor Library (`genetics/alpha/`)

**Acceptance:**
- `CuratedAlphaLibrary` class with 50 named factors
- Each factor is `Callable[[pd.Series], float]` or `Callable[[pl.DataFrame], float]` (single asset or cross-sectional)
- Factors organized by category: momentum (10), mean-reversion (8), volatility (6), correlation (6), volume (5), seasonality (5), fundamental proxies (5), microstructure (5)
- `compute(series, factor_names) → dict[str, float]` — batch compute with caching
- All factors vectorized (Polars or NumPy) — no loops over individual rows
- Each factor has docstring with formula and citation
- **`FactorPrecomputer`**: pre-computes ALL 50 factors for a given data window (symbol, date_range) in one pass; caches result keyed by `(symbol_hash, start_date, end_date)`. Drastically reduces repeated computation across genome evaluations within the same generation.

**Factors to include (representative):**
- Momentum: `roc_1m`, `roc_3m`, `roc_6m`, `roc_12m`, `mom_1m_exc_last`, `mom_reversal`, `weighted_mom`, `exponential_mom`, `momentum_trend`, `momentum_stability`
- Mean-reversion: `rsi_14`, `bb_position`, `distance_from_sma_20`, `distance_from_sma_50`, `zscore_20`, `mean_reversion_speed`, `serial_correlation`, `idiosyncratic_reversion`
- Volatility: `atr_14`, `bb_width`, `historical_vol_20`, `historical_vol_60`, `parkinson_vol`, `yang_zhang_vol`
- Correlation: `corr_to_spy`, `corr_to_sector`, `corr_stability`, `beta_60`, `beta_120`, `idiosyncratic_vol`
- Volume: `volume_zscore_20`, `volume_trend`, `dollar_volume`, `turnover`, `volume_vs_avg`
- Seasonality: `month_effect`, `day_of_week`, `quarter_effect`, `turning_month`, `january_effect`, `halloween_effect`
- Fundamental proxies: `div_yield`, `earnings_yield`, `book_to_price`, `cash_flow_yield`, `payout_ratio`
- Microstructure: `bid_ask_spread_est`, `amihud_illiquidity`, `roll_impact`, `lot_size_adj`, `price_reversal_1d`

**Files to create:** `genetics/alpha/__init__.py`, `genetics/alpha/library.py`, `genetics/alpha/factors.py`, `genetics/alpha/precompute.py`, `tests/genetics/test_alpha_library.py`, `tests/genetics/test_precompute.py`

**Risks:**
- Factor implementation errors → silent degradation of GA fitness landscape. MUST unit-test each factor against known reference values.
- NaN/inf propagation from factors (e.g., division by zero vol). MUST handle with fill/clip.
- Pre-computation cache invalidation: if data changes between GA runs, old cache entries must be ignored. Key includes data fingerprint.

---

### Task 4: External Interface Contracts + Stubs (`genetics/fitness/interfaces.py`)

**Acceptance:**
- Define the **exact signatures** the GA fitness evaluator expects from external Phase 0-2 components:

```python
class BacktestResult:
    """Result of a single backtest run."""

    returns: pl.Series  # Daily strategy returns
    trades: list[dict]  # Individual trade log
    metrics: dict  # Raw computed metrics


class BacktestEngine:
    @staticmethod
    def run(data: pl.DataFrame, signal: BacktestSignal, config: BacktestConfig) -> BacktestResult:
        """Run a backtest given market data and a signal definition."""
        ...


class MetricsCalculator:
    @staticmethod
    def sharpe_ratio(returns: pl.Series) -> float:
        """Annualized Sharpe ratio from daily returns series."""

    @staticmethod
    def sortino_ratio(returns: pl.Series) -> float:
        """Annualized Sortino ratio (downside deviation only)."""

    @staticmethod
    def calmar_ratio(returns: pl.Series) -> float:
        """Annualized return / max drawdown."""

    @staticmethod
    def max_drawdown(returns: pl.Series) -> float:
        """Maximum peak-to-trough drawdown as positive percentage."""


class WalkForwardEngine:
    @staticmethod
    def run(
        data: pl.DataFrame,
        signal: BacktestSignal,
        config: BacktestConfig,
        n_splits: int = 5,
        purge_window: int = 5,
    ) -> list[BacktestResult]:
        """Run walk-forward backtest with purge/embargo. Returns one BacktestResult per fold (out-of-sample)."""
        ...
```

- All methods are static — no instance state, safe for multiprocessing
- `BacktestConfig` defined with required fields
- If Phase 0-2 components don't exist yet, provide thin stubs that return synthetic data for testing

**Files to create:** `genetics/fitness/interfaces.py`, update `genetics/fitness/__init__.py`

**Risks:**
- If Phase 0-2 components use different signatures, integration fails at Task 4 runtime. Stubs must be real enough for GA integration tests.

---

### Task 5: GA Operators (`genetics/operators/`)

**Acceptance:**
- DEAP toolbox configured with:
  - `cxSimulatedBinaryBounded` (SBX crossover, eta=15)
  - `mutPolynomialBounded` (polynomial mutation, eta=20, indpb=0.15)
  - `selTournament` (tournament size=3) for single-objective
  - `selTournamentDCD` for NSGA-II selection
  - `selNSGA2` for environmental selection
- `create_toolbox(genome_def: GenomeConfig) → Toolbox` — factory from config
- Per-type mutation support: `ContinuousParameter` uses gaussian, `IntParameter` uses integer-respecting polynomial, `CategoricalParameter` uses random swap
- Wrapper functions for mutation/crossover that operate on `Genome` objects internally but register DEAP primitives externally
- Fitness weights: (+1.0, +1.0, +1.0, -1.0) for (Sharpe, Sortino, Calmar, MaxDD)
- Hall of Fame: archive top-10 unique individuals
- Post-validation hook: every offspring validated via `validate(genome)`; invalid ones are re-generated

**Files to create:** `genetics/operators/__init__.py`, `genetics/operators/selection.py`, `genetics/operators/crossover.py`, `genetics/operators/mutation.py`, `tests/genetics/test_operators.py`

**Risks:**
- DEAP fitness weights direction: maximizing Sharpe/Sortino/Calmar (positive), minimizing MaxDD (negative). Wrong sign → GA optimizes for drawdown.
- Crossover producing out-of-bounds offspring even with bounded operators. MUST post-validate.

---

### Task 6: Fitness Evaluator (`genetics/fitness/evaluator.py`, `cache.py`)

**Acceptance:**
- `FitnessEvaluator(backtest_engine, metrics_calculator, alpha_library, walk_forward_config, factor_precomputer)`
- `evaluate(genome) → tuple[float, float, float, float]` — returns (Sharpe, Sortino, Calmar, MaxDD)
- Walk-forward schedule: configurable folds (default 5), purge window (default 5), embargo (default 10)
- Each fold: evaluate as:
  ```
  signal = GenomeToSignal(genome)  # adapter
  result = BacktestEngine.run(data, signal, config)
  sharpe = MetricsCalculator.sharpe_ratio(result.returns)
  sortino = MetricsCalculator.sortino_ratio(result.returns)
  calmar = MetricsCalculator.calmar_ratio(result.returns)
  maxdd = MetricsCalculator.max_drawdown(result.returns)
  ```
- Fold score = mean of out-of-sample periods across folds
- **Fitness caching:** LRU cache keyed by `(genome_parameters_hash, fold_config_hash, data_version_hash)`. Cache size ~10k entries.
- Factor pre-computation: `FactorPrecomputer.prefactor(data_window)` called once per generation, then each fitness evaluation reads pre-computed factors, not raw prices
- Parallel evaluation across folds (ProcessPoolExecutor) for single-genome speed
- Edge cases: empty returns → fitness = (-inf, -inf, -inf, 0.0) (avoid division by zero)
- Failed backtest → fitness = exception caught, individual marked invalid (fitness = (-1e6, -1e6, -1e6, 1e6))

**Files to create:** `genetics/fitness/__init__.py`, `genetics/fitness/evaluator.py`, `genetics/fitness/cache.py`, `tests/genetics/test_fitness.py`, `tests/genetics/test_cache.py`

**Risks:**
- **Hot path:** Every genome evaluation runs O(folds) backtests. With pop=100, gens=50, folds=5 → 25,000 backtests per run. MUST have caching + parallelism + factor pre-computation.
- **Cache invalidation:** If the underlying price data changes, all cached fitness values are stale. Solution: hash the data version into the cache key.
- **Walk-forward leakage:** Embargo too short → future information leaks into train set. Default embargo = 10 trading days (2 weeks).

---

### Task 7: Population Management + Migration (`genetics/population/`)

**Acceptance:**
- `seeded_individuals(param_defs, rng) → list[Genome]`: encode ~10 known strategy templates using typed parameter definitions
- `random_individual(n_bounds, rng, param_defs) → Genome`: uniform random in [0,1] normalized
- `initialize_population(pop_size, param_defs, seed_ratio=0.2, rng_seed=42) → list[Genome]`: 20% seeded, 80% random
- `PopulationStats` computed each generation: mean/max/min fitness per objective, diversity (mean pairwise distance in genome space), Pareto front size
- `HallOfFame` wrapper: top-K unique individuals by weighted sum (fallback if Pareto front empty)
- `MigrationPolicy`:
  - Ring topology: island i sends to (i+1) mod N
  - Every K generations (default 5), exchange M best individuals (default 3)
  - Incoming individuals replace worst M in receiving island
  - Migration event logged with individuals, timestamps

**Strategy templates to seed:**
1. Trend-following (SMA crossover 20/50)
2. Mean-reversion (RSI<30>70)
3. Momentum (12m-1m)
4. Volatility breakout (Bollinger 2σ)
5. Pairs trading hedge ratio
6. Carry trade basis
7. Seasonal (month-of-year)
8. Volume-weighted momentum
9. Low-volatility
10. Quality (DivYield + ROE)

**Files to create:** `genetics/population/__init__.py`, `genetics/population/seeding.py`, `genetics/population/stats.py`, `genetics/population/migration.py`, `tests/genetics/test_population.py`, `tests/genetics/test_migration.py`

**Risks:**
- Seeded strategies dominate → collapse diversity. Mitigation: mutate seeded individuals before insertion; limit seed ratio.
- RNG seed not propagated → non-reproducible experiments. Mitigation: single RNG passed through all random ops.

---

### Task 8: Island Model + Checkpoint/Restart (`genetics/islands.py`, `genetics/engine.py`)

**Acceptance:**
- `Island` class: owns sub-population, its own DEAP toolbox, generation counter, checkpoint path
- `IslandManager` class: manages N islands (default 4)
- `run(generations, callback=None)`: parallel evaluation via asyncio + `ProcessPoolExecutor`
- Each island uses different RNG seeds (derived from master seed + island_id)
- Final merge: combine Pareto fronts from all islands → global Pareto set
- Logging per island: generation, best fitnesses, diversity, migration events
- **Checkpoint:** every generation, `IslandManager` saves full state:
  - All island populations + fitnesses
  - Generation counter
  - Current Pareto front
  - Migration history
  - Saved to Experiment Registry (`genome_snapshots` table) AND local JSON checkpoint file
- **Restart:** `GeneticEngine.restore(checkpoint_path) → GeneticEngine` — loads full state, resumes from last completed generation
- `GeneticEngine.run()` — checks for existing checkpoint at `--resume` path; if valid and generation matches, skips completed generations
- `GAResult`: populations log, Pareto front, hall of fame, timing, checkpoint paths

**Execution flow:**
```python
async def run():
    # Load or init state
    if resume_from and Path(resume_from).exists():
        engine = GeneticEngine.restore(resume_from)
    else:
        engine = GeneticEngine(config)

    # Spawn ProcessPoolExecutor (max_workers = n_islands or cpu_count)
    for gen in range(engine.current_gen, total_generations):
        tasks = [island.evaluate_next_gen(executor) for island in islands]
        results = await asyncio.gather(*tasks)
        if gen % migration_interval == 0 and gen > 0:
            migrate_between_islands(islands, topology)
        # Checkpoint every generation
        engine.save_checkpoint(gen)
        log_generation(gen, results)

    engine.finalize()  # Save final result
    return engine.result
```

**Files to create:** `genetics/islands.py`, `genetics/engine.py`, `tests/genetics/test_islands.py`, `tests/genetics/test_engine.py`

**Risks:**
- **Deadlock risk:** ProcessPoolExecutor inside asyncio loop → deadlock if executor shares parent process. Mitigation: use `ProcessPoolExecutor` (not `ThreadPool`), submit only serializable work.
- **Migration sync:** Islands that finish faster wait for slower ones. Mitigation: async gather has inherent sync point; accept this for correctness.
- **Memory growth:** Each island holds full population → 4 islands × 100 individuals × 50 params = 20K arrays. Negligible.
- **Checkpoint I/O:** Writing full population every generation can be slow. Mitigation: async writes; optional checkpoint interval (every 5 generations default).

---

### Task 9: Experiment Registry Schema (`experiments/registry/schema.py`)

**Acceptance:**
- `ga_runs` table:
  - `run_id`: UUID (primary key)
  - `config`: JSON (full GAConfig)
  - `seed`: int
  - `started_at`: timestamp
  - `finished_at`: timestamp (nullable)
  - `status`: enum('running', 'completed', 'failed', 'interrupted')
  - `checkpoint_path`: text (last saved checkpoint file location)
  - `result_summary`: JSON (final stats, Pareto size, wall time)
- `genome_snapshots` table:
  - `snapshot_id`: UUID
  - `run_id`: UUID (FK → ga_runs)
  - `generation`: int
  - `population`: JSON (all individuals, normalized parameters)
  - `fitnesses`: JSON (4-objective fitness vector per individual)
  - `pareto_front_indices`: list[int] (indices into population)
  - `diversity_metric`: float
  - `created_at`: timestamp
- `pareto_fronts` table:
  - `front_id`: UUID
  - `run_id`: UUID (FK → ga_runs)
  - `generation`: int
  - `is_final`: bool
  - `individuals`: JSON (decoded parameters, not normalized — human readable)
  - `fitnesses`: JSON (4-objective fitness values)
  - `created_at`: timestamp
- `serialize.py` helpers: `ga_run_to_dict()`, `snapshot_to_dict()`, `pareto_to_dict()`
- Registry compatible with `genetics/serialize.py` output format

**Files to create:** `experiments/registry/__init__.py`, `experiments/registry/schema.py`

**Risks:**
- Schema drift between `genetics/serialize.py` and `experiments/registry/schema.py`. Must share dict format constants.
- Large population JSON (100 individuals × 50 params = 5000 floats) is fine per row.

---

### Task 10: GA Config + Serialization (`genetics/config.py`, `genetics/serialize.py`)

**Acceptance:**
- `GAConfig(genome_def, pop_size=100, generations=50, crossover_prob=0.8, mutation_prob=0.2, seed=42, n_jobs=4, checkpoint_interval=5, resume_from=None)`
- `GenomeConfig(param_defs: list[GenomeParameter])` — derived from parameter taxonomy
- `IslandConfig(n_islands=4, migration_interval=5, migration_size=3, topology="ring")`
- `WalkForwardConfig(n_folds=5, purge=5, embargo=10)`
- `BacktestConfig(data_source, symbol, start_date, end_date, ...)` — config for backtest engine
- `genome_to_dict(genome) → dict`: JSON-serializable
- `dict_to_genome(d, param_defs) → Genome`
- `population_to_dict(pop) → list[dict]`
- `pop_snapshot(pop, generation, pareto_indices, diversity) → dict`: metadata + all individuals + fitnesses
- `GAConfig.to_dict() → dict`: full experiment hyperparameters
- `GAResult.to_dict() → dict`: result + config + Pareto front + timing + checkpoint paths

**Files to create:** `genetics/config.py`, `genetics/serialize.py`, `tests/genetics/test_serialize.py`

---

### Task 11: Experiment Scripts (`experiments/scripts/`)

**Acceptance:**
- `run_ga.py`: CLI with sensible defaults, checkpoint/restart, saves to Experiment Registry
  - `--config` (JSON/YAML file)
  - `--data` (symbol, date range)
  - `--pop-size`, `--generations`, `--islands`
  - `--seed`
  - `--resume <checkpoint_path>` — resume from last checkpoint
  - `--no-log` (dry run, no registry persistence)
  - `--checkpoint-interval` (default 5)
  - Auto-saves checkpoint at SIGTERM / SIGINT for graceful interruption
- `analyze_results.py`: load experiment → Pareto frontier plot (plotly/matplotlib), diversity heatmap, convergence curves, best individual decode → human-readable strategy
- Both scripts: `--help` flag, error handling, progress output

**Files to create:** `experiments/scripts/run_ga.py`, `experiments/scripts/analyze_results.py`

---

## 4. Expanded Test Plan

### Unit Tests (must pass before integration)

| Module | Tests | Key Scenarios |
|--------|-------|---------------|
| `test_parameters.py` | 10+ | Continuous bounds/scale/clamp, Int rounding, Categorical validation, edge cases: zero-range int, single-category cat, log-scale negative check |
| `test_codec.py` | 8+ | encode/decode roundtrip for each parameter type, bounds clamping, int rounding consistency, large values (inf/nan), empty config |
| `test_genome.py` | 8+ | encode/decode roundtrip, bounds clamping, invalid param count, mutation within bounds, large values (inf/nan), empty genome, validation of out-of-bounds |
| `test_signal.py` | 6+ | GenomeToSignal converts each parameter type correctly, missing params → error, extra params → error, all-categorical genome |
| `test_operators.py` | 8+ | crossover produces valid offspring, mutation stays in bounds per parameter type, tournament selection stochastic fairness (chi-squared), NSGA-II selection preserves Pareto diversity, toolbox construction from config edge cases, categorical mutation behavior |
| `test_population.py` | 6+ | seeded 20% ratio exact count, random diversity (no duplicate genomes), HallOfFame uniqueness, degenerate case: pop_size=1, seed_ratio=1.0 (all seeded), empty seed list |
| `test_migration.py` | 6+ | ring topology exact routing, migration merge worst-M replaced, no-op when migration_size=0, single-island degenerate, diversity shift after migration |
| `test_fitness.py` | 12+ | walk-forward fold count exact, purge/embargo correctness (no overlap), GenomeToSignal called correctly, MetricsCalculator static methods invoked with correct types, caching hit/miss, parallel vs sequential consistency, zero returns → sentinel fitness, NaN returns → sentinel fitness, failed backtest → sentinel fitness, cache key collision stability, large cache eviction, single-fold (degenerate config) |
| `test_cache.py` | 6+ | LRU eviction order, key collision (same genome, diff data → separate entries), data version invalidation, max_size enforcement, thread safety |
| `test_islands.py` | 8+ | island isolation (different RNG seeds → different populations), migration effect (diversity shift), ring topology exact routing, migration merge (worst M replaced), all-island Pareto front merge deduplication, single-island (degenerate), concurrent non-determinism (same seed → same result), executor shutdown clean |
| `test_engine.py` | 8+ | checkpoint save/restore roundtrip, resume from generation N skips completed generations, full run produces GAResult with Pareto front, graceful SIGTERM saves checkpoint, resume from corrupted checkpoint → error, empty run (gen=0), resume with different config → error |
| `test_serialize.py` | 8+ | genome→dict→genome roundtrip, population→dict roundtrip, NaN/inf in fitness dict, large genome serialization, unknown field preservation, schema validation, dict→genome with different param_defs → error, checkpoint dict schema |
| `test_alpha_library.py` | 55+ | each of 50 factors + 5 batch compute edge cases; known values for RSI, BB, SMA, ROC, correlation, beta; NaN handling per factor, empty series, constant series (zero vol), single-element series |
| `test_precompute.py` | 6+ | precomputation covers all 50 factors, cache hit returns correct values, cache miss triggers compute, data change → cache miss, concurrent access, empty data edge case |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_end_to_end_single_island` | pop=10, gen=5, one island, synthetic price data, typed parameters. Verifies: all generations complete, fitness improves or stays stable, Pareto front non-empty, Experiment Registry log written |
| `test_end_to_end_multi_island` | pop=10 per island, 2 islands, gen=5, migration every 2 gens. Verifies: final Pareto front larger than single island, migration events logged, async completion |
| `test_checkpoint_resume` | Run 5 generations, checkpoint, resume, run 5 more → same result as 10-generation run without interruption |
| `test_seeded_convergence` | 1 seeded strategy should appear in first-generation Pareto front. Verifies genome encoding fidelity. |
| `test_reproducibility` | Same seed → identical population, identical fitness trajectory, identical Pareto front. Runs twice, asserts genome-level equality. |
| `test_walk_forward_consistency` | Walk-forward with purge=0, embargo=0 → should be equivalent to single backtest (modulo fold boundary effects). |
| `test_genome_to_signal_integration` | Encode known parameters → GenomeToSignal → BacktestSignal → BacktestEngine.run → verify trade signal matches expected behavior |

### Pre-Mortem: 6 Failure Scenarios

**Scenario A: GA converges on noise, not signal.**
- *Indicators:* Fitness improves each generation but degrades on out-of-sample data. Pareto front shifts right without generalization.
- *Root cause:* Walk-forward folds are too few (3) or purge too short. GA overfits to noise in the training folds.
- *Defense:* Minimum 5 folds. Mandatory out-of-sample validation after GA run (time period after the walk-forward window). If OOS Sharpe < walk-forward Sharpe by 0.5, flag experiment.

**Scenario B: Island diversity collapses.**
- *Indicators:* All islands converge to identical Pareto front by generation 20. Migration overwhelms local diversity.
- *Root cause:* Migration interval too short or migration size too large. Islands homogenize.
- *Defense:* Default migration_interval=5, migration_size=3 for pop=100. Monitor diversity per island; log warning if diversity drops below threshold (mean pair distance < 0.05). Adaptive migration that reduces when diversity is low.

**Scenario C: Fitness cache poisoning.**
- *Indicators:* Fitness function returns cached stale values after data refresh. GA optimizes against outdated landscape.
- *Root cause:* Cache key does not include data version hash. Re-run with different data → same cache hits.
- *Defense:* Cache key = `(genome_hash, fold_config_hash, data_version_hash)`. Data version = sha256 of data start/end dates + symbol list.

**Scenario D: Checkpoint corruption or incompatibility.**
- *Indicators:* `--resume` fails with deserialization error; checkpoint file exists but has wrong schema.
- *Root cause:* Code changes between GA runs (new parameter types, changed config fields). Schema version not tracked.
- *Defense:* Checkpoint file includes `schema_version` integer. On resume, assert exact match. If mismatch, error with message "Checkpoint schema v{N} incompatible with current v{M}. Start fresh with --seed <same> for reproducibility."

**Scenario E: Factor pre-computation introduces look-ahead bias.**
- *Indicators:* GA performance on training folds is unrealistically high, but live performance degrades.
- *Root cause:* FactorPrecomputer computes factors using the full data window, including future data relative to the walk-forward fold's training period.
- *Defense:* FactorPrecomputer must be fold-aware: compute factors using only data available up to the fold's training end date. Integration test asserts fold isolation.

**Scenario F: ProcessPoolExecutor deadlock on asyncio event loop.**
- *Indicators:* GA hangs after first generation. ProcessPoolExecutor tasks never return.
- *Root cause:* DEAP's multiprocessing map uses fork (on Linux) which can deadlock inside asyncio event loop. Or submitted tasks reference non-picklable objects.
- *Defense:* Use `multiprocessing.get_context('spawn')` on all platforms. All task arguments must be picklable (no lambdas, no closures). Integration test verifies clean parallel execution.

---

## 5. ADR — Decision Record

### ADR-001: Genetic Engine Framework

- **Decision:** Adopt DEAP with custom async island manager and typed parameters
- **Drivers:** DEAP is already a dep; NSGA-II and bounded operators are mature; custom island model needed for parallel execution
- **Alternatives considered:** Custom GA (rejected: unnecessary effort), PyGAD (rejected: weaker multi-objective), Ray (deferred)
- **Why chosen:** Lowest risk path with proven core algorithm
- **Consequences:** Must wrap DEAP's synchronous operators in async execution layer; DEAP 1.4 API surface is stable but verbose
- **Follow-ups:** Phase 4 may evaluate Ray for multi-node island execution

### ADR-002: Genome Representation

- **Decision:** Typed parameter vector (Continuous, Int, Categorical) with normalized [0,1] encoding
- **Drivers:** Type safety, serialization simplicity, DEAP compatibility; Phase 3 scope constraint
- **Alternatives considered:** Flat float vector (rejected: silent type errors), Expression-tree GP (Phase 4), hybrid (Phase 5+)
- **Why chosen:** Typed taxonomy prevents silent bugs (e.g. treating integer `lookback` as continuous), enables per-type mutation semantics, and provides self-documenting parameter definitions
- **Consequences:** Cannot discover novel alpha factors (deferred to Phase 4). Must carefully map each genome dimension to interpretable strategy parameter.
- **Follow-ups:** Phase 4 adds expression-tree representation alongside vector for factor discovery.

### ADR-003: Alpha Factor Library Scope

- **Decision:** Start with 50 curated factors, not 484, with fold-aware pre-computation
- **Drivers:** Too many factors → overfitting risk and compute cost; 50 factors × 50 genome params → rich search space; pre-computation drastically reduces fitness evaluation cost
- **Alternatives considered:** 484 factors (FinClaw scale), expression-tree GP
- **Why chosen:** Balances search diversity with robustness and compute budget
- **Consequences:** Factors must be carefully selected for diversity and minimal redundancy. Each factor needs unit test with known values. Pre-computation must be fold-aware to avoid look-ahead bias.
- **Follow-ups:** Expand library to 100-150 factors in Phase 4 based on empirical factor importance.

### ADR-004: Fixed Interface Contracts

- **Decision:** Define exact BacktestEngine, MetricsCalculator, WalkForwardEngine interfaces with static methods; stub if missing
- **Drivers:** GA fitness evaluator cannot depend on hypothetical interfaces; static methods are pickle-safe for multiprocessing
- **Alternatives considered:** Dynamic duck-typing (rejected: fragile), abstract base classes (rejected: add coupling)
- **Why chosen:** Static method signatures with typed return values give maximum flexibility for future Phase 0-2 implementations while keeping the GA engine testable now.
- **Consequences:** If Phase 0-2 APIs differ from the defined contracts, adapter methods will be needed at integration time.

### ADR-005: Checkpoint/Restart Strategy

- **Decision:** Checkpoint every N generations (default 5) to Experiment Registry + local JSON file; `--resume` flag
- **Drivers:** GA runs of 50+ generations can take hours. A crash mid-run loses all progress. Checkpoints enable interruption-resilient experimentation.
- **Alternatives considered:** In-memory only (rejected: crash-prone), Database-only (rejected: higher latency per checkpoint), Every generation checkpoint (rejected: I/O overhead)
- **Why chosen:** Local JSON enables fast checkpoint I/O; Experiment Registry provides durable cross-session storage. Dual-path for speed + safety.
- **Consequences:** Checkpoint schema versioning required. `--resume` with different config must error. SIGTERM handler must write emergency checkpoint.

---

## 6. Success Criteria

1. GA converges (fitness improves) on synthetic price data with known regime structure within 50 generations. *Measured:* mean Sharpe of top-10 individuals increases from generation 1 to 50.
2. NSGA-II produces a non-trivial Pareto front (≥3 distinct trade-off points) for Sharpe vs Sortino vs Calmar vs MaxDD. *Measured:* Pareto front size ≥ 3 at generation 50.
3. Island model produces more diverse solutions than single-island with same total population. *Measured:* mean pairwise genome distance 20% higher for 4-island vs 1-island at same total pop.
4. Same seed → identical result (genome-level, not just statistical). *Measured:* two runs with seed=42 produce identical Pareto front individuals.
5. Checkpoint/resume produces identical result to uninterrupted run. *Measured:* checkpoint at gen 25, resume, compare final Pareto front to single-run.
6. Walk-forward purge/embargo enforces temporal isolation. *Measured:* assertion-based test in test_fitness.py verifies no fold overlap.
7. All tests pass: `ruff check`, `mypy --strict`, `pytest --cov>=85%`.

---

## 7. Implementation Order

```
Week 1:  Task 0 (scaffold + DEAP) + Task 1 (typed params) + Task 2 (genome core + signal adapter)
Week 2:  Task 3 (alpha library + precompute) + Task 4 (interface contracts)
Week 3:  Task 5 (operators) + Task 6 (fitness evaluator + cache)
Week 4:  Task 7 (population + migration) + Task 8 (island model + checkpoint/engine)
Week 5:  Task 9 (registry schema) + Task 10 (config + serialization) + Task 11 (scripts)
Week 6:  Integration tests, polish, review
```

**Hard dependencies:**
- Task 4 defines the interfaces that Tasks 6 and 8 depend on. Task 4 must complete before Task 6 implementation.
- Task 1 (typed params) must complete before Task 2 (genome) and Task 5 (operators).
- Task 3 (alpha) should complete before Task 6 (fitness) since FactorPrecomputer is an input.
- Task 9 (registry schema) can run in parallel with Tasks 1-8.
- Tasks 1-8 are prerequisites for Task 11 (scripts).

**Soft dependencies:**
- Phase 0-2 BacktestEngine, MetricsCalculator, WalkForwardEngine: if non-existent, Task 4 produces stubs. Integration with real implementations is a Phase 3.5 concern.

---

## 8. Open Questions

- [ ] **Phase 0-2 state:** Are BacktestEngine, MetricsCalculator, WalkForwardEngine actually implemented somewhere, or do we need stubs? This affects Task 4 acceptance criteria and integration test strategy.
- [ ] **Data availability:** What OHLCV data source will GA use for fitness evaluation in CI/test mode? Synthetic data in tests; yfinance or local parquet for experiments?
- [ ] **Experiment Registry:** What DB backend is the Experiment Registry using? SQLite? PostgreSQL? This affects `experiments/registry/schema.py` import strategy.
- [ ] **pyproject.toml:** Does one exist yet? If not, Task 0 must create it. What build system and other deps are already configured?
