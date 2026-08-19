> **ARCHIVIO STORICO.** Documento del modello Phase, deprecato da ADR-012
> e sostituito dai capability gate G0-G9. Roadmap canonica:
> [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).
> **Non aggiornare** — solo git archaeology.

# Oracle Phase 2: Backtesting — Implementation Plan (REVISED v2)

> **Status:** REVISED v2 — All Architect (R1-R7) and Critic (F1-F6) findings applied
> **Date:** 2026-07-09
> **Phase:** 2 (Weeks 5–7 — revised from 2 to 3 weeks)
> **Prerequisite:** Phase 0-1 (Core Infrastructure, Data Ingestion, Feature Store, Technical Analysis, Regime Detection, Sentiment, Macro, Fundamentals)
---

## 1. RALPLAN-DR Summary

### Principles

1. **Correctness first** — Backtest results must match reality. Every fill model, slippage assumption, and metric calculation gets verified against known baselines before we trust it.
2. **Reuse over reinvent** — Phase 0-1 built: Experiment Registry, Feature Store, Event Bus, AnalyticsOrchestrator, Domain Models. The backtest engine must integrate with these rather than duplicate them.
3. **Dual-engine architecture** — Researchers need fast iteration (vectorized) AND production realism (event-driven). We build a `BacktestEngine` abstraction that supports both, with cross-validation.
4. **Composability** — Strategies, fill models, metrics, and data sources should be swappable. A strategy written for vectorized mode must be easy to port to event-driven.
5. **Observability** — Every backtest is an Experiment. Parameters, results, artifacts, and comparisons are logged to the Experiment Registry automatically (ADR-007).
6. **Signal execution integrity** — All signals are computed on bar close and executed at the next open. No look-ahead, no intrabar peeking. This invariant is enforced at the `BacktestSignal` protocol level (R4, F4).
7. **Data provenance** — Every data source carries documented survivorship bias (R7). The Feature Store maintains dual-format OHLCV (wide-format for backtest reads, long-format for features) to optimize both access patterns (R2).
8. **Persistent results** — Every `BacktestResult` is a Pydantic model serialized to both Parquet (for analysis) and the Experiment Registry (for audit). No result is ephemeral (F5).
| D1: Backtest engine | Critical | Determines architecture, performance, realism tradeoff for entire Phase 2 |
| D2: Metrics library | High | Must produce trustworthy Sharpe/Sortino/Calmar; regression-tested across engines |
| D5: Fill model | High | Slippage assumptions dominate strategy P&L; naive fills give false confidence |

### Options Considered

#### D1: Backtest Engine Strategy

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Hybrid (nautilus_trader + vectorbt)** | Best of both: event-driven realism + vectorized speed; nautilus already installed; vectorbt enables rapid parameter sweeps | Integration surface; two APIs to maintain; vectorbt not yet installed | **SELECTED** — Dual engine with common interface |
| nautilus_trader only | Already installed; production-grade; HFT-quality fills | Slow for parameter sweeps; overkill for simple strategies | Rejected — too slow for research iteration |
| Custom lightweight engine | Full control; no dependency on external lifecycle | Rebuilding what exists; months of work; likely buggy | Rejected — massive waste |
| vectorbt only | Fast; great UI; Numba-accelerated | No realistic fills; no live trading path; limited strategy complexity | Rejected — insufficient for production |

#### D2: Metrics Framework

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **quantstats** | Already installed; comprehensive (Sharpe, Sortino, Calmar, MaxDD, waterfall); matplotlib+seaborn plots | Some functions need Pandas Series not Polars; actively maintained | **SELECTED** — Primary metrics engine |
| ffn | Lightweight; simple API | Less comprehensive; less actively maintained | Rejected — quantstats covers more |
| pyfolio | Tear sheets; well-known; risk analysis | Abandoned/unmaintained; depends on zipline | Rejected — maintenance risk |
| Custom | Full control | Reimplementing quantstats; months of work | Rejected — waste |

#### D3: Walk-Forward Approach

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Custom WFA built on Oracle infrastructure** | Leverages FeatureStore for data windows; Experiment Registry for tracking; our code, our control; composable with both engines | Implementation effort; need to handle look-ahead bias ourselves | **SELECTED** — nautilus has no built-in WFA; PyBroker would add heavy dependency |
| PyBroker integration | ML-focused WFA; built-in walk-forward; bias correction | Heavy dependency; ML-centric assumptions; conflicts with dual-engine plan | Rejected — wrong abstraction layer |
| nautilus_trader native | No extra code | No built-in WFA support | Rejected — doesn't exist |
| Manual (scripts) | Simple to start | No reproducibility; no tracking | Rejected — must track via Experiment Registry |

#### D4: Backtest Data Source

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **FeatureStore (Parquet + DuckDB)** | Already built in Phase 1; Polars-native; DuckDB for SQL-like queries; excellent performance | May need optimization for tick data | **SELECTED** — reuse existing infrastructure |
| QuestDB | Time-series optimized; SQL; streaming | Additional infrastructure; not yet deployed; operational overhead | Deferred — evaluate in Phase 3 if latency becomes an issue |
| Custom HDF5 | Portable; hierarchical | No query capability; no ecosystem; additional code | Rejected — no advantage over Parquet+FeatureStore |

#### D5: Fill Model

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Hybrid (nautilus native + custom OHLC)** | nautilus provides L1/L2 fills; custom OHLC for vectorized mode; covers both engines | Two implementations; must regression-match them | **SELECTED** — nautilus for event-driven; OHLC with configurable slippage for vectorized |
| hftbacktest-style queue model | Most realistic L2 order book simulation | Heavy; requires tick data; not needed for most strategies | Deferred — add in Phase 4 for HFT strategies |
| Simple OHLC only | Fast; easy to implement | No realistic fills; false confidence | Rejected — too naive |

#### D6: Portfolio Optimization

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **PyPortfolioOpt** | Efficient frontier; HRP; Black-Litterman; scikit-learn API; well-documented | Not installed; adds dependency | **SELECTED** — most comprehensive for Phase 2 needs |
| Riskfolio-Lib | CVaR, CDaR, Omega-optimization; very comprehensive | Heavier dependency; overlapping functionality | Deferred — add in Phase 3 if CVaR optimization needed |
| Custom allocation | Full control | Reimplementing; likely buggy; months of work | Rejected — waste |

---

## 2. Architecture

### How Backtesting Fits Oracle's 8-Layer Architecture

```
Phase 0-1 (Existing)         Phase 2 (New)
==================           ==============

Layer 8: CLI/API             ─────────────────► Layer 8: CLI/API (backtest commands)
Layer 7: Experiment Registry ─────────────────► Layer 7: Backtest Experiment Logging
Layer 6: AnalyticsOrchestrator ───────────────► Layer 6: BacktestOrchestrator
Layer 5: Regime/Sentiment/   ────────────────► Layer 5: Strategy Engine (strategies + portfolio)
  Macro/Fundamental                             + Walk-Forward Validator
Layer 4: Feature Store       ─────────────────► Layer 4: BacktestDataProvider (wraps FeatureStore)
Layer 3: Market Ingestion                       Layer 3: Fill Models + SimulatedExchange
Layer 2: Core Domain Models ─────────────────► Layer 2: BacktestResult + Metrics Models
Layer 1: Config/Logging/     ─────────────────► Layer 1: No changes (reuse existing)
  Plugin/Event Bus
```

### Module Map (new/ modified)

```
backtest/
├── __init__.py
├── engine.py                 # BacktestEngine (abstract + dual-mode orchestrator)
├── engine_nautilus.py        # NautilusEventDrivenEngine
├── engine_vectorized.py      # VectorizedEngine (wraps vectorbt or custom polars)
├── data.py                   # BacktestDataProvider (wraps FeatureStore; wide-format OHLCV read path, R2)
├── protocol.py               # BacktestSignal Protocol (F4: close→next-open contract)
├── fill.py                   # FillModel (abstract), OHLCFill with volume participation (R5), nautilus adapter
├── metrics.py                # MetricsCalculator (Polars-native Sharpe/Sortino/Calmar; quantstats for plots only, R6)
├── walk_forward.py           # WalkForwardValidator
├── optimizer.py              # PortfolioOptimizer (wraps PyPortfolioOpt)
├── orchestrator.py           # BacktestOrchestrator (separate from AnalyticsOrchestrator, F6)
├── benchmark.py              # BenchmarkEngine (buy-and-hold, market, etc.)
├── bias.py                   # BiasCorrection
├── result.py                 # BacktestResult Pydantic model (F5); serialized to Parquet + Experiment Registry
├── validation.py             # Cross-validation results comparison
└── config.py                 # BacktestConfig, WalkForwardConfig, EngineConfig, BacktestSettings (R3)

feature_store/
└── ohlcv_pivot.py            # Dual-format OHLCV: wide-format Parquet for backtest reads + long-format for features (R2)
```

### Data Flow

```
                ┌─────────────────────┐
                │  CLI / User Request │
                └─────────┬───────────┘
                          │
                          ▼
               ┌────────────────────────────┐
               │  BacktestOrchestrator       │
               │  (backtest/orchestrator.py, │
               │   separate from Analytics-  │
               │   Orchestrator)             │
               └──────┬──────┬───────────────┘
                      │      │
           ┌──────────┘      └──────────┐
           ▼                             ▼
┌─────────────────────┐     ┌─────────────────────┐
│ NautilusEventDriven │     │   VectorizedEngine  │
│ Engine              │     │   (wraps vectorbt)  │
│  • SimulatedExchange│     │   • Polars-native   │
│  • OrderMatching    │     │   • Numba/vectorized│
│  • L1/L2 fills      │     │   • Configurable    │
│                     │     │     slippage        │
└──────────┬──────────┘     └──────────┬──────────┘
           │                            │
           └──────────┬────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  WalkForwardValidator│
           │  • Rolling windows   │
           │  • Purged CV         │
           │  • Combinatorial     │
           │    purged            │
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  MetricsCalculator  │
           │  (wraps quantstats) │
           │  • Sharpe/Sortino/  │
           │    Calmar/MaxDD     │
           │  • Benchmark comp.  │
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  Experiment Registry│
           │  • Log parameters   │
           │  • Store results    │
           │  • Track runs       │
           └─────────────────────┘
```

---

## 3. Milestones (3-Week Sprint, 8 Milestones — revised from 2 weeks)

> **Timeline:** Week 5 → M1-M3, Week 6 → M4-M6, Week 7 → M7-M8
### Milestone 1: Backtest Domain Models + Config (Week 5, Days 1–3)
**Deliverable:** Core data models and configuration schemas
- `BacktestResult` Pydantic model (F5): all standard metrics, equity curve, trades; serializable to Parquet + ExperimentRegistry
- `BacktestSettings` in OracleSettings with `initial_capital: Decimal` on Portfolio model (R3)
- `BacktestSignal` Protocol (R4, F4):
  - Signals computed on bar close, executed at next open — no intrabar peeking
  - Pure function signature: `(features: dict[str, PolarsSeries], timestamp) → signal: float`
  - Enforced at the protocol level so both engines inherit the same contract
- `BacktestConfig`: engine_type, instruments, date range, fill model, initial_capital
- `WalkForwardConfig`: window sizes, step sizes, purge width
- `MetricsResult`: structured metrics container (Sharpe, Sortino, Calmar, etc.)
- Reuse existing domain models (Order, Trade, Position, Portfolio from Phase 1)

**Acceptance:** Config serializes to/from dict; all fields validated with Pydantic; signal protocol type-checks with strict mypy
### Milestone 2: BacktestDataProvider (Week 5, Days 3–5)
**Deliverable:** Unified data interface wrapping FeatureStore with OHLCV pivot support

- OHLCV Pivot (R2): Dual-format strategy
  - Wide-format OHLCV Parquet for backtest read path (one column per price field per instrument)
  - Long-format for feature computation (existing Phase 1 FeatureStore)
  - DuckDB PIVOT as fallback for ad-hoc queries
  - Pre-computed rollups for vectorized engine performance
- Survivorship bias documentation (R7): every data source carries a `survivorship_bias` flag in metadata; docs explain which indices/symbols are point-in-time vs current-constituent
- Query FeatureStore (Parquet + DuckDB) for instrument data
- Support: OHLCV (daily/intraday), tick bars, order book snapshots (L1/L2)
- Time range slicing with proper alignment
- Convert Polars DataFrame to nautilus_trader data types (QuoteTick, TradeTick, Bar)
- Support for multiple instruments and universes

**Acceptance:** Can feed a week of EUR/USD data from FeatureStore to both engines; wide-format OHLCV loads 2x faster than long-format on read
### Milestone 3: VectorizedEngine (Week 5, Days 5–7)
**Deliverable:** Fast Polars-native vectorized backtester with volume-aware fill model

- `VectorizedEngine` implementing `BacktestEngine` abstract interface
- Strategy signal vector: 1D Polars Series over time
- OHLC fill model with:
  - Configurable slippage (bps) and commission (flat + pct)
  - **Volume participation** (R5): `fill_qty = min(order_qty, volume * max_participation_rate)` — prevents unrealistic fills exceeding market volume
  - Falls back to slippage-only when volume data unavailable
- Position sizing: fixed, fractional, Kelly-optimized, risk-budgeted
- Portfolio aggregation: multi-instrument position tracking, cash balance, P&L
- Equity curve computation
- Performance: <1s for 5 years of 1m bars on single instrument

**Acceptance:** Reproduces known strategy returns within 0.1% of reference; volume participation limit caps fills at configured rate
### Milestone 4: NautilusEventDrivenEngine (Week 6, Days 8–14 — revised from 2 days to 5–7 days)
**Deliverable:** Production-grade event-driven backtester via nautilus_trader

- Add `nautilus-trader` to pyproject.toml `[tool.poetry.group.backtest.dependencies]` (F1)
- `NautilusEventDrivenEngine` implementing `BacktestEngine`
- Configure nautilus BacktestEngine with SimulatedExchange (venue, OMS, account)
- Strategy adapter: wraps Oracle strategy signals as nautilus TradingStrategy
- Fill model: nautilus native order matching (L1/L2 queue model)
- Data feed: BacktestDataProvider → nautilus data catalog
- Result extraction: equity curve, trades, fill events from BacktestResult
- Commission + slippage config matching VectorizedEngine parameters

**Acceptance:** Same strategy produces similar equity curves (±5% due to fill model differences); runs in <10s for 5 years of 1m data
### Milestone 5: Metrics + Benchmarks (Week 6, Days 8–12)
**Deliverable:** MetricsCalculator with Polars-native core metrics; quantstats for plots only; reference dataset baseline

- Add `quantstats` to pyproject.toml `[tool.poetry.group.backtest.dependencies]` (F1)
- **Polars-native Sharpe/Sortino/Calmar** (R6): Implement core performance metrics directly in Polars to avoid quantstats Pandas dependency for CI/headless runs
- **quantstats for plots only** (R6): waterfall charts, monthly heatmaps, underwater plots — called only when `generate_plots=True`
- Full metrics suite:
  - Sharpe, Sortino, Calmar, Max Drawdown, CAGR, Volatility, Win Rate
  - Profit Factor, Payoff Ratio, Recovery Factor, Ulcer Index
  - Monthly returns heatmap, drawdown plot, underwater chart
- Benchmark comparisons: buy-and-hold, market index, sector benchmark, risk-free rate
- Comparison table: strategy vs benchmark across all metrics
- Configurable risk-free rate (FRED data, or config override)
- **Reference dataset** (F3): SMA crossover on SPY (2015–2020) with documented expected Sharpe (~0.6–0.8) and Sortino (~0.9–1.2) — serves as CI gate and regression anchor

**Acceptance:** Polars-native metrics match quantstats reference to 1e-8; SMA crossover baseline reproduces expected Sharpe/Sortino within ±10%
### Milestone 6: Walk-Forward Validation (Week 6, Days 10–14)
**Deliverable:** Custom walk-forward analysis framework with SQLite ExperimentRegistry

- **ExperimentRegistry upgrade (pre-M6, R1):** Migrate from JSONL+threading.Lock to SQLite+async
  - Use `aiosqlite` for async I/O; add to pyproject.toml backtest extras
  - Add `parent_experiment_id` to Experiment model for WFA hierarchy (each fold is a child experiment)
  - All WFA runs create experiment tree: root (WFA run) → children (individual folds)
- Rolling window splitter: train/test pairs with configurable purge width
- Purged Cross-Validation (advance/purge to prevent data leakage)
- Combinatorial Purged Cross-Validation (CPCV) for parameter robustness
- Walk-forward ratio: OOS Sharpe / IS Sharpe
- Parameter stability analysis: variance of optimal params across windows
- Integration with Experiment Registry for tracking each fold using parent_experiment_id
- **Bias correction:** Lopez de Prado's deflated Sharpe ratio; Bayesian adjustment

**Acceptance:** Reproduces a known WFA example; reports IS/OOS performance across windows; experiment tree shows parent-child relationship in SQLite
### Milestone 7: Portfolio Optimization + Bias Correction (Week 7, Days 15–17)
**Deliverable:** PyPortfolioOpt integration and bias correction pipeline

- `initial_capital: Decimal` added to `BacktestSettings` (R3) — Portfolio model reads from config, not hard-coded
- `BacktestOrchestrator` created at `backtest/orchestrator.py` (F6)
- PortfolioOptimizer wrapping PyPortfolioOpt:
  - Mean-Variance (max Sharpe, min volatility)
  - Hierarchical Risk Parity (HRP)
  - Black-Litterman (if configs available)
  - CVaR optimization (via Riskfolio-Lib if installed)
- Bias correction methods:
  - Deflated Sharpe Ratio (DSR)
  - Bayesian posterior Sharpe adjustment
  - Selection bias correction (multiple testing adjustment)
- Results merged into BacktestResult metrics

**Acceptance:** Optimized portfolio weights computed; DSR reported alongside standard Sharpe; initial_capital flows from config → Portfolio → P&L
### Milestone 8: CLI Integration + Cross-Engine Regression Tests (Week 7, Days 17–21)
**Deliverable:** CLI commands, regression test suite, result persistence, integration tests

- CLI commands (via existing CLI infrastructure):
  ```
  oracle backtest run --strategy <name> --engine <vectorized|nautilus> [options]
  oracle backtest walk-forward --strategy <name> [options]
  oracle backtest compare <run-id-1> <run-id-2>
  oracle backtest list [--status]
  ```
- **Result persistence** (F5): every `BacktestResult` serialized to Parquet (for analysis) and logged to ExperimentRegistry (for audit); CLI can query by run ID
- **Reference dataset integration tests** (F3): SMA crossover on SPY (2015–2020) runs as CI gate; expected Sharpe/Sortino validated on every PR
- **BacktestOrchestrator** (backtest/orchestrator.py) wired to CLI, separate from AnalyticsOrchestrator (F6)
- Cross-engine regression tests: same strategy → same metrics (within tolerance)
- Known-baseline tests: reproduce canonical strategy returns
- Experiment Registry integration: all runs logged automatically
- Documentation: backtest API docs, user guide
- ruff strict + mypy strict clean

**Acceptance:** All tests pass; CLI commands functional; cross-engine diff <5% on equity curves; reference dataset gate passes in CI
## 4. Key Design Decisions

### D1 (SELECTED): Hybrid Engine — nautilus_trader + Vectorized

```
BacktestEngine (ABC)
├── run(config: BacktestConfig) -> BacktestResult
├── run_walk_forward(config: WalkForwardConfig) -> WFRresult
├── equity_curve() -> Polars Series
└── trades() -> List[Trade]
    ├── NautilusEventDrivenEngine   # Production realism
    └── VectorizedEngine            # Rapid iteration
```

- Vectorized is DEFAULT for research (speed). Nautilus is DEFAULT for production validation.
- Cross-engine regression tests at M8 ensure they agree within tolerance.
- Strategy abstraction allows writing once, running on both.

### D2 (REVISED): Polars-Native Metrics + quantstats for Plots (R6)

Starting from the original quantstats selection, we split responsibilities:
- **Polars-native (R6):** Sharpe, Sortino, Calmar, and all core ratios computed directly in Polars — no Pandas dependency, works in CI/headless, fast on large equity curves
- **quantstats (plots only):** Waterfall charts, monthly heatmaps, drawdown plots — called only when `generate_plots=True`
- Reference implementation: both implementations are regression-tested against each other to 1e-8
- Comparison engine: strategy vs benchmark vs risk-free
### D3 (SELECTED): Custom Walk-Forward on Oracle Infrastructure

- `WalkForwardValidator` uses FeatureStore for data folding (no duplication)
- Each fold is a sub-Experiment in the Experiment Registry
- Supports: Simple Rolling, Purged CV, Combinatorial Purged CV
- Bias correction integrated post-WFA

### D4 (REVISED): FeatureStore (Parquet + DuckDB) + OHLCV Pivot (R2)

Starting from the original D4, we add a dual-format strategy:
- **Wide-format OHLCV Parquet** for backtest read path — one column per price field per instrument, optimized for vectorized engine time-series slicing
- **Long-format** for feature computation (existing Phase 1 FeatureStore)
- DuckDB PIVOT as fallback for ad-hoc queries
- DataProvider abstracts source; FeatureStore is default
- Allows on-the-fly resampling: tick → 1s → 1m → 1d
- DuckDB for time-windowed aggregations without loading full dataset

### D5 (REVISED): Hybrid Fill Model with Volume Participation (R5)

| Engine | Fill Model | Realism | Speed |
|--------|-----------|---------|-------|
| Vectorized | OHLC with configurable slippage (bps) + **volume participation limit** (R5): `fill_qty = min(order_qty, volume * max_participation_rate)` | Medium | Fastest |
| Nautilus | Native L1/L2 queue model via SimulatedExchange + OrderMatchingEngine | High | Slower |

Both engines accept the same slippage/commission config parameters
Vectorized fill price: `signal_price * (1 ± slippage_bps/10000)`; fill quantity capped by volume participation
Volume participation falls back to slippage-only when volume data unavailable
Nautilus uses full order book simulation

- Integrated via PortfolioOptimizer adapter
- HRP for multi-asset portfolios (no invertibility requirement)
- Mean-Variance for concentrated strategies
- Conditional: Riskfolio-Lib deferred to Phase 3 for CVaR optimization

### D7 (NEW): SQLite+async ExperimentRegistry (R1)

Migrate from JSONL+threading.Lock to SQLite+async (`aiosqlite`) for:
- **Concurrent access:** Multiple WFA folds can log results simultaneously without lock contention
- **Hierarchical experiments:** `parent_experiment_id` enables experiment trees (WFA run → individual folds → parameter sweeps)
- **Queryability:** SQL queries on experiment metadata, parameter comparisons across runs
- The existing `Experiment` model gains `parent_experiment_id: Optional[str]`
- All Phase 1 callers continue to work via a backward-compatible sync wrapper

---

## 5. Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Look-ahead bias in WFA** | Medium | Critical | Data purging enforced at DataProvider level; purged cross-validation; test on known datasets first |
| **Nautilus API changes** | Medium | Medium | Pin version (1.224.x); abstract adapter layer; integration tests catch regressions |
| **Cross-engine metric mismatch** | High | Medium | Regression test suite (M8); document expected tolerance (±5%); metrics comparison is feature, not bug |
| **FeatureStore missing required data** | Low | High | DataProvider raises clear errors; backfill scripts; fallback CSV import |
| **quantstats breaking changes** | Low | Low | Wrap in MetricsCalculator; pin dependency version; unit tests reproduce known values |
| **Performance with multi-instrument + tick data** | Medium | Medium | Profile early; optimize hot paths; vectorized engine should handle; nautilus has Cython/Rust for perf |
| **Strategy overfitting (false discovery)** | High | Critical | Deflated Sharpe Ratio (DSR); combinatorial purged CV; out-of-sample holdout; strict WFA discipline |
| **Symbol mapping mismatches** | Medium | Medium | Normalizer handles internal→exchange mapping; backtest data needs the same treatment |
| **Survivorship bias in price data** (R7) | High | High | Every data source tagged with `survivorship_bias` flag; documentation explains which indices are point-in-time vs current-constituent; backtests should use point-in-time data where available; bias impact quantified in reference dataset validation |

### Pre-Mortem: 3 Failure Scenarios

1. **"The equity curves don't match"** — Vectorized and nautilus produce wildly different results. Root cause: fill model assumptions diverge at high-frequency or during volatile regimes. Fix: Add fill model configuration validation; document expected divergence; provide fill-simulation equivalence table.

2. **"Walk-forward says it's great, live says it's not"** — Classic overfitting despite WFA. Root cause: WFA windows aren't independent (serial correlation leakage). Fix: Increase purge width; add combinatorial purged CV as mandatory gate before production.

3. **"First backtest run takes 20 minutes"** — Data loading is the bottleneck. Root cause: FeatureStore not optimized for time-range slicing at tick granularity. Fix: Add partition pruning; DuckDB index on (instrument, timestamp); pre-compute OHLC rollups for vectorized engine.

---

## 6. New Dependencies

| Package | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| `vectorbt` | >=1.1.0, <2 | Vectorized backtest engine | Fast parameter sweeps, Numba-accelerated |
| `PyPortfolioOpt` | >=1.5, <2 | Portfolio optimization | Efficient frontier, HRP, Black-Litterman |
| `scipy` | (already present) | PyPortfolioOpt dep | — |
| `matplotlib` | (already present) | quantstats plots | — |
| `seaborn` | (already present) | quantstats plots | — |
| `nautilus-trader` | >=1.224, <2 | Event-driven engine | Production-grade backtest engine (F1) |
| `quantstats` | >=0.0.64, <1 | Plots | Deferred to backtest extras group for plots only (R6, F1) |
| `aiosqlite` | >=0.20, <1 | Async SQLite | ExperimentRegistry async I/O (R1) |
| `riskfolio-lib` | OPTIONAL, >=1.3 | CVaR/CDaR optimization | Deferred to Phase 3 |

### Dependency Decision Record

- **Backtest extras group (F1):** `quantstats`, `nautilus-trader` added to `[tool.poetry.group.backtest.dependencies]` so core install stays lean
- **vectorbt (new):** The dual-engine strategy requires a fast vectorized engine. Custom Polars-native vectorized engine is smaller scope (can be built without vectorbt), but vectorbt provides proven Numba-accelerated backtesting with portfolio support. We add it.
- **PyPortfolioOpt (new):** Required for D6. Lightweight, well-maintained, scikit-learn API interface.
- **aiosqlite (new, R1):** Required for async SQLite ExperimentRegistry migration. Minimal dependency (pure Python + libsqlite3).
- **quantstats (new, F1):** Added to backtest extras group. Used for plots only; core metrics are Polars-native (R6).
- **nautilus-trader (new, F1):** Added to backtest extras group. Production event-driven backtest engine.
- **riskfolio-lib (deferred):** Adds 2.8MB with many nested deps (cvxpy, etc.). Phase 3 when CVaR becomes critical.
---
## 7. Test Strategy

### Unit Tests

| Component | Tests | Priority |
|-----------|-------|----------|
| BacktestResult | Serialization, field validation, arithmetic (merge, compare), Parquet round-trip (F5) | P0 |
| BacktestSignal | Protocol type-check, close→next-open invariant, pure function contract (R4, F4) | P0 |
| FillModel | Slippage calculation, commission impact, limit fill logic, **volume participation cap** (R5) | P0 |
| MetricsCalculator | Each metric against known reference values (quantstats comparison); Polars-native vs quantstats cross-check (R6) | P0 |
| WalkForwardValidator | Window splitting, purge correctness, fold non-overlap | P0 |
| PortfolioOptimizer | Weight calculation, HRP convergence, validation | P1 |
| BacktestConfig | Deserialization, validation, defaults | P1 |

### Integration Tests
| Scenario | Description |
|----------|-------------|
| **Cross-engine regression (P0)** | Same strategy, same data → metrics within tolerance |
| **Reference dataset (P0, F3)** | SMA crossover on SPY 2015–2020; reproduces expected Sharpe (~0.6–0.8) and Sortino (~0.9–1.2); runs as CI gate |
| **Known baseline (P0)** | Reproduce returns of a published strategy (e.g., SMA crossover on SPY) |
| **Walk-forward end-to-end (P0)** | Full WFA pipeline: data → split → train → test → report |
| **Result persistence (P0, F5)** | BacktestResult → Parquet + ExperimentRegistry; round-trip matches original |
| **ExperimentRegistry upgrade (P0, R1)** | SQLite+async handles concurrent WFA folds; parent_experiment_id queries return correct tree |
| **FeatureStore feed (P1)** | DataProvider → engine, all data types (OHLC, tick, L1); wide-format OHLCV read path (R2) |
| **CLI smoke test (P1)** | All four CLI commands run without error |

### Regression Test Architecture

```
tests/
├── backtest/
│   ├── test_engine_vectorized.py
│   ├── test_engine_nautilus.py
│   ├── test_engine_cross_validate.py   # P0: same strategy, both engines
│   ├── test_metrics.py                 # Known reference values
│   ├── test_walk_forward.py
│   ├── test_fill_model.py
│   ├── test_portfolio_optimizer.py
│   ├── test_data_provider.py
│   └── test_known_baselines.py         # P0: reproduce canonical results
```

### Performance Tests

- Vectorized: <1s for 5 years of 1m OHLCV on 1 instrument
- Nautilus: <10s same scenario (expected slower due to event-driven overhead)
- Walk-forward: 100-fold CPCV in <60s
- Multi-instrument (10): both engines handle within 5x single-instrument time

---

## 8. Open Questions

- [ ] **Data granularity for backtests:** Are we starting with daily OHLCV only, or need intraday (1m, tick) support from day one? — **Recommendation:** Daily+M1; tick data deferred to Phase 4.
- [ ] **Multi-asset universe size:** What's the max number of instruments in a single backtest? — **Recommendation:** Start with 1–10, test up to 100.
- [ ] **vectorbt vs custom Polars vectorized:** If vectorbt API friction is high, we should fall back to building a lightweight custom engine. Revisit at M3.
- [x] **Strategy coupling (F4):** Signals are pure functions (close→next-open). Resolved via BacktestSignal Protocol. — **Decision:** Pure functions for vectorized; stateful adapter for nautilus. Close→next-open invariant enforced at protocol level.
- [ ] **nft/nft files for strategy serialization:** Should backtest configs be YAML, JSON, or Python files? — **Recommendation:** YAML (existing config convention).
- [ ] **Realistic commission models:** Tiered commissions (by volume)? Zero-commission brokers? — **Recommendation:** Flat + percentage first, tiered in Phase 3.
- [ ] **Currency handling:** Single-currency portfolios only, or multi-currency with FX conversion? — **Recommendation:** Single-currency first (USD); multi-currency in Phase 3.

- [ ] **Survivorship bias in data sources (R7):** Which indices/symbols have point-in-time constituent data available? — **Recommendation:** Tag each data source with `survivorship_bias` flag; document known gaps; prefer CRSP/Compustat for US equities.
- [ ] **Reference dataset validation (F3):** SMA crossover on SPY 2015–2020 — expected Sharpe ~0.6–0.8, Sortino ~0.9–1.2. — **Recommendation:** Hard-code these expectations as CI gate thresholds; revisit if data source changes.
