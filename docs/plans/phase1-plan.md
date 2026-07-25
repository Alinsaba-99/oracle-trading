# Oracle Phase 1 — Analytics Engine Implementation Plan

> **Date:** 2026-07-09
> **Status:** REVISED v2 (incorporating Architect & Critic findings)
> **Author:** PlannerPhase1Revise
> **Repository:** `~/_repos/oracle-trading/`
> **Phase 1 Budget:** 2 weeks (wk 3-4 per PROJECT.md)
> **Phase 0 Baseline:** 138 files, +8257 lines, 175 tests, ruff + mypy strict clean

---

## Change Log (v1 → v2)

| # | Change | Type | Section |
|---|--------|------|---------|
| F1 | Added **AnalyticsOrchestrator** at `analytics/orchestrator.py` — manages startup ordering, health aggregation, graceful shutdown; coordinates M4-M8 lifecycle | CRITICAL | §2, §3 M1 |
| F2 | Replaced abstract-only M2 with **concrete data connectors**: Binance WebSocket, yfinance, CoinPaprika REST. Keep `BaseSource` ABC but ship with real implementations | CRITICAL | §3 M2 |
| F3 | Added per-feature-set **asyncio write lock** in FeatureStore; documented cross-feature-set safety | MAJOR | §3 M3 |
| F4 | Fixed **dependency graph**: M6/M7/M8 are data-parallel to M4. Only M5 (Regime) depends on M4. DAG: M1→M2→M3→(M4→M5 ∥ M6 ∥ M7 ∥ M8)→M9 | MAJOR | §2, §3 |
| F5 | **Removed hnswlib** from Phase 1 deps; added to Phase 4 planning doc only | MAJOR | §6 |
| F6 | Added **AnalyticsSettings integration** with OracleSettings, config/analytics.yaml loading in ConfigLoader, with ADR | MAJOR | §1 D6, §3 M1 |
| F7 | Feature Store schema **flattened to long-format** (feature_name, value) — better compression, schema evolution, natural DuckDB queries | MAJOR | §3 M3, §1 pre-mortem |
| AR2 | Added **backpressure model** — bounded asyncio queues with drop-policy in module settings | ARCH | §2, §3 M4-M8 |
| AR3 | Added **in-memory LRU cache** in FeatureStore for hot features | ARCH | §3 M3 |
| AR6 | Added shared **TA-Lib helpers** (numpy conversion, NaN boundary handling) in `converters.py` | ARCH | §3 M1 |
| AR7 | Added **freshness/staleness tracking** in FeatureStore — per-feature-set staleness TTL | ARCH | §3 M3 |
| AR8 | **Enforced UTC** in all new models — timezone-aware datetimes, validation in base model | ARCH | §3 M1 |

---

## 1. RALPLAN-DR Summary

### Principles (Immutable for Phase 1)

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | **Phase 0 core is FROZEN.** No modifications to `core/config/`, `core/errors/`, `core/logging/`, `core/plugin/`, `core/events/`, `core/domain/`. All Phase 1 code lives in `analytics/`, `market/`, and new top-level packages. | Phase 0 has passed review and first commit. Every change to core requires a new ADR and full re-validation. |
| P2 | **Compute once, reuse everywhere.** The Feature Store is the single source of truth for all computed analytics. No component computes the same indicator twice. Every analytics output flows through `feature.updated` NATS events. | ADR-006 (Genome Pipeline) and SPEC.md §8 require this. Duplicate computation violates reproducibility (DD1). |
| P3 | **Polars primary, pandas compat.** Polars is the default DataFrame in all new code. pandas is used only where TA-Lib/numpy APIs require it, with explicit conversion boundaries. | Polars is 10-100x faster than pandas for the multi-timeframe, multi-instrument workloads at Oracle's core. |
| P4 | **Event-driven analytics.** Every analytics module is a NATS consumer and producer. Inputs arrive as events (market.tick, market.bar). Outputs publish as events (feature.updated, regime.updated). No direct function calls between analytics modules. | ADR-001 requires all communication via NATS. This ensures analytics can be distributed, monitored, and replayed independently. |
| P5 | **Fail gracefully on missing data.** Analytics modules must handle partial data, missing instruments, and NaN values without crashing. Each module reports a health status via `system.health`. | Markets have holidays, data gaps, and delistings. A single missing tick must never crash the pipeline. |
| P6 | **UTC everywhere.** All timestamps in new Phase 1 models are timezone-aware UTC datetimes. No naive datetimes, no local time conversions. | Timezone mismatches caused misaligned bars in earlier designs. Every new model validates tz-aware UTC at construction. |

### Decision Drivers (Top 3)

| Driver | Weight | Description |
|--------|--------|-------------|
| **DD1: Reproducibility** | CRITICAL | Every analytics run must be reproducible: input data version, feature store version, and all parameters logged in Experiment Registry. Same input + same version = same output. |
| **DD2: Computation Latency** | HIGH | Features must compute faster than the fastest incoming bar interval (1m). Real-time regime detection must complete within one bar. Indicator computation for 500 instruments × 50 features must complete in <10s. |
| **DD3: Extensibility** | HIGH | New indicators, new data sources, new regime detectors must be addable via plugin without modifying existing code. Plugin system from Phase 0 must be the primary extension mechanism. |

### Key Decisions & Options

#### D1: Feature Store Backend

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Parquet + DuckDB (RECOMMENDED)** | Feature Store backed by Parquet files with DuckDB for analytical queries. FeatureSetVersion tracks schema. **Long-format rows (feature_name, value) for flat schema evolution.** | Zero infrastructure dependencies; columnar compression (10:1+); DuckDB enables SQL directly on features; versioned via directory structure (`features/v1/...`); lightweight embeddable; long-format enables natural SQL (`SELECT * WHERE feature_name = 'sma_20'`). | No built-in replication; manual cleanup for stale versions; DuckDB not designed for concurrent writes from multiple processes. |
| **B: ArcticDB** | Man Group's purpose-built DataFrame DB for quant workloads. | Versioned by design; built-in compression; optimized for financial time series; append-only storage; supports concurrent readers. | New dependency (~50MB); learning curve; less community adoption; heavier than needed for Phase 1. |
| **C: PostgreSQL + JSONB** | Store features in PG with JSONB columns, versioned by table. | Already in infra stack; built-in replication; familiar tooling. | Horrible for time-series range scans; JSONB query performance degrades at scale; no columnar compression; wrong tool for the job. |

**Invalidation:** Option B (ArcticDB) is over-engineered for Phase 1 — we can add it in Phase 4 when backtesting needs heavy I/O. Option C fails DD2 (latency) for time-series scans. **Option A wins** — Parquet + DuckDB gives us columnar storage, zero-infrastructure overhead, and SQL analytics, all within a single process. Long-format schema further improves Parquet compression via dictionary encoding on feature_name.

#### D2: TA-Lib vs Native Indicators

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: TA-Lib wrapper + Polars-native where faster (RECOMMENDED)** | Wrapper that converts Polars → numpy → TA-Lib → Polars. Compute-critical indicators (SMA, EMA, RSI, ATR) have Polars-native implementations as drop-in replacements. Shared numpy conversion helpers in `converters.py`. | Full TA-Lib coverage (200+ indicators); Polars-native path for hot indicators is 10-50x faster; gradual migration path; both paths produce the same output verified by tests. | Two implementations to maintain for ~5 indicators; conversion overhead for TA-Lib path (negligible at daily batch scale). |
| **B: Pure TA-Lib** | All indicators via TA-Lib C library. numpy arrays only. | Single code path; battle-tested C library; comprehensive indicator set. | Requires C library install (pain in CI/containers); bottleneck for 500-instrument batch; no streaming support. |
| **C: Pure Polars via `pandas-ta`-like patterns** | Every indicator implemented in Polars expressions. | Zero C dependencies; fully streaming; Polars-native speed. | Massive implementation effort (200+ indicators); testing burden; high regression risk. |

**Invalidation:** Option B locks us into C library dependency with no escape path. Option C is too much work for Phase 1. **Option A wins** — wrappers are thin, hot indicators get native speed, and TA-Lib fills the gaps. Shared numpy helpers in converters.py keep TA-Lib conversion unified.

#### D3: Regime Detection Architecture

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Ensemble pipeline — HMM + BOCD + PELT + Vol Cluster + Corr Matrix + Macro State (RECOMMENDED)** | Six detectors run independently, each publishing a regime signal. The ensemble merges them via weighted voting into a single regime.updated event. | Robust to single-detector failure; each detector covers a different regime dimension (vol, trend, correlation, macro, change point); ensemble output is more stable than any single detector. | Higher compute cost (6 models); parameter tuning required per detector; ensemble weighting needs validation. |
| **B: HMM-only** | Single HMM with 3-4 hidden states for bull/bear/choppy. | Simple; fast; one model to maintain. | Misses volatility regimes, correlation shifts, macro context; HMM assumes Markov property (state depends only on previous state). |
| **C: HMM + Macro overlay** | HMM for technical regime, macro state (GDP/CPI) as regime overlay. | Simpler than full ensemble; macro overlay adds context. | Misses change points, volatility clusters, and correlation shifts entirely. |

**Invalidation:** Option B and Option C miss critical regime dimensions documented in SPEC.md §8 and EVENTS.md §3.5. **Option A wins** — the ensemble approach is documented in SPEC.md, matches the regime.updated event schema, and provides the robustness needed for future autopilot mode.

#### D4: Sentiment NLP Approach

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Local lightweight model + external API fallback (RECOMMENDED)** | FinBERT (local, ~400MB) for news/financial text. External API (e.g., NewsAPI NLP, StockTwits sentiment) for social media. | Fast inference (<100ms/article); no API key required for FinBERT; external API covers social media nuance. | FinBERT is less accurate on social media slang; API costs for high volume; extra dependency (transformers). |
| **B: Full external API** | All sentiment via third-party API. | Zero local compute; no model management; best accuracy for social media. | API costs scale with volume; latency depends on network; vendor lock-in. |
| **C: Local transformer ensemble** | FinBERT + RoBERTa + DistilBERT ensemble. | Maximum accuracy; no external dependencies. | ~3GB model footprint; 5-10x slower than single model; over-engineered for Phase 1. |

**Invalidation:** Option B fails DD2 (latency) and adds operational cost for every request. Option C is over-engineered for Phase 1. **Option A wins** — FinBERT handles the core use case (earnings calls, financial news), while the API fallback provides social media coverage.

#### D5: Polars Migration Strategy

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Coexistence with clean boundaries (RECOMMENDED)** | `analytics/common/converters.py` provides `to_polars()`, `to_pandas()`, `validate_frame()`, and shared TA-Lib numpy helpers. All new code uses Polars by default. | No pandas code modified; clear conversion points; TA-Lib works unchanged; gradual migration path. | Two DataFrame paradigms coexist; developers must learn both APIs. |
| **B: Forklift replacement** | Replace all pandas usage in one pass. | Clean break; single paradigm. | Massive refactor; blocks other Phase 1 work; high risk of regression. |
| **C: Polars-only (no pandas in new code)** | New code is Polars-only; existing pandas code runs untouched. | No conversion overhead; clean separation. | Duplicate utility functions; pandas knowledge doesn't transfer to Polars code. |

**Invalidation:** Option B would consume the entire Phase 1 budget on migration alone. Option C lacks the conversion layer needed for TA-Lib interop. **Option A wins** — clean boundaries, minimal friction, progressive migration. Shared TA-Lib numpy helpers keep the conversion layer unified.

#### D6: AnalyticsSettings Integration (NEW — per F6)

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Extend OracleSettings with AnalyticsSettings (RECOMMENDED)** | `AnalyticsSettings` becomes a top-level field on `OracleSettings`. ConfigLoader loads `config/analytics.yaml` alongside existing config files and merges into `OracleSettings`. | Single config entry point (`OracleSettings`); all Phase 1 settings accessible via `settings.analytics.feature_store_path`; backward compatible with existing config loading. | Adds one more config file; existing config tests need updating. |
| **B: Standalone analytics config** | Analytics code loads its own config file independently, bypassing OracleSettings. | No changes to existing ConfigLoader; fully independent. | Two config systems in same codebase; settings scattered; violates ADR-002 config hierarchy. |
| **C: Environment-only** | All analytics settings via env vars, no YAML config file. | Minimal code; 12-factor compliant. | Unwieldy for 20+ settings; no documentation in YAML; hard to version. |

**Invalidation:** Option B creates a parallel config system (violates ADR-002). Option C is unmanageable at Phase 1 scale. **Option A wins** — single `OracleSettings` entry point, clean YAML config, backward compatible. Requires `config/analytics.yaml` added to ConfigLoader's file list.

### Pre-mortem: 3 Failure Scenarios

#### Scenario 1: "TA-Lib C Library Blocks CI"
TA-Lib requires a C extension compiled against the host system. In CI (GitHub Actions), the `ta-lib` pip install fails because the `ta-lib` system library is missing. Local `make dev` also fails on machines without the C library.
- **Probability:** HIGH (well-known pain point)
- **Impact:** CRITICAL (blocks all indicator computation)
- **Detection:** Fails on first `pip install -e ".[analytics]"` in CI
- **Mitigation:**
  - Document system-level install in README (`apt-get install ta-lib` or `brew install ta-lib`)
  - Docker image bundles the C library
  - CI workflow installs `ta-lib` via apt before pip
  - Polars-native indicator path works WITHOUT TA-Lib (degraded mode)
  - Tests that need TA-Lib are marked `@pytest.mark.ta_lib` and skipped when library absent

#### Scenario 2: "Feature Store Schema Drift Breaks Downstream Consumers"
The Phase 1 Feature Store writes features as **long-format Parquet** with `(instrument_id, timestamp, feature_name, value)` rows. Phase 2's backtesting module reads the same Parquet files. If the schema changes (e.g., adding a `feature_version` column), consumers that don't expect it may fail.
- **Probability:** MEDIUM
- **Impact:** HIGH (silent data corruption)
- **Detection:** Only caught when backtest results look suspicious (too late)
- **Mitigation:**
  - FeatureSetVersion schema is the contract: every feature set has a JSON schema registered before first write
  - Schema evolution tests: write → read round-trip with schema validation
  - Feature Store has a `validate_schema()` method that consumers call on first read
  - Long-format schema is self-describing and additive (new features = new rows, not new columns)
  - Integration test: write a feature set, read it back, assert schema matches
  - Schema evolution policy: additive changes (new feature_names) always backward compatible; breaking changes increment major version

#### Scenario 3: "Regime Detection Ensemble Produces Oscillating Output"
The HMM and BOCD detectors disagree on regime transitions. HMM says "bear" because of 3-day downtrend, while BOCD fires a change point signal. The ensemble oscillates between "bull" and "bear" every few bars, causing the strategy engine to flip positions repeatedly.
- **Probability:** MEDIUM-HIGH (well-known ensemble problem)
- **Impact:** HIGH (whipsaw trades, drawdown)
- **Detection:** Regime oscillation in logs during backtesting
- **Mitigation:**
  - Minimum regime duration: ensemble must see consensus for N bars before emitting a regime change
  - Hysteresis buffer: `regime_updated` event includes a "confidence" score and requires >0.6 to transition
  - Regime change events are rate-limited: max 1 change per 5 bars regardless of ensemble output
  - Backtest includes regime stability as a secondary metric (fewer transitions = better)

---

## 2. Architecture Overview

### How Phase 1 Fits Into the 8-Layer Architecture

```
                    ┌──────────────────────────────────────┐
                    │   LAYER 2: STRATEGY GENERATION        │
                    │   (Phase 2+)                           │
                    └──────────────────────────────────────┘
                               ▲
                               │ feature.updated / regime.updated
                               ▼
┌──────────────────────────────────────────────────────────┐
│              LAYER 1: ANALYTICS ENGINE (Phase 1)         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │              AnalyticsOrchestrator                │    │
│  │  startup ordering · health aggregation · shutdown │    │
│  └──────────────────────────────────────────────────┘    │
│          │ starts & monitors                             │
│          ▼                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │Technical │ │Regime    │ │Fundament │ │Sentiment │    │
│  │Indicators│ │Detection │ │Module    │ │NLP       │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Feature Store (Parquet+DuckDB)       │    │
│  │  LRU cache · concurrency guard · freshness TTL   │    │
│  └──────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Market Ingestion & Normalization         │    │
│  │  Binance WS · yfinance · CoinPaprika · Base ABC  │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
           ▲                               │
           │ market.tick / market.bar       │ data
           ▼                               ▼
┌──────────────────────┐     ┌────────────────────────────┐
│ LAYER 0: DATA INFRA  │     │  External Data Sources     │
│ NATS · QuestDB       │     │  FRED · WB · TradingEc     │
│ Redis · PostgreSQL   │     │  NewsAPI · SEC EDGAR       │
└──────────────────────┘     └────────────────────────────┘
```

### AnalyticsOrchestrator

The `AnalyticsOrchestrator` (`analytics/orchestrator.py`) is the lifecycle manager for all analytics modules (M4-M8):

```
┌─────────────────────────────────────────┐
│           AnalyticsOrchestrator          │
│                                         │
│  1. await feature_store.ready()          │
│  2. for module in modules:               │
│       module.start()                     │
│  3. loop:                                │
│       health = {m: m.health()            │
│                  for m in modules}       │
│       await bus.publish(                 │
│           "system.health", health)       │
│  4. on shutdown:                         │
│       for module in reversed(modules):   │
│           module.stop()                  │
└─────────────────────────────────────────┘
```

**Sequence:**
1. Wait for FeatureStore to signal readiness (`feature_store.ready()` event)
2. Start modules in dependency order: M4 → M5, M6, M7, M8 in parallel
3. Poll health every 10s, publish aggregated health to `system.health`
4. On SIGTERM/SIGINT: stop modules in reverse order, flush Feature Store

**Backpressure Model:**

Each module (M4-M8) uses a bounded `asyncio.Queue` for input events. Configurable per-module settings:

```python
class BackpressureSettings(BaseModel):
    max_queue_size: int = 1000      # max buffered events
    drop_policy: Literal["oldest", "newest", "block"] = "oldest"
    poll_interval_ms: int = 100     # polling interval when queue is empty
```

The drop policy determines behavior when the queue is full:
- `oldest`: discard the oldest pending event (prefer fresh data)
- `newest`: discard the incoming event (preserve processing queue)
- `block`: await space in queue (guaranteed delivery, may block upstream)

Default: `oldest` — analytics should always work on the newest data.

### UTC Enforcement (Architect Rec #8)

All new Phase 1 models use `datetime` fields that are:
- Timezone-aware (`datetime.now(timezone.utc)` not `datetime.now()`)
- Validated at construction via Pydantic's `datetime` type with `utc` constraint
- Serialized as ISO-8601 with `Z` suffix in NATS events
- Never converted to local time within analytics code

A shared base class `UTCModel(BaseModel)` is provided in `analytics/common/models.py`:
```python
class UTCModel(BaseModel):
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})

    @field_validator("*", mode="before")
    @classmethod
    def ensure_utc(cls, v, info):
        if isinstance(v, datetime) and v.tzinfo is None:
            raise ValueError(f"{info.field_name} must be timezone-aware UTC")
        if isinstance(v, datetime):
            return v.astimezone(timezone.utc)
        return v
```

### Data Flow: Market Data → Ingestion → Analytics → Feature Store → Events

```
External Source (Binance WS / yfinance / CoinPaprika)
    │
    ▼
┌──────────────────────────────────────────┐
│ market/ingestion/                         │
│  • WebSocket connector (Binance)         │
│  • REST poller (yfinance, CoinPaprika)   │
│  • Normalizer (Tick → MarketTickEvent)    │
│  • Bar aggregator (Tick → 1m/5m/1h bars) │
│  • NATS publisher                         │
└────────────────┬─────────────────────────┘
                 │ event: market.tick / market.bar
                 ▼
┌──────────────────────────────────────────┐
│ analytics/technical/                      │
│  • TA-Lib wrapper (Polars → numpy → TA)  │
│  • Polars-native hot indicators           │
│  • Candlestick pattern detector           │
│  • Subscribes to market.bar               │
│  • Publishes feature.updated via NATS     │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ analytics/regime/                         │
│  • HMM detector (hmmlearn)               │
│  • BOCD detector (custom/ruptures)       │
│  • PELT detector (ruptures)              │
│  • Vol Cluster (sklearn KMeans)          │
│  • Corr Matrix (rolling pairwise)        │
│  • Macro State (from FRED/World Bank)    │
│  • Ensemble voter (weighted consensus)   │
│  • Publishes regime.updated              │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ analytics/fundamental/                    │
│  • Financial statements parser           │
│  • Ratio calculator (P/E, P/B, ROE)     │
│  • DCF valuation                         │
│  • Publishes feature.updated             │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ analytics/sentiment/                      │
│  • News processor (FinBERT)              │
│  • Social media sentiment                │
│  • Earnings call sentiment               │
│  • Publishes feature.updated             │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ market/store/ (Feature Store)             │
│  • Versioned Parquet store (long-format) │
│  • LRU cache for hot feature sets        │
│  • Per-feature-set asyncio write lock    │
│  • Freshness/staleness TTL tracking      │
│  • DuckDB query interface                │
│  • Schema validation on write            │
└──────────────────────────────────────────┘
```

### Polars/Pandas Coexistence Strategy

```
                    ┌──────────────────────────────────┐
                    │        analytics/common/          │
                    │   converters.py · validators.py   │
                    │   talib_helpers.py · models.py    │
                    └──────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Polars-native   │  │  TA-Lib wrapper  │  │  Shared numpy    │
│  (default path)  │──│  (via numpy)     │──│  helpers          │
│                  │  │                  │  │  (converters.py)  │
│  SMA, EMA, RSI   │  │  All 200+ TA-Lib│  │                  │
│  ATR, BB, MACD   │  │  indicators     │  │  to_numpy_2d()   │
│  Volume profile  │  │  via thin conv  │  │  from_numpy()    │
└──────────────────┘  └──────────────────┘  │  validate_numpy()│
                                             └──────────────────┘
```

**Rules:**
1. All new analytics code imports `import polars as pl` by default
2. TA-Lib wrapper converts Pl → np → TA → Pl: `ta_lib_sma(pl.Series) → pl.Series`
3. `analytics/common/converters.py` has `to_polars()`, `to_pandas()`, `ensure_frame()` — exported, tested
4. `analytics/common/converters.py` also provides shared TA-Lib helpers: `to_numpy_2d(pl.Series) → np.ndarray`, `from_numpy(data, index) → pl.Series`, `validate_numpy(arr, min_length)` — ensures NaN/Inf handling consistent across all TA-Lib callers
5. No `import pandas as pd` in new code under `analytics/` or `market/`
6. Existing `core/domain/` and `core/events/` continue using pydantic+dict (no DataFrame needed)
7. `pyproject.toml` adds `polars>=1.0` as core dependency; `pandas` stays for numpy compat
8. **All new models extend `UTCModel`** for timezone-aware UTC datetime enforcement

### Feature Store Schema: Long Format

The Feature Store uses **long-format** (normalized) rows instead of wide-format columns:

```
┌──────────────────────────────────────────────────┐
│  Feature Store Parquet Schema (long format)       │
├──────────────────────────────────────────────────┤
│  instrument_id: str     # Partition key           │
│  timestamp: datetime    # Partition key (date)    │
│  feature_set: str       # "technical_v2"          │
│  feature_name: str      # "sma_20", "rsi_14"      │
│  value: float           # The computed value      │
│  version: str           # FeatureSetVersion       │
│  updated_at: datetime   # When written            │
└──────────────────────────────────────────────────┘
```

**Benefits over wide-format:**
1. **Better Parquet compression**: dictionary encoding on `feature_name` column (typically <50 unique features per set) compresses extremely well
2. **Schema evolution**: adding a new feature means inserting rows with a new `feature_name` — no schema migration, no column addition
3. **Natural DuckDB SQL**: `SELECT * WHERE feature_name = 'sma_20'` works natively; window functions partition by `feature_name`
4. **Sparse data**: if only 30 of 50 features compute for a given instrument, no NULL columns — only the computed rows exist
5. **Cross-feature-set joins**: `WHERE feature_set = 'technical_v2'` cleanly merges with `feature_set = 'regime_v1'`

### Milestone Dependency Graph (Revised per F4)

```
M1: Foundation (DuckDB eval + Polars migration + common utils + Orchestrator)
│
├──► M2: Market Ingestion (Binance WS · yfinance · CoinPaprika · normalizer · NATS pub)
│    │
│    └──► M3: Feature Store (Parquet long-format, version tracking, LRU cache, locks, freshness)
│         │
│         ├──► M4: Technical Indicators (TA-Lib + Polars-native + patterns)
│         │    │
│         │    └──► M5: Regime Detection (HMM + BOCD + PELT + VolCluster + Corr + Macro)
│         │
│         ├──► M6: Fundamental Module (statements, ratios, DCF)        ╮
│         ├──► M7: Sentiment NLP (FinBERT, news, social, earnings)    ─┤  Parallel to M4
│         └──► M8: Macro Connector (FRED, World Bank, TradingEconomics)╯
│              │
│              └──► M9: Integration & Wiring (end-to-end, benchmarks, experiments)
```

**Key dependencies:**
- M1 → M2 → M3 is strictly sequential (foundation → data sources → storage)
- M4, M6, M7, M8 all depend on M3 (Feature Store) but are **independent of each other**
- M5 (Regime) depends on M4 (Technical indicators) — Regime reads technical features from Feature Store
- M4 → M5 is a sequential sub-pipeline within the parallel block
- M9 wraps everything: orchestrator starts M4-M8, runs E2E, benchmarks
- **Revised from v1:** M6/M7/M8 are NOT downstream of M4 — they run in parallel. Only M5 gates on M4.

---

## 3. Implementation Milestones

### M1: Foundation Layer — DuckDB Evaluation + Polars Migration + Common Utilities + Orchestrator

**Goal:** Establish the shared infrastructure for all analytics modules. Polars becomes the default DataFrame. DuckDB is evaluated for offline queries on Parquet. AnalyticsOrchestrator provides lifecycle management.

**Files to create:**
- `analytics/__init__.py` — update with exports
- `analytics/common/__init__.py` — module init
- `analytics/common/converters.py` — `to_polars()`, `to_pandas()`, `ensure_frame()`, `to_numpy_2d()`, `from_numpy()`, `validate_numpy()`
- `analytics/common/schema.py` — `validate_schema()`, `FeatureSchema`, schema registry
- `analytics/common/models.py` — `UTCModel` base class with UTC datetime validation
- `analytics/common/config.py` — `AnalyticsSettings(BaseModel)` for Phase 1 config
- `analytics/common/errors.py` — `AnalyticsError`, `IndicatorError`, `RegimeError` extending `OracleError`
- `analytics/common/__tests__/` — test directory
- `analytics/orchestrator.py` — `AnalyticsOrchestrator` lifecycle manager
- `docs/ANALYTICS.md` — module documentation

**Key APIs:**

```python
# analytics/common/converters.py
def to_polars(df: pd.DataFrame | pl.DataFrame | pl.LazyFrame) -> pl.DataFrame: ...
def to_pandas(df: pl.DataFrame | pl.LazyFrame) -> pd.DataFrame: ...
def ensure_frame(data: pl.Series | pl.DataFrame) -> pl.DataFrame: ...
def to_numpy_2d(series: pl.Series) -> np.ndarray: ...
def from_numpy(data: np.ndarray, index: pl.Series | None = None) -> pl.Series: ...
def validate_numpy(arr: np.ndarray, min_length: int = 1) -> np.ndarray:
    """Validate numpy array for NaN/Inf, ensure minimum length. Raises IndicatorError."""

# analytics/common/schema.py
class FeatureSchema(BaseModel):
    name: str
    dtype: str  # "float64", "int64", "str", etc.
    nullable: bool = True
    description: str = ""
    valid_range: tuple[float | None, float | None] | None = None

def validate_schema(df: pl.DataFrame, schema: list[FeatureSchema]) -> list[str]:
    """Returns list of schema violations (empty = valid)."""

# analytics/common/models.py
class UTCModel(BaseModel):
    """Base model enforcing timezone-aware UTC datetimes."""
    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat()},
        arbitrary_types_allowed=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def ensure_utc(cls, v, info):
        if isinstance(v, datetime) and v.tzinfo is None:
            raise ValueError(f"{info.field_name} must be timezone-aware UTC")
        if isinstance(v, datetime):
            return v.astimezone(timezone.utc)
        return v

# analytics/common/config.py
class BackpressureSettings(BaseModel):
    """Bounded queue backpressure for analytics modules."""
    max_queue_size: int = 1000
    drop_policy: Literal["oldest", "newest", "block"] = "oldest"
    poll_interval_ms: int = 100

class AnalyticsSettings(BaseModel):
    """Configuration for analytics engine."""
    indicator_batch_size: int = 100  # instruments per batch
    regime_lookback_bars: int = 500
    regime_ensemble_min_confidence: float = 0.6
    feature_store_path: str = "data/features"
    backpressure: BackpressureSettings = BackpressureSettings()
    feature_cache_ttl_seconds: int = 300       # LRU cache TTL (Architect Rec #3)
    feature_freshness_max_age_seconds: int = 600  # staleness threshold (Architect Rec #7)
    utc_enforced: bool = True                    # UTC validation toggle (Architect Rec #8)

# analytics/orchestrator.py
class AnalyticsModule(ABC):
    """Interface each analytics module implements for lifecycle management."""
    name: ClassVar[str]

    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

class AnalyticsOrchestrator:
    """Manages startup ordering, health aggregation, and graceful shutdown of M4-M8."""

    def __init__(self, bus: EventBusClient, store: FeatureStore): ...

    async def start_all(self) -> None:
        """1. Wait for FeatureStore ready
        2. Start M4 (Technical) → M5 (Regime) sequentially
        3. Start M6 (Fundamental), M7 (Sentiment), M8 (Macro) in parallel
        4. Begin health polling loop
        """

    async def shutdown(self) -> None:
        """Graceful shutdown: stop modules in reverse dependency order, flush store."""

    async def health_check(self) -> dict[str, dict[str, Any]]:
        """Aggregate health from all modules, publish to system.health."""
```

**AnalyticsSettings Integration with OracleSettings (per F6):**

New ADR-xxx documents the integration path:
- `AnalyticsSettings` is added as a top-level field on `OracleSettings`
- `ConfigLoader` is extended to load `config/analytics.yaml` (if present) alongside existing config files
- Settings merge order: defaults → `config/analytics.yaml` → environment overrides
- All Phase 1 modules access config via `settings.analytics.<field>`
- Backward compatible: existing projects without `config/analytics.yaml` get defaults

```yaml
# config/analytics.yaml
analytics:
  feature_store_path: "data/features"
  regime_lookback_bars: 500
  regime_ensemble_min_confidence: 0.6
  indicator_batch_size: 100
  backpressure:
    max_queue_size: 1000
    drop_policy: "oldest"
    poll_interval_ms: 100
  feature_cache_ttl_seconds: 300
  feature_freshness_max_age_seconds: 600
  utc_enforced: true
```

**DuckDB Evaluation Task:**
- Install `duckdb` in virtual env
- Write benchmark notebook/script: `analytics/duckdb_eval.py`
- Test queries against 100MB Parquet dataset:
  - Time-series range scan (1M rows, 10 columns)
  - Aggregation (mean, std, group by instrument)
  - JOIN between two feature sets
  - Window functions (rolling 20-bar SMA via DuckDB SQL)
- Produce `docs/DUCKDB_EVAL.md` with results and recommendation

**Test Strategy:**
- Unit tests for each converter function (round-trip, edge cases, NaN handling)
- Unit tests for shared TA-Lib numpy helpers (NaN boundary, min_length validation)
- Schema validation tests (valid, invalid, empty DataFrame)
- Config loading from YAML/env
- Orchestrator tests: startup order, health aggregation, shutdown sequence
- UTC model tests: naive datetime rejected, tz-aware converted to UTC
- DuckDB eval is a standalone script, not a test — results documented in `docs/DUCKDB_EVAL.md`

**Acceptance Criteria:**
- `to_polars(pd.DataFrame)` returns correct `pl.DataFrame` with schema preserved
- `to_pandas(pl.DataFrame)` round-trips correctly (with NaN handling)
- `ensure_frame(pl.Series)` wraps into DataFrame with default name
- `validate_schema()` catches nullable violations, type mismatches, missing columns
- `AnalyticsSettings` loads from `config/analytics.yaml` via OracleSettings
- `AnalyticsOrchestrator` starts M4 before M5, runs M6/M7/M8 in parallel, reports health
- `UTCModel.ensure_utc` raises on naive datetime, converts tz-aware to UTC
- DuckDB eval produces documented performance numbers
- All tests pass: `make test-unit`
- ruff + mypy pass on `analytics/common/`

### M2: Market Ingestion — Concrete Data Connectors + Normalizer + NATS Publisher

**Goal:** Create the data ingestion pipeline that converts raw market data from external sources into normalized NATS events. **Concrete implementations ship with the ABC — Binance WebSocket, yfinance REST, and CoinPaprika REST.**

**Files to create:**
- `market/ingestion/__init__.py` — module init
- `market/ingestion/base.py` — `DataSource(ABC)`, `WebSocketSource(ABC)`, `RESTPoller(ABC)`
- `market/ingestion/connectors/binance.py` — `BinanceWebSocketSource` (crypto, real-time, free, no API key)
- `market/ingestion/connectors/yfinance.py` — `YFinanceConnector` (US equities EOD, free)
- `market/ingestion/connectors/coinpaprika.py` — `CoinPaprikaConnector` (7000+ coins, REST backup, free)
- `market/ingestion/config.py` — `IngestionSettings` (instruments list, sources config)
- `market/ingestion/errors.py` — `IngestionError`, `SourceDisconnectedError`, `NormalizationError`
- `market/normalizer/__init__.py` — module init
- `market/normalizer/tick.py` — `normalize_tick(raw: dict) -> MarketTickEvent`
- `market/normalizer/bar.py` — `normalize_bar(raw: dict) -> MarketBarEvent`
- `market/normalizer/publisher.py` — NATS publisher for normalized events
- `market/store/__init__.py` — module init (stub: Phase 4 QuestDB integration)
- `tests/unit/market/test_ingestion.py`
- `tests/unit/market/test_normalizer.py`

**Key APIs:**

```python
# market/ingestion/base.py
class DataSource(ABC):
    """Base class for all data sources."""
    name: ClassVar[str]
    instruments: list[str]
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...

class WebSocketSource(DataSource):
    """Base for WebSocket data sources with auto-reconnect."""
    ws_url: str
    _ws: WebSocket | None = None
    async def _on_message(self, raw: dict) -> None: ...
    async def _reconnect(self) -> None: ...

class RESTPoller(DataSource):
    """Base for REST-polled data sources with configurable interval."""
    poll_interval_seconds: int = 60
    async def _fetch(self) -> dict[str, Any]: ...
    async def _poll_loop(self) -> None: ...

# market/ingestion/connectors/binance.py
class BinanceWebSocketSource(WebSocketSource):
    """Real-time crypto data via Binance WebSocket.
    - No API key required
    - Streams: <symbol>@trade, <symbol>@kline_1m
    - Auto-reconnect with exponential backoff
    """
    name = "binance"
    ws_url = "wss://stream.binance.com:9443/ws"
    instruments: list[str]  # e.g., ["btcusdt", "ethusdt"]

    async def _subscribe(self) -> None:
        """Send SUBSCRIBE message with instrument streams."""

# market/ingestion/connectors/yfinance.py
class YFinanceConnector(RESTPoller):
    """US equities EOD data via yfinance.
    - Free, no API key
    - Supports: history, dividends, splits
    - Returns Polars DataFrame of daily bars
    """
    name = "yfinance"
    poll_interval_seconds = 86400  # once per day for EOD

    async def fetch_history(self, symbol: str, period: str = "1mo") -> pl.DataFrame: ...

# market/ingestion/connectors/coinpaprika.py
class CoinPaprikaConnector(RESTPoller):
    """CoinPaprika REST API for crypto market data.
    - 7000+ coins
    - Free, no API key
    - Rate limit: 10 req/min (free tier)
    """
    name = "coinpaprika"

    async def fetch_ticker(self, coin_id: str) -> dict[str, Any]: ...

# market/normalizer/publisher.py
class MarketEventPublisher:
    """Publishes normalized market events to NATS."""
    def __init__(self, bus: EventBusClient): ...
    async def publish_tick(self, tick: MarketTickEvent) -> None: ...
    async def publish_bar(self, bar: MarketBarEvent) -> None: ...
    async def start_stream(self, source: DataSource) -> None:
        """Connect source, normalize, and publish continuously."""
```

**Test Strategy:**
- Unit tests: `normalize_tick()` with valid/invalid/missing fields
- Unit tests: normalizer rejects prices <= 0, negative volumes, missing instrument_id
- Unit tests: `WebSocketSource` auto-reconnect logic (mock WebSocket)
- Unit tests: concrete connectors with mock HTTP responses (Binance WS frame, yfinance CSV, CoinPaprika JSON)
- Unit tests: `MarketEventPublisher` publishes correct events (mock NATS)
- Integration tests (Docker NATS): end-to-end pub/sub round-trip

**Acceptance Criteria:**
- `normalize_tick()` produces a valid `MarketTickEvent` from a raw dict
- `normalize_bar()` produces a valid `MarketBarEvent` with correct OHLC validation
- Invalid raw data raises `NormalizationError` (not `AttributeError` or `KeyError`)
- `BinanceWebSocketSource` connects, subscribes, and processes real trade messages (unit test with mock frames)
- `YFinanceConnector.fetch_history("AAPL", "5d")` returns valid `pl.DataFrame` with OHLCV columns
- `CoinPaprikaConnector.fetch_ticker("btc-bitcoin")` returns valid ticker data
- `WebSocketSource` reconnects after simulated disconnect
- `MarketEventPublisher` publishes to correct NATS subject
- Integration test: publish → subscribe → assert event envelope matches EVENTS.md
- All tests pass; ruff + mypy pass

### M3: Feature Store — Versioned Parquet Long-Format Store + Concurrency Guard + LRU Cache + Freshness Tracking + DuckDB Query Interface

**Goal:** Implement the versioned feature store that is the single source of truth for all computed analytics. Features are stored in **long format** (feature_name, value), written once, versioned via FeatureSetVersion, guarded by per-feature-set write locks, cached with LRU, monitored for freshness, and queryable via DuckDB.

**Files to create:**
- `market/store/feature_store.py` — `FeatureStore` main class
- `market/store/parquet_backend.py` — Parquet read/write with long-format schema
- `market/store/duckdb_backend.py` — DuckDB query wrapper
- `market/store/cache.py` — `FeatureLRUCache` (in-memory, size-bounded, TTL-aware)
- `market/store/errors.py` — `StoreError`, `SchemaVersionError`, `FeatureNotFoundError`
- `market/store/config.py` — `FeatureStoreSettings`
- `tests/unit/market/test_feature_store.py`
- `tests/integration/test_feature_store.py`

**Key APIs:**

```python
# market/store/feature_store.py
class FeatureStore:
    """Versioned, parquet-backed feature store with concurrency guard and LRU cache.

    Parquet schema (long format):
        instrument_id: str     # Partition key
        timestamp: datetime    # Partition key (date)
        feature_set: str       # e.g., "technical_v2"
        feature_name: str      # e.g., "sma_20", "rsi_14"
        value: float           # Computed feature value
        version: str           # FeatureSetVersion
        updated_at: datetime   # When this row was written

    Directory structure:
        data/features/
            v1/
                technical_v2/
                    instrument=SPY/
                        date=2026-07-09/
                            data.parquet
                regime_v1/
                    instrument=SPY/
                        ...
            v2/ ...
    """

    def __init__(self, settings: FeatureStoreSettings):
        self._write_locks: dict[str, asyncio.Lock] = {}  # per-feature-set lock
        self._cache = FeatureLRUCache(max_size=1000, ttl=settings.cache_ttl_seconds)
        self._freshness: dict[str, datetime] = {}  # last write time per (feature_set, instrument)

    async def write_features(
        self,
        feature_set: str,
        version: str,
        df: pl.DataFrame,
        instrument_id: str,
    ) -> FeatureSetVersion:
        """Write feature DataFrame with schema validation.

        Expects long-format DataFrame with columns:
            [timestamp, feature_name, value, version, updated_at]

        Per-feature-set asyncio lock prevents concurrent writes.
        Updates LRU cache and freshness tracker.

        Raises StoreError if schema validation fails.
        """
        async with self._get_write_lock(feature_set):
            self._validate_long_format(df, feature_set, version)
            path = self._partition_path(feature_set, version, instrument_id)
            df.write_parquet(path, partition_cols=["instrument_id", "date"])
            self._cache.put(f"{feature_set}:{instrument_id}", df)
            self._freshness[f"{feature_set}:{instrument_id}"] = datetime.now(timezone.utc)
            return FeatureSetVersion(...)

    async def read_features(
        self,
        feature_set: str,
        version: str | None = None,
        instrument_ids: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        feature_names: list[str] | None = None,  # filter by feature
    ) -> pl.DataFrame:
        """Read features via DuckDB SQL on Parquet files.

        1. Check LRU cache for hot feature sets
        2. Falls through to DuckDB on cache miss
        3. Supports filtering by feature name for efficient long-format queries
        Version=None reads latest version.
        """

    def get_versions(self, feature_set: str) -> list[FeatureSetVersion]: ...

    def validate_schema(
        self, feature_set: str, version: str, schema: list[FeatureSchema]
    ) -> list[str]:
        """Validate stored data against expected schema."""

    def get_freshness(self, feature_set: str, instrument_id: str) -> datetime | None:
        """Return last write time for (feature_set, instrument). None if never written."""

    def is_stale(self, feature_set: str, instrument_id: str, max_age_seconds: int) -> bool:
        """True if last write time exceeds max_age_seconds from now."""

    def _get_write_lock(self, feature_set: str) -> asyncio.Lock:
        """Get or create per-feature-set asyncio write lock.

        Cross-feature-set safety: writes to different feature sets
        (e.g., technical_v2 and regime_v1) proceed concurrently.
        Only writes to the same feature set serialize.
        """

# market/store/cache.py
class FeatureLRUCache:
    """In-memory LRU cache for hot feature set reads.

    Bounded by max_size items and per-item TTL.
    Thread-safe for concurrent access.
    """
    def __init__(self, max_size: int = 1000, ttl: int = 300): ...
    def get(self, key: str) -> pl.DataFrame | None: ...
    def put(self, key: str, df: pl.DataFrame) -> None: ...
    def invalidate(self, key: str) -> None: ...
    def invalidate_feature_set(self, feature_set: str) -> None: ...

# market/store/duckdb_backend.py
class DuckDBQuery:
    """Embedded DuckDB for analytical SQL on Parquet features."""
    def __init__(self, feature_store_path: Path): ...
    def sql(self, query: str) -> pl.DataFrame: ...
    def register_views(self, feature_sets: dict[str, FeatureSetVersion]) -> None: ...
```

**Test Strategy:**
- Unit tests: write → read round-trip for single instrument (long format)
- Unit tests: version tracking (write v1, v2, read latest)
- Unit tests: per-feature-set write lock (concurrent writes to same set serialize)
- Unit tests: schema validation on write (reject missing columns, wrong dtypes)
- Unit tests: LRU cache hit/miss/eviction (cache returns correct rows, TTL expiry)
- Unit tests: freshness tracking (get_freshness returns correct timestamp, is_stale works)
- Unit tests: feature filtering in read (read_features with feature_names list)
- Integration tests: write 1000 instruments x 50 features, read back via DuckDB SQL
- Data quality tests: null count, NaN fraction, value range per feature_name
- Performance benchmark: write 100K rows, time the query

**Acceptance Criteria:**
- Feature Store write → read round-trips with identical schema (long format)
- Versioning works: v1 and v2 coexist, latest returns v2 by default
- Concurrent writes to different feature sets complete in parallel
- Concurrent writes to the same feature set are serialized (proven by test)
- Schema validation rejects invalid data before write (not on read)
- LRU cache returns data on hit, queries DuckDB on miss
- Freshness: `is_stale` correctly identifies features older than max_age_seconds
- DuckDB SQL query on Parquet files returns correct results (long format)
- Partition pruning works: query for SPY doesn't scan BTC data
- Write throughput > 10K rows/second (single process)
- Read latency < 100ms for 1M rows (long format)
- All tests pass; ruff + mypy pass

### M4: Technical Indicators — TA-Lib Wrapper + Polars-Native + Candlestick Patterns

**Goal:** Implement the technical indicator computation module with dual-path architecture (TA-Lib + Polars-native for hot indicators). Includes backpressure on the event input queue.

**Files to create:**
- `analytics/__init__.py` — update
- `analytics/technical/__init__.py` — module init
- `analytics/technical/talib_wrapper.py` — `ta_sma()`, `ta_ema()`, `ta_rsi()`, `ta_macd()`, `ta_bbands()`, `ta_atr()`, `ta_volatility()` — uses shared numpy helpers from `converters.py`
- `analytics/technical/overlap.py` — Polars-native: SMA, EMA, WMA, HMA, VWAP
- `analytics/technical/momentum.py` — Polars-native: RSI, MACD, Stochastic, Williams %R, ROC
- `analytics/technical/volatility.py` — Polars-native: ATR, Bollinger Bands, Keltner, Donchian
- `analytics/technical/volume.py` — Polars-native: Volume SMA, OBV, MFI, ADL, Volume Profile
- `analytics/technical/candlestick.py` — Candlestick pattern detection (TA-Lib-based)
- `analytics/technical/statistical.py` — Polars-native: rolling Pearson/Spearman, Z-score, Beta
- `analytics/technical/compute.py` — `IndicatorComputer` with batch processing, NATS subscription to market.bar, bounded queue for backpressure
- `analytics/technical/config.py` — `TechnicalSettings(BackpressureSettings)`
- `tests/unit/analytics/test_talib_wrapper.py`
- `tests/unit/analytics/test_overlap.py`
- `tests/unit/analytics/test_momentum.py`
- `tests/unit/analytics/test_volatility.py`
- `tests/unit/analytics/test_volume.py`
- `tests/unit/analytics/test_candlestick.py`
- `tests/unit/analytics/test_compute.py`
- `tests/unit/analytics/test_statistical.py`

**Key APIs:**

```python
# analytics/technical/talib_wrapper.py
# Uses shared numpy helpers from analytics.common.converters:
#   to_numpy_2d(series) -> np.ndarray
#   from_numpy(data, index) -> pl.Series
#   validate_numpy(arr, min_length) -> np.ndarray

@overload
def ta_sma(series: pl.Series, period: int = 20) -> pl.Series: ...
@overload
def ta_sma(df: pl.DataFrame, column: str, period: int = 20) -> pl.Series: ...

def ta_rsi(series: pl.Series, period: int = 14) -> pl.Series: ...
def ta_macd(close: pl.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, pl.Series]: ...
def ta_bbands(close: pl.Series, period: int = 20, std: int = 2) -> dict[str, pl.Series]: ...

# analytics/technical/compute.py
class IndicatorComputer(AnalyticsModule):
    """Subscribes to market.bar, computes indicators, publishes feature.updated.

    Backpressure: bounded asyncio.Queue with configurable drop policy.
    """

    name = "technical"

    def __init__(self, bus: EventBusClient, store: FeatureStore,
                 settings: TechnicalSettings): ...

    async def start(self) -> None:
        """Subscribe to market.bar, begin processing loop."""

    async def stop(self) -> None:
        """Unsubscribe, flush pending events."""

    async def health(self) -> dict[str, Any]:
        """Return queue depth, events processed, last computation time."""

    async def on_bar(self, event: MarketBarEvent) -> None:
        """Queue bar event (respects backpressure drop policy)."""

    async def compute_all(
        self, bars: pl.DataFrame, indicators: list[str]
    ) -> pl.DataFrame:
        """Batch compute multiple indicators on multi-instrument DataFrame."""

# Candlestick patterns
def detect_patterns(df: pl.DataFrame) -> dict[str, list[str]]:
    """Return {instrument_id: [pattern_name, ...]} for detected patterns.
    Uses TA-Lib CDL* functions internally.
    """

# analytics/technical/config.py
class TechnicalSettings(BackpressureSettings):
    """Technical indicator settings with inherited backpressure."""
    pass
```

**Test Strategy:**
- Unit tests: each TA-Lib wrapper function with known input → known output (compare to TA-Lib docs)
- Unit tests: each Polars-native function compared to TA-Lib output (same input → same output within tolerance)
- Unit tests: edge cases (empty Series, constant Series, NaN inputs, single-bar DataFrames)
- Unit tests: candlestick patterns on known patterns (doji, hammer, engulfing)
- Unit tests: backpressure queue behavior (drop oldest when full)
- Integration tests: `IndicatorComputer` processes a real `market.bar` event and writes to Feature Store
- Performance benchmarks: 500 instruments × 50 indicators, measure wall-clock time

**Acceptance Criteria:**
- All TA-Lib wrappers produce output matching TA-Lib reference (within 1e-8)
- Polars-native SMA/EMA/RSI/MACD/BB/ATR match TA-Lib output within 1e-8
- Candlestick detection correctly identifies doji, hammer, engulfing, harami
- `ta_sma()` with `pl.Series` input and `pl.DataFrame` input both work
- `IndicatorComputer.on_bar()` correctly publishes `feature.updated` via NATS
- Backpressure: queue at max capacity drops oldest event
- Edge cases: constant series → constant indicator result (not NaN or error)
- Batch compute: 500 instruments × 50 indicators in <10s
- All tests pass; ruff + mypy pass on `analytics/technical/`

### M5: Regime Detection Ensemble — HMM + BOCD + PELT + Vol Cluster + Corr Matrix + Macro State

**Goal:** Implement the six-detector regime detection ensemble that produces a unified `regime.updated` event. Depends on M4 technical features from Feature Store. Includes backpressure on input queue.

**Files to create:**
- `analytics/regime/__init__.py` — module init
- `analytics/regime/detectors/base.py` — `BaseRegimeDetector(ABC)` with `fit()`, `predict()`, `name`
- `analytics/regime/detectors/hmm.py` — `HMMRegimeDetector` (hmmlearn GaussianHMM, 3-4 states)
- `analytics/regime/detectors/bocd.py` — `BOCDRegimeDetector` (Bayesian Online Changepoint Detection)
- `analytics/regime/detectors/pelt.py` — `PELTRegimeDetector` (ruptures PELT, cost="rbf")
- `analytics/regime/detectors/vol_cluster.py` — `VolatilityClusterDetector` (KMeans on rolling vol)
- `analytics/regime/detectors/corr_matrix.py` — `CorrelationRegimeDetector` (rolling pairwise correlation)
- `analytics/regime/detectors/macro_state.py` — `MacroStateDetector` (macro data → regime state)
- `analytics/regime/ensemble.py` — `RegimeEnsemble` (weighted voting, min confidence, hysteresis)
- `analytics/regime/publisher.py` — `RegimePublisher` (subscribes to feature.updated, runs ensemble, publishes regime.updated, bounded queue)
- `analytics/regime/config.py` — `RegimeSettings(BackpressureSettings)`
- `analytics/regime/errors.py` — `RegimeError`
- `tests/unit/analytics/test_regime_detectors.py`
- `tests/unit/analytics/test_regime_ensemble.py`
- `tests/unit/analytics/test_regime_publisher.py`

**Key APIs:**

```python
# analytics/regime/detectors/base.py
class BaseRegimeDetector(ABC):
    name: ClassVar[str]
    requires_fit: bool = True
    min_samples: int = 100

    @abstractmethod
    def fit(self, data: pl.DataFrame) -> None: ...
    @abstractmethod
    def predict(self, data: pl.DataFrame) -> dict[str, Any]: ...

# analytics/regime/detectors/hmm.py
class HMMRegimeDetector(BaseRegimeDetector):
    """Gaussian HMM with 3-4 hidden states on returns + vol features."""
    n_states: int = 4
    covariance_type: str = "full"

    def fit(self, features: pl.DataFrame) -> None:
        """Fit HMM on [returns, volatility, volume_change]."""
    def predict(self, features: pl.DataFrame) -> dict[str, Any]:
        """Return {regime: state_idx, probabilities: [p0, p1, p2, p3]}."""

# analytics/regime/ensemble.py
class RegimeEnsemble:
    """Weighted ensemble of regime detectors with hysteresis.

    Configuration:
        weights: dict[name, float] — detector weights (sum to 1)
        min_confidence: float = 0.6 — minimum ensemble confidence to emit
        min_regime_duration: int = 5 — minimum bars before regime change
    """

    def __init__(self, detectors: list[BaseRegimeDetector], config: RegimeSettings): ...
    async def analyze(self, features: pl.DataFrame) -> RegimeUpdatedEvent | None:
        """Run all detectors, merge via weighted voting, apply hysteresis.
        Returns None if confidence < min_confidence (no regime change).
        """

# analytics/regime/publisher.py
class RegimePublisher(AnalyticsModule):
    """Subscribes to feature.updated, runs ensemble, publishes regime.updated."""
    name = "regime"

    def __init__(self, bus: EventBusClient, ensemble: RegimeEnsemble,
                 settings: RegimeSettings): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...
    async def on_feature_updated(self, event: FeatureUpdatedEvent) -> None: ...
```

**Test Strategy:**
- Unit tests: HMM detector on synthetic data (known bull/bear regimes with 5% noise)
- Unit tests: BOCD detects change point at known index
- Unit tests: PELT detects change points with known cost model
- Unit tests: VolCluster correctly separates low/medium/high volatility
- Unit tests: CorrMatrix correctly identifies risk-on vs risk-off
- Unit tests: Ensemble produces stable output (no oscillation on near-identical data)
- Unit tests: Hysteresis buffer prevents regime flips within min_regime_duration
- Unit tests: Empty/insufficient data → graceful return (not crash)
- Integration tests: RegimePublisher end-to-end with real NATS

**Acceptance Criteria:**
- HMM detector correctly identifies bull/bear regimes on synthetic data with >80% accuracy
- BOCD detects change point within 5 bars of actual change point
- PELT matches BOCD on known single-change-point dataset
- VolCluster produces consistent cluster assignments (deterministic with fixed seed)
- Ensemble with 0.6 min confidence requires majority agreement
- Hysteresis buffer: regime change emitted at most every 5 bars
- Insufficient data (< min_samples) returns None (no crash, no event)
- All tests pass; ruff + mypy pass

### M6: Fundamental Module — Financial Statements Parser + Ratios + DCF

**Goal:** Implement fundamental analysis for equities: parse financial statements, compute ratios, and run DCF valuation. Uses **edgartools** (SEC EDGAR, has MCP server) as primary data source. Runs in parallel with M4 (no dependency on technical indicators).

**Files to create:**
- `analytics/fundamental/__init__.py` — module init
- `analytics/fundamental/statements.py` — `FinancialStatements` model + parser (SEC EDGAR XBRL via edgartools)
- `analytics/fundamental/ratios.py` — ratio computation:
  - Profitability: ROE, ROA, Gross Margin, Net Margin
  - Valuation: P/E, P/B, P/S, EV/EBITDA, Dividend Yield
  - Liquidity: Current Ratio, Quick Ratio
  - Leverage: Debt-to-Equity, Interest Coverage
  - Efficiency: Asset Turnover, Inventory Turnover
- `analytics/fundamental/dcf.py` — `DCFValuation` model with configurable assumptions
- `analytics/fundamental/pipeline.py` — `FundamentalPipeline(AnalyticsModule)` — orchestrates data fetch → compute ratios → publish feature.updated; bounded queue for backpressure
- `analytics/fundamental/config.py` — `FundamentalSettings(BackpressureSettings)`
- `analytics/fundamental/errors.py` — `FundamentalError`
- `tests/unit/analytics/test_fundamental_ratios.py`
- `tests/unit/analytics/test_fundamental_dcf.py`
- `tests/unit/analytics/test_fundamental_statements.py`

**Key APIs:**

```python
# analytics/fundamental/statements.py
class FinancialStatements(UTCModel):
    """Parsed financial statements from SEC EDGAR (XBRL) or API."""
    instrument_id: str
    fiscal_year: int
    fiscal_period: str  # "Q1", "Q2", "Q3", "Q4", "FY"
    income_statement: dict[str, float]
    balance_sheet: dict[str, float]
    cash_flow: dict[str, float]
    filing_date: datetime  # UTC via UTCModel

    @classmethod
    def from_edgar(cls, ticker: str) -> FinancialStatements:
        """Fetch and parse SEC EDGAR XBRL filing via edgartools."""
    @classmethod
    def from_api(cls, data: dict[str, Any]) -> FinancialStatements: ...

# analytics/fundamental/ratios.py
class RatioCalculator:
    def compute_all(self, statements: FinancialStatements) -> dict[str, float]: ...
    def profitability(self, st: FinancialStatements) -> dict[str, float]: ...
    def valuation(self, st: FinancialStatements, price: float) -> dict[str, float]: ...
    def liquidity(self, st: FinancialStatements) -> dict[str, float]: ...
    def leverage(self, st: FinancialStatements) -> dict[str, float]: ...
    def efficiency(self, st: FinancialStatements) -> dict[str, float]: ...

# analytics/fundamental/dcf.py
class DCFValuation(UTCModel):
    """Discounted Cash Flow valuation model."""
    growth_rate: float = 0.05
    terminal_growth: float = 0.02
    discount_rate: float = 0.10
    projection_years: int = 5

    def compute(self, fcf: float, debt: float, cash: float,
                shares_outstanding: float) -> dict[str, float]:
        """Return {fair_value, upside_pct, margin_of_safety, ...}."""

# analytics/fundamental/pipeline.py
class FundamentalPipeline(AnalyticsModule):
    name = "fundamental"
    def __init__(self, bus: EventBusClient, store: FeatureStore,
                 settings: FundamentalSettings): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...
    async def process(self, instrument_id: str) -> None:
        """Fetch statements, compute ratios & DCF, publish feature.updated."""
```

**Test Strategy:**
- Unit tests: each ratio with known inputs → known outputs
- Unit tests: DCF with known inputs → correct fair value (cross-checked against spreadsheet)
- Unit tests: edge cases (negative earnings, zero revenue, missing fields)
- Unit tests: `FinancialStatements.from_api()` with minimal/partial data
- Integration tests: pipeline end-to-end with mock data source

**Acceptance Criteria:**
- All ratios computed correctly: ROE, ROA, P/E, P/B, EV/EBITDA, D/E, Current Ratio
- DCF produces fair value within 1% of spreadsheet reference
- Negative earnings handled without division-by-zero or NaN
- Missing fields raise `FundamentalError` (not `KeyError`)
- Pipeline publishes `feature.updated` event with fundamental ratios
- All tests pass; ruff + mypy pass

### M7: Sentiment NLP — FinBERT News Processor + Social Media + Earnings Call

**Goal:** Implement sentiment analysis for news, social media, and earnings calls using a local FinBERT model with external API fallback. Uses **AlphaAI** (free tier, 20 req/min) for social/news sentiment. Runs in parallel with M4 (no dependency on technical indicators).

**Files to create:**
- `analytics/sentiment/__init__.py` — module init
- `analytics/sentiment/models.py` — `SentimentResult(UTCModel)` with score, label, confidence, source
- `analytics/sentiment/news.py` — `NewsSentimentAnalyzer` (FinBERT on financial news)
- `analytics/sentiment/social.py` — `SocialSentimentAnalyzer` (AlphaAI API for StockTwits/Reddit sentiment)
- `analytics/sentiment/earnings.py` — `EarningsCallSentimentAnalyzer` (FinBERT on earnings transcripts)
- `analytics/sentiment/aggregator.py` — `SentimentAggregator` (combines multiple sources, weighted score)
- `analytics/sentiment/pipeline.py` — `SentimentPipeline(AnalyticsModule)` (publishes feature.updated, bounded queue)
- `analytics/sentiment/config.py` — `SentimentSettings(BackpressureSettings)`
- `analytics/sentiment/errors.py` — `SentimentError`
- `tests/unit/analytics/test_sentiment_news.py`
- `tests/unit/analytics/test_sentiment_aggregator.py`
- `tests/unit/analytics/test_sentiment_pipeline.py`

**Key APIs:**

```python
# analytics/sentiment/models.py
class SentimentResult(UTCModel):
    instrument_id: str
    timestamp: datetime  # UTC via UTCModel
    score: float  # -1.0 (bearish) to +1.0 (bullish)
    label: Literal["bullish", "bearish", "neutral"]
    confidence: float  # 0.0 to 1.0
    source: str  # "news", "social", "earnings"
    text_sample: str = ""

# analytics/sentiment/news.py
class NewsSentimentAnalyzer:
    """Financial news sentiment via local FinBERT model."""

    def __init__(self, model_name: str = "ProsusAI/finbert"):
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_name)

    async def analyze(self, articles: list[NewsArticle]) -> list[SentimentResult]: ...
    def _classify(self, text: str) -> tuple[float, str, float]:
        """Return (score, label, confidence)."""

# analytics/sentiment/aggregator.py
class SentimentAggregator:
    """Combines sentiment from multiple sources with configurable weights."""
    weights: dict[str, float] = {"news": 0.5, "social": 0.2, "earnings": 0.3}
    min_articles: int = 1

    def aggregate(self, results: list[SentimentResult]) -> SentimentResult: ...
```

**Test Strategy:**
- Unit tests: FinBERT returns valid classification for known financial text
- Unit tests: Social sentiment analyzer with mock API responses
- Unit tests: Aggregator with known inputs → correct weighted average
- Unit tests: Empty input, single source, conflicting sources
- Unit tests: Model loading failure → graceful fallback (not crash)
- Integration tests: Pipeline end-to-end with mock article source + NATS

**Acceptance Criteria:**
- FinBERT correctly classifies "profit warning" → bearish, "record revenue" → bullish
- SentimentAggregator produces correct weighted average
- Missing model file returns `SentimentError` (not `ImportError` or crash)
- Pipeline publishes `feature.updated` event with sentiment
- All tests pass; ruff + mypy pass

### M8: Macro Connector — FRED + World Bank + TradingEconomics

**Goal:** Implement macro data connectors that fetch economic indicators from FRED API, World Bank, and TradingEconomics, and publish them as features. Runs in parallel with M4 (no dependency on technical indicators).

**Files to create:**
- `market/sources/__init__.py` — module init
- `market/sources/fred.py` — `FREDClient` (Federal Reserve Economic Data)
- `market/sources/world_bank.py` — `WorldBankClient` (World Bank Open Data)
- `market/sources/trading_economics.py` — `TradingEconomicsClient`
- `market/sources/config.py` — `DataSourceSettings(BackpressureSettings)`
- `market/sources/errors.py` — `SourceError`, `SourceRateLimitError`, `SourceAuthError`
- `market/sources/base.py` — `MacroDataSource(ABC)` base class, `MacroPublisher(AnalyticsModule)`
- `tests/unit/market/test_fred.py`
- `tests/unit/market/test_world_bank.py`

**Key APIs:**

```python
# market/sources/fred.py
class FREDClient:
    """FRED API v2 client for macroeconomic data."""

    def __init__(self, api_key: str, session: httpx.AsyncClient | None = None): ...
    async def get_series(
        self, series_id: str, start: date, end: date | None = None
    ) -> pl.DataFrame: ...
    async def get_multiple(
        self, series_ids: list[str], start: date, end: date | None = None
    ) -> dict[str, pl.DataFrame]: ...

    # FRED Series IDs
    GDP = "GDP"
    CPIAUCSL = "CPIAUCSL"
    FEDFUNDS = "FEDFUNDS"
    UNRATE = "UNRATE"
    T10Y2Y = "T10Y2Y"

# market/sources/base.py
class MacroDataSource(ABC):
    """Base class for macro data sources with rate limiting and caching."""
    name: str
    async def fetch(self, indicator: str) -> pl.DataFrame: ...
    async def health(self) -> bool: ...

class MacroPublisher(AnalyticsModule):
    name = "macro"
    def __init__(self, bus: EventBusClient, store: FeatureStore,
                 settings: DataSourceSettings): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...
    async def publish_all(self) -> None: ...
```

**Test Strategy:**
- Unit tests: FREDClient with mock HTTP responses (known series data)
- Unit tests: rate limit handling (429 response → retry after backoff)
- Unit tests: error handling (invalid API key, network timeout, empty response)
- Unit tests: data normalization (string dates → datetime, string numbers → float)
- Integration tests: MacroPublisher end-to-end with mock source + NATS

**Acceptance Criteria:**
- FREDClient correctly parses FRED API v2 JSON responses
- Rate limit handling: exponential backoff up to max_retries=3, then `SourceRateLimitError`
- Invalid API key raises `SourceAuthError` (not HTTPError)
- Normalization converts dates to datetime and values to float
- MacroPublisher publishes `feature.updated` events with macro indicators
- All tests pass; ruff + mypy pass

### M9: Integration & Wiring — End-to-End Pipeline + Benchmarks + Experiment Registry

**Goal:** Wire all modules into a complete end-to-end pipeline (orchestrated by AnalyticsOrchestrator), run performance benchmarks, register analytics runs in Experiment Registry. E2E uses Binance testnet for live crypto data + synthetic data for full coverage.

**Files to create/modify:**
- `apps/cli/commands/analytics_cmd.py` — CLI commands: `analytics run`, `analytics benchmarks`
- `apps/cli/main.py` — add analytics subcommand
- `config/development.yaml` — add analytics/ingestion/sentiment source settings
- `config/analytics.yaml` — new analytics-specific config file (loads alongside other configs via ConfigLoader)
- `config/production.yaml` — add production analytics config
- `infra/docker/docker-compose.yml` — add TA-Lib C library to Docker image
- `tests/e2e/test_analytics_pipeline.py` — end-to-end pipeline test
- `docs/ANALYTICS.md` — documentation

**Key APIs:**

```python
# CLI commands
# oracle analytics run --feature-set technical_v2 --instruments SPY,AAPL,QQQ
# oracle analytics benchmarks --instruments 500 --indicators 50

# apps/cli/commands/analytics_cmd.py
def run_analytics(args: argparse.Namespace) -> None:
    """Run analytics pipeline:
    1. Load config (includes config/analytics.yaml)
    2. Initialize FeatureStore
    3. Start AnalyticsOrchestrator with all modules
    4. Run until SIGTERM
    """
    import asyncio
    asyncio.run(_run())

def run_benchmarks(args: argparse.Namespace) -> None:
    """Run performance benchmarks and log to Experiment Registry."""
    ...
```

**E2E Pipeline Test:**

The E2E test uses Binance testnet for live crypto bar data + synthetic data for full feature coverage:

1. Start NATS via Docker
2. Initialize FeatureStore with long-format schema
3. Start AnalyticsOrchestrator → starts M4-M8 modules
4. Publish synthetic `market.bar` events for 10 instruments, 100 bars each (Binance testnet for SPOT pairs)
5. Run `IndicatorComputer` (M4) → writes features to Feature Store (long format)
6. Run `RegimePublisher` (M5) → reads features from Feature Store, publishes `regime.updated`
7. Run `FundamentalPipeline` (M6) → publishes `feature.updated`
8. Run `SentimentPipeline` (M7) → publishes `feature.updated`
9. Run `MacroPublisher` (M8) → publishes `feature.updated`
10. Assert all events received: `feature.updated` (technical + fundamental + sentiment + macro) + `regime.updated`
11. Assert Feature Store contains all feature sets with correct schema (long format)
12. Assert DuckDB SQL query returns correct data (e.g., `SELECT * WHERE feature_name = 'sma_20'`)
13. Assert LRU cache returns hot data on repeated queries
14. Assert freshness tracking: `is_stale` returns correct values after test run

**Acceptance Criteria:**
- E2E pipeline processes 10 instruments × 100 bars in <30s
- All feature sets written to Feature Store with correct versioning
- All NATS events received by mock subscriber
- DuckDB SQL query returns correct aggregated results on long-format data
- AnalyticsOrchestrator reports healthy status for all modules
- Benchmark results logged to Experiment Registry with git commit + params
- `oracle analytics run` CLI command works
- `make test` passes all Phase 1 tests (unit + integration + e2e)
- ruff + mypy pass on all Phase 1 code
- Coverage >= 80% on all Phase 1 production code

---

## 4. Expanded Test Plan (Revised)

### Per-Milestone Test Matrix

| Milestone | Unit Tests | Integration Tests | Data Quality | Benchmarks |
|-----------|-----------|-------------------|-------------|------------|
| M1: Foundation | converters round-trip, schema validation, config loading, orchestrator lifecycle, shared TA-Lib helpers, UTC model validation | — | — | DuckDB 100MB scan time |
| M2: Ingestion | normalize_tick/bar with valid/invalid data, reconnect, concrete connector mocks (Binance WS frame, yfinance CSV, CoinPaprika JSON) | NATS pub/sub round-trip | Null prices, negative volume | Throughput: 10K ticks/s |
| M3: Feature Store | write/read round-trip (long format), version tracking, per-feature-set write lock concurrency, LRU cache hit/miss, freshness/staleness | Write 1000x50 features (long format), DuckDB SQL filter by feature_name | NaN fraction, value range per feature_name, stale detection | Write 100K rows, read 1M rows |
| M4: Technical | each indicator vs TA-Lib reference, edge cases (constant, empty), backpressure queue behavior | IndicatorComputer → Feature Store | NaN propagation, inf handling | 500 instr × 50 ind < 10s |
| M5: Regime | synthetic regime detection, ensemble stability, hysteresis, backpressure | RegimePublisher → NATS | Missing data handling | 500 instr full ensemble < 1s |
| M6: Fundamental | ratios vs reference, DCF vs spreadsheet, negative earnings, edgartools stub | Pipeline → Feature Store → NATS | Division by zero, missing fields | 500 instruments < 30s |
| M7: Sentiment | FinBERT classification, aggregator math, model fallback | Pipeline → NATS | Empty text, model OOM | Throughput: articles/s |
| M8: Macro | FRED parser, rate limiting, auth errors | MacroPublisher → NATS | Missing indicators, stale data | Fetch 10 series < 5s |
| M9: Integration | CLI commands parse correctly, Orchestrator startup/shutdown | E2E: 10 instr × 100 bars → all events + store (long format) + metrics | Schema consistency across modules, module health reporting | Full pipeline throughput |

### New Test Cases (v1 → v2)

```python
# Orchestrator lifecycle test
async def test_orchestrator_startup_order():
    """M4 starts before M5; M6, M7, M8 start in parallel."""
    orch = AnalyticsOrchestrator(...)
    await orch.start_all()
    assert modules["technical"].started_at < modules["regime"].started_at
    assert all(m.running for m in [modules["fundamental"], modules["sentiment"], modules["macro"]])

# FeatureStore concurrency guard test
async def test_concurrent_write_lock():
    """Same feature set writes serialize; different sets proceed in parallel."""
    store = FeatureStore(...)
    t1 = asyncio.create_task(store.write_features("technical_v2", ...))
    t2 = asyncio.create_task(store.write_features("technical_v2", ...))  # same set
    t3 = asyncio.create_task(store.write_features("regime_v1", ...))     # different set
    # t1 and t2 overlap? t3 runs concurrently
    ...

# FeatureStore long format round-trip test
def test_long_format_round_trip():
    """Write long-format features, read back, assert structure."""
    df = pl.DataFrame({
        "timestamp": [datetime.now(timezone.utc)] * 4,
        "feature_name": ["sma_20", "rsi_14", "bb_upper", "bb_lower"],
        "value": [195.5, 62.5, 201.0, 190.0],
        "version": ["1.0"] * 4,
        "updated_at": [datetime.now(timezone.utc)] * 4,
    })
    version = await store.write_features("technical_v2", "1.0", df, "SPY")
    result = await store.read_features("technical_v2", feature_names=["sma_20"])
    assert result.filter(pl.col("feature_name") == "sma_20")["value"][0] == 195.5

# UTC enforcement test
def test_utc_model_rejects_naive():
    """UTCModel rejects naive datetimes."""
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        SentimentResult(
            instrument_id="SPY",
            timestamp=datetime.now(),  # naive!
            score=0.5, label="bullish", confidence=0.8, source="news"
        )

# Backpressure test
async def test_backpressure_drop_oldest():
    """Queue at capacity drops oldest event."""
    computer = IndicatorComputer(..., settings=TechnicalSettings(max_queue_size=2))
    await computer.on_bar(bar1)
    await computer.on_bar(bar2)
    await computer.on_bar(bar3)  # bar1 should be dropped
    assert computer.queue.qsize() == 2
    ...

# LRU cache test
def test_feature_cache_hit():
    """Repeated read of same feature set returns cached data."""
    cache = FeatureLRUCache(max_size=10, ttl=300)
    cache.put("technical_v2:SPY", df)
    result = cache.get("technical_v2:SPY")
    assert result is not None
    expected_shape = result.shape

# Freshness test
def test_feature_staleness():
    """is_stale returns True when feature hasn't been updated past TTL."""
    store = FeatureStore(settings=FeatureStoreSettings(cache_ttl_seconds=1))
    # ... write, then time travel ...
    assert store.is_stale("technical_v2", "SPY", max_age_seconds=0)
```

---

## 5. Risk Assessment (Revised)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **R1: TA-Lib C library installation fails in CI** | HIGH | CRITICAL — blocks indicator tests | Docker image with TA-Lib pre-installed; apt install in CI; Polars-native path as degraded mode; tests gated with `@pytest.mark.ta_lib` |
| **R2: Polars/pandas incompatible behavior** | MEDIUM | HIGH — silent wrong results | `converters.py` has exhaustive round-trip tests; NaN handling explicitly tested (Polars uses None, pandas uses NaN); datetime precision explicitly tested |
| **R3: FinBERT model download fails** | MEDIUM | MEDIUM — blocks sentiment | Cache model in Docker image; fallback to API-only sentiment; graceful degradation message in logs |
| **R4: Regime detector parameter sensitivity** | HIGH | MEDIUM — regime oscillation | Minimum regime duration (hysteresis); ensemble averaging (not single detector); backtest with cross-validation for parameter selection |
| **R5: Feature Store long-format schema evolution** | MEDIUM | LOW — long format is additive | Long-format schema is inherently additive (new features = new rows); FeatureSetVersion tracks exact feature_name set; schema evolution documented and tested |
| **R6: DuckDB version conflicts with Polars Arrow format** | LOW | MEDIUM — query failures | Pin duckdb and polars versions; integration test validates interop; fallback to direct Parquet read |
| **R7: Market data rate exceeds ingestion throughput** | MEDIUM | MEDIUM — data loss | Backpressure via bounded asyncio.Queue with drop-policy; configurable batch interval; health metrics for ingestion lag |
| **R8: Experiment Registry JSONL becomes slow** | LOW | LOW — first commit standard | Phase 1 stays on JSONL; migration to PostgreSQL planned for Phase 2 |
| **R9: Timezone handling inconsistencies** | MEDIUM | HIGH — misaligned bars | UTC enforced via `UTCModel` base class; all timestamps in UTC; domain models enforce timezone-aware datetime; test: every datetime field is UTC |
| **R10: Orchestrator module startup race** | LOW | HIGH — M5 starts before M4 features ready | Orchestrator enforces dependency order: M4 ready event → M5 start; FeatureStore signals readiness before modules begin |
| **R11: Concurrent FeatureStore write contention** | MEDIUM | MEDIUM — degraded throughput | Per-feature-set asyncio lock; different feature sets proceed in parallel; lock timeout with error reporting |
| **R12: LRU cache returns stale data** | MEDIUM | MEDIUM — analytics on outdated features | TTL-based cache invalidation; freshness tracking as authoritative staleness check; explicit bypass API for critical reads |

---

## 6. New Dependencies (Revised)

### Core Dependencies (analytics extra)

| Package | Version | Rationale |
|---------|---------|-----------|
| `polars` | `>=1.0` | Primary DataFrame library. 10-100x faster than pandas, lazy evaluation, streaming. |
| `duckdb` | `>=1.0` | Embedded analytical SQL engine for Feature Store queries on Parquet. |
| `pyarrow` | `>=17.0` | Arrow format for Polars-DuckDB interop. Required by both. |
| `hmmlearn` | `>=0.3` | Gaussian HMM for regime detection (HMM regime detector). |
| `ruptures` | `>=1.1` | Changepoint detection (BOCD + PELT methods). |
| `httpx` | `>=0.27` | Async HTTP client for external APIs (FRED, World Bank, NewsAPI). |
| `transformers` | `>=4.40` | FinBERT model loading for sentiment NLP. Pin v4.x for stability. |
| `torch` | `>=2.3` | PyTorch backend for FinBERT (transformers dependency). CPU-only. |
| `yfinance` | `>=0.2` | Free US equities EOD data connector (M2). No API key required. |

### Phase 4 Deferred Dependencies

The following are removed from Phase 1 and planned for Phase 4 only:

| Package | Version | Phase | Rationale |
|---------|---------|-------|-----------|
| `hnswlib` | `>=0.8` | Phase 4 | HNSW index for similarity search in RAG/document retrieval. Not needed until full backtesting with document analysis. |
| `edgartools` | `>=1.0` | Phase 4 | SEC EDGAR XBRL parsing for fundamentals (M6). Has MCP server — may integrate via MCP instead. Phase 1 uses mock/yfinance fundamentals. |
| `arcticdb` | `>=4.0` | Phase 4 | Purpose-built DataFrame DB. Only needed when backtesting needs heavy I/O beyond Parquet. |

### Rationale for Each

- **polars >=1.0**: Stable v1 release; primary DataFrame for all new code. Coexists with pandas via explicit converters.
- **duckdb >=1.0**: Embeddable analytical SQL engine purpose-built for Parquet. No separate server, no infrastructure.
- **pyarrow >=17.0**: Polars and DuckDB share the Arrow memory format. Required for zero-copy interop.
- **hmmlearn >=0.3**: The only maintained Gaussian HMM library for Python. Well-tested, scikit-learn compatible API.
- **ruptures >=1.1**: Standard changepoint detection library. Supports PELT, BOCD, and window-based methods.
- **httpx >=0.27**: Async-first HTTP client. Required for async data ingestion without blocking the event loop.
- **transformers >=4.40**: HuggingFace transformers for FinBERT. Pinned to 4.x for API stability.
- **torch >=2.3**: PyTorch backend. CPU-only (no CUDA needed for FinBERT). Required by transformers.
- **yfinance >=0.2**: De facto standard for free US equities EOD data. No API key, no authentication.

### Removed from Phase 1

- ~~**hnswlib >=0.8**: Efficient similarity search for future RAG features.~~ → Deferred to Phase 4. Not needed for analytics engine.

### Updated pyproject.toml analytics extra

```toml
[project.optional-dependencies]
analytics = [
    "polars>=1.0",
    "duckdb>=1.0",
    "pyarrow>=17.0",
    "hmmlearn>=0.3",
    "ruptures>=1.1",
    "httpx>=0.27",
    "transformers>=4.40",
    "torch>=2.3",
    "yfinance>=0.2",
    # Phase 0 analytics deps (unchanged):
    "ta-lib>=0.5",
    "scipy>=1.12",
    "scikit-learn>=1.4",
    "statsmodels>=0.14",
    "arch>=6.3",
]
```

### Docker Changes

```dockerfile
# infra/docker/Dockerfile additions
RUN apt-get update && apt-get install -y --no-install-recommends \
    libta-lib0 \
    libta-lib-dev \
    && rm -rf /var/lib/apt/lists/*

# Pre-download FinBERT model for offline use
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
    AutoTokenizer.from_pretrained('ProsusAI/finbert'); \
    AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

---

## 7. Open Questions

- [ ] TA-Lib version for Docker: `libta-lib0` is available via apt on Debian/Ubuntu, or should we compile from source for latest features? Prefer apt for CI reproducibility, source for development machines.
- [ ] FinBERT alternatives: `ProsusAI/finbert` (~400MB) vs `yiyanghkust/finbert-tone` vs `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` (smaller, faster). Decision: benchmark all three on same 1000-article dataset and pick best accuracy/size trade-off.
- [ ] FRED API key management: should we require `FRED_API_KEY` env var (current design) or support reading from `~/.fred_api_key`? Prefer env var for 12-factor compliance.
- [ ] DuckDB vs Polars for Feature Store aggregation: DuckDB SQL is excellent for ad-hoc queries, but Polars expressions may be faster for repeated computations. Decision deferred to M1 DuckDB eval results.
- [ ] Regime detector refresh rate: should the ensemble run on every bar (real-time) or on a fixed schedule (e.g., every 5 bars)? Default: every bar with hysteresis (rate-limited to 1 change per 5 bars). Adjust based on benchmark results.
- [ ] Should the Feature Store support distributed reads (multiple processes reading the same Parquet files)? Phase 1: single-process. Distributed access planned for Phase 2 (NFS or S3-backed Parquet).
- [ ] What's the fallback when FinBERT model can't be downloaded (air-gapped environment)? Option: API-only sentiment with NewsAPI's built-in sentiment scoring.
- [ ] **NEW — Orchestrator health check interval**: should the AnalyticsOrchestrator poll health every 5s (responsive) or 30s (low overhead)? Default 10s, configurable. Adjust based on operational experience.
- [ ] **NEW — LRU cache max size**: 1000 items is heuristic. Do we need a benchmark to determine optimal size for the 500-instrument workload? Mitigation: start at 1000, monitor cache hit rate in benchmarks, adjust.
- [ ] **NEW — Binance testnet rate limits**: Binance testnet has lower rate limits than production. Ensure E2E tests respect testnet limits or use synthetic data fallback. Default: synthetic data for deterministic CI, testnet flag for integration testing.
- [ ] **NEW — edgartools MCP integration**: edgartools has an MCP server. Should M6 use direct Python library or MCP protocol? Decision: Phase 1 uses mock/SEC website data; MCP integration evaluated for Phase 2 when fundamentals are used in strategy generation.
