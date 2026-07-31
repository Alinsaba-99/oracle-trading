# Oracle Trading — Quantitative Finance Deep Analysis

**Data:** 2026-07-30 | **Scope:** oracle-trading system | **Rating:** RESEARCH-GRADE (NOT production)

---

## 1. Backtest Engine Duality: vectorbt vs nautilus-trader

### Architecture
| Engine | File | Dep | Status |
|--------|------|-----|--------|
| `VectorizedEngine` | `analytics/backtest/engines/vectorized.py` | vectorbt≥0.23.3 | ✅ Active |
| `NautilusEngine` | `analytics/backtest/engines/nautilus.py` | nautilus-trader≥1.230.0 | ⚠️ Candidate |
| Orchestrator | `analytics/backtest/orchestrator.py` | — | ✅ Dual routing |

### Cross-Engine Parity: ❌ NOT CERTIFIED
- `tests/unit/test_parity.py` → `test_vectorbt_nautilus_parity()` is **an empty `pass`** (with TODO: "implement when Nautilus certification is active")
- Known divergence acknowledged: cost models apply differently (vectorbt subtracts from returns, nautilus deducts from cash)
- Parity test uses **0% commission/slippage** because of cost model mismatch
- **No multi-asset parity tests**, **no realistic cost scenario tests**

### VectorizedEngine (vectorbt)
- Custom annualization logic (`_periods_per_year()`) to fix vectorbt's NaN-on-irregular-index issue
- Uses `vbt.Portfolio.from_signals()` with `OppositeEntryMode.Close`
- Custom `_risk_metrics_from_equity()` computes Sharpe/Sortino/Calmar from equity curve (bypasses vectorbt's NaN-prone stats)
- Signal shift by 1 bar to prevent look-ahead bias ✅
- No support for multi-instrument

### NautilusEngine (nautilus-trader)
- Uses `FuturesContract` with point-value P&L calculation ✅
- Configurable `FillModel` with `prob_slippage`
- Requires `timestamp` column (safety gate over VectorizedEngine)
- **⚠️ Equity curve is flat**: `_compute_equity_curve_from_account()` returns a **constant vector** (final_balance repeated), not per-bar equity — means per-bar metrics (drawdown, Ulcer, etc.) are meaningless
- **⚠️ Silent exception swallowing**: `try/except Exception: pass` patterns exist in equity curve extraction
- **⚠️ CAGR mis-named**: Line 502-503: `total_return=cagr` → the result stores CAGR as total_return

### Risk Rating: 🔴 HIGH
The dual engine strategy is sound in design but **completely unvalidated**. Without parity certification, any strategy can give different results depending on which engine is used. This is a G5-blocking issue.

---

## 2. Genetic Evolution Risk

### Walk-Forward Implementation
| Component | File | Status |
|-----------|------|--------|
| CPCV splitter | `analytics/backtest/splitters.py` | ✅ Implemented with purge |
| Time-series split | `analytics/backtest/splitters.py` | ✅ Implemented with purge |
| WalkForwardEngine | `analytics/backtest/walk_forward.py` | ✅ Active |
| OOS concatenated equity | `walk_forward.py:combined_metrics()` | ✅ Computed |
| FitnessEvaluator | `genetics/fitness/evaluator.py` | ✅ Uses walk-forward |

### 🔴 CRITICAL FINDINGS

1. **Embargo parameter NOT passed to engine**
   `WalkForwardConfig` defines `embargo: int = 10` (line 48 in `evaluator.py`), but in `evaluate()` (lines 137-143):
   ```python
   fold_results = wf.run(
       data,
       signal,
       settings=...,
       n_splits=...,
       purge_window=...,
       split_method=...,  # ← embargo NOT passed!
   )
   ```
   The `embargo` parameter is silently dropped. WalkForwardEngine.run() doesn't accept an `embargo` parameter. This means **data leakage across fold boundaries is not fully prevented**.

2. **No explicit train/val/test holdout**
   The GA optimizes directly on walk-forward results (train→test). There is no separate **holdout set** that remains untouched until final validation. This creates **optimization bias** — the GA can overfit to the walk-forward structure.

3. **GA placeholder fitness**
   `genetics/ga_evolution.py:StrategyEvolution.evaluate_fitness()` is explicitly documented as "PLACEHOLDER — override in subclass" (line 111-112). The real GA loop uses `FitnessEvaluator`, but this architectural split means the simple GA could be used inadvertently.

4. **Small data fingerprint**
   `_data_fingerprint()` (line 224-235 in evaluator.py) hashes **only the first 10 close values** + shape + column names. Two datasets with the same first 10 bars but different later periods would collide in the cache.

5. **Cache collision risk**
   `genome_hash()` uses only `normalized_params` bytes — two genomes with identical normalized params but different param_defs would collide.

### Walk-Forward Configuration
| Default | Value | Assessment |
|---------|-------|-----------|
| n_splits | 5 | ✅ Minimum recommended |
| purge_window | 5 | ⚠️ Sample-based, not time-based — may not align with autocorrelation structure |
| embargo | 10 | ❌ NOT APPLIED (silently dropped) |
| split_method | "time" | ✅ Expanding window preserves temporal order |

### Risk Rating: 🔴 HIGH
Without proper embargo application and without a separate holdout set, **the GA can overfit to walk-forward folds**. The 100,000+ backtests per evolution run (population=100, generations=50, folds=5, islands=4) compound this risk. The `_EMPTY_FITNESS` sentinel (-1, -1, -1, 1) is too close to zero to provide a strong penalty signal.

---

## 3. Results Analysis (5 most recent JSON files)

### All 5 files show IDENTICAL, computationally-degenerate metrics

| File | Strategy | Period | Sharpe | Sortino | Calmar | Max DD | Trades |
|------|----------|--------|--------|---------|--------|--------|--------|
| cf1d00ac | CompositeMTFSignal | 10 days (GOLD) | **207.84** | **207.84** | **7033** | 0.15% | 1 |
| e83a06bc | CompositeMTFSignal | 10 days (GOLD) | **207.84** | **207.84** | **7033** | 0.15% | 1 |
| 06013b81 | **DonchianBreakout** | 10 days (GOLD) | **207.84** | **207.84** | **7033** | 0.15% | 1 |
| 9134da15 | CompositeMTFSignal | 10 days (GOLD) | **207.84** | **207.84** | **7033** | 0.15% | 1 |
| latest | CompositeMTFSignal | 10 days (GOLD) | **207.84** | **207.84** | **7033** | 0.15% | 1 |

### 🔴 MATHEMATICAL DECOMPOSITION OF THE ARTIFACT

**Sharpe = 207.84**
- Daily return ≈ 0.97% (10.15% over 10 trading days)
- With only 1 trade, the return series has **near-zero variance** (flat except for one linear ramp)
- Sharpe = (mean_return / std_return) × √252
- If all returns are identical (linear equity curve), std → 0 → Sharpe → ∞
- The code has safeguards for zero std, but on borderline cases it produces extreme values

**Calmar = 7033**
- CAGR ≈ 10.15% annualized = (1.1015)^(252/10) - 1 ≈ 33.63 = **3363%** per year
- Max DD = 0.15%
- Calmar = CAGR / MaxDD = 3363% / 0.15% ≈ 7033 (annualization artifact)

**Sortino = Sharpe** (both 207.84)
- No negative returns → downside_std ≈ 0 → Sortino degenerates to fallback to Sharpe
- Confirms the equity curve has no down periods

**Total Return = 10.15% ✓** — This is the only trustworthy metric (a simple P&L calculation).

### Why this matters
These results demonstrate that **metrics computed on <30 samples are unreliable**. The system stores these values without warning or confidence intervals. A user reading `Sharpe > 200` would be misled.

### Recommendation
- Reject backtest results with < 30 bars or < 10 trades
- Auto-include Sharpe 95% confidence intervals (Lo 2002) in BacktestResult
- Flag extreme values (Sharpe > 5, Calmar > 10) for human review

---

## 4. Market Data Quality

### Source Coverage
| Source | Symbols | Quality | Adjustments |
|--------|---------|---------|-------------|
| yfinance | ES=NQ=GC=CL=F + equities | ⚠️ Continuous contract (yfinance's roll) | yfinance Adj Close is auto-computed, **no verification** |
| CCXT | Crypto spot & perpetuals | ✅ Raw OHLCV | **No adjustment needed** for perpetuals |
| OpenBB | US equities/ETFs | ⚠️ API stability issues | Not adjusted |
| Polygon.io | Intraday futures | ✅ Requires API key | Not continuously available |
| FRED | Macro data | ✅ Free tier | N/A |

### 🔴 Key Gaps

1. **No adjusted close handling in pipeline**
   - yfinance returns Adj Close by default, but the code reads "close" column
   - No verification that close == adjusted close
   - No split/dividend adjustment logic for non-yfinance sources

2. **No survivorship bias check in data ingestion**
   - `BacktestDataProvider` has `survivorship_bias` flag and `delisted` tracking
   - **Not wired into the actual data sources** — yfinance/CCXT/OpenBB fetchers don't set this flag
   - `BiasCorrector` applies empirical haircuts, but these are post-hoc, not data-quality controls

3. **Continuous futures contract risk**
   - `market/roll.py` defines roll dates and month codes
   - **No back-adjusted price series** — yfinance's ES=F uses its own roll logic (unknown method)
   - No verification of roll quality (gap size at roll, volume profile)

4. **Data pinning failure (G5 REGRESSED)**
   - `data/ohlcv/ES_1d.parquet` is untracked (`data/ohlcv/` in .gitignore COMMENTED OUT)
   - Any script calling `yfinance_futures("ES")` overwrites it
   - ADR-014 documents the evidence loss
   - Direct consequence: **M31 non riproducibile**

### Contract Specs: ✅ EXCELLENT
`market/contracts.py` has verified CME futures specs with:
- ES ($50/pt), MES ($5/pt), NQ ($20/pt), MNQ ($2/pt), GC ($100/pt), MGC ($10/pt), CL ($1000/point), MCL ($100/pt)
- Point values, tick values, margins, mini/micro ratios
- All verified 2026-07-19 against CME Group specs

### Risk Rating: 🟡 MEDIUM-HIGH
Data quality is adequate for research but has known survivorship bias gaps and the data-pinning regression blocks G5 certification.

---

## 5. Cross-Engine Regression Testing

| Test | File | Status |
|------|------|--------|
| Vectorbt engine tests | `test_vectorbt_engine.py` (325 lines) | ✅ Works |
| Nautilus no-silent-fallback | `test_parity.py` | ✅ AST check |
| **Cross-engine parity** | `test_parity.py:test_vectorbt_nautilus_parity` | **❌ EMPTY (pass)** |
| Test cross engine | `test_cross_engine.py` (141 lines) | ⚠️ Zero costs |
| Cost model tests | `test_parity.py:TestCostModel` | ⚠️ Abstract constants only |

### Known Divergences
1. **Cost model**: vectorbt subtracts from returns, nautilus deducts from cash → different final equity even with same settings
2. **Tolerances**: Sharpe ±10%, Final Equity ±5% — wide enough to hide significant differences
3. **Data requirements**: NautilusEngine requires `timestamp` column; VectorizedEngine doesn't

### Risk Rating: 🔴 HIGH
The entire dual-engine qualification pipeline rests on certification that doesn't exist. The G5 gate is BLOCKED precisely because of this.

---

## 6. Risk Metrics Inventory

### In `analytics/backtest/metrics.py` (MetricsCalculator)
| Metric | Implementation | In BacktestResult? |
|--------|---------------|-------------------|
| Sharpe Ratio | ✅ Polars-native, annualized | ✅ Yes |
| Sortino Ratio | ✅ Downside deviation | ✅ Yes |
| Calmar Ratio | ✅ CAGR / MaxDD | ✅ Yes |
| Max Drawdown | ✅ Peak-to-trough | ✅ Yes |
| CAGR | ✅ Geometric growth | ✅ Yes |
| Volatility | ✅ Annualized std | ✅ Yes |
| Total Return | ✅ Final/initial | ✅ Yes |
| Profit Factor | ✅ Gross P&L ratio | ✅ Yes |
| Win Rate | ✅ Fraction positive | ✅ Yes |
| Expectancy | ✅ Mean per observation | ❌ Not stored |
| Max Consecutive Losses | ✅ Run-length | ❌ Not stored |
| **Ulcer Index** | ✅ RMS of drawdowns | ❌ Not stored |

### In `agents/decision/risk.py` (RiskManager — agent-level)
| Metric | Implementation | In Backtest? |
|--------|---------------|-------------|
| VaR (95%) | ✅ Historical quantile | ❌ Agent only |
| CVaR / Expected Shortfall | ✅ Mean of tail | ❌ Agent only |
| Kelly Fraction | ✅ p - q/b clamped to [0,1] | ❌ Agent only |
| Correlation Check | ✅ Threshold-based | ❌ Agent only |

### 🔴 Critical Gap
**VaR and CVaR are completely absent from the backtest metrics pipeline.** They exist only in the agent-level RiskManager, which is used for pre-trade decisions, not for evaluating backtest results. This means:
- A backtest can show Sharpe=3 while having 20% VaR (daily) — **the report won't show it**
- Prop firm qualification requires VaR monitoring; the current backtest can't provide it
- Ulcer Index (in MetricsCalculator) is computed but not stored in BacktestResult — wasted compute

### Risk Rating: 🟡 MEDIUM
Standard metrics coverage is good. The missing VaR/CVaR in the backtest pipeline is a significant gap for institutional use but acceptable for research.

---

## 7. Prop Firm Readiness

### Gate Status (from ORACLE_AUTOPILOT_STATUS.md)
| Gate | Status | What's Missing |
|------|--------|---------------|
| G0 baseline | ✅ PASSED | — |
| G1 authority | ✅ PASSED | OrderManager accepts `risk_manager=None` |
| G2 contracts | 🟡 PARTIAL | Intraday futures missing (Polygon key) |
| G3 ledger/OMS | ✅ PASSED | Postgres path active |
| G4 hard risk | ✅ PASSED | PropFirm adapter excluded from paper harness |
| **G5 research truth** | ❌ **REGRESSED** | Dataset not pinned, M31 non-reproducible |
| **G6 paper** | 🟡 **REJECTED** | Pass rate 77% vs target 90% |
| **G7 prop firm** | ⚪ **NOT STARTED** | Blocked on G5/G6 |

### Implemented Infrastructure
- ✅ **PropFirmRiskGovernor**: Full-featured (`policy/prop_firm/governor.py`):
  - Daily loss tracking (balance/equity basis, timezone-aware reset)
  - Overall drawdown (static/trailing EOD/intraday)
  - Pre-trade gate (projected loss check)
  - Position sizing from remaining risk budget
  - Breach detection with severity levels
  - Challenge outcome evaluation (PASSED/FAILED)

- ✅ **FirmProgramProfile**: Versioned, immutable profiles (`policy/prop_firm/profile.py`)
  - Support modes: AUTO_SUPPORTED, ASSISTED_ONLY, RESEARCH_ONLY, UNSUPPORTED
  - Content hashing for integrity verification
  - Effective date range for rule versioning
  - Full rule encoding: profit target, drawdown limits, daily loss, contract caps, scaling, sessions, news blackout, consistency, min days

- ✅ **Topstep 50K fixture** in `policy/prop_firm/fixtures.py`

- ✅ **Verified firms**: Topstep (RESEARCH_ONLY), TPT PRO (ASSISTED_ONLY — bots banned), MyFundedFutures (RESEARCH_ONLY), FundedNext (RESEARCH_ONLY), Apex (UNSUPPORTED — Cloudflare)

### Economic Reality (from AUDIT_FINDINGS.md, 30 paper sessions)
| Metric | Value | Target | Verdict |
|--------|-------|--------|---------|
| Pass rate | 77% (23/30) | ≥ 90% | ❌ |
| Mean Sharpe | -0.31 | ≥ -0.5 | ✅ (borderline) |
| Mean Max DD | 1.54% | ≤ 3.0% | ✅ |
| Single-session payout (PASSED) | +0.78% | — | ⚠️ Small |
| Regime bias | 96.7% choppy | balanced | 🔴 |

### 🔴 Key Risk: Monoculture
- 29/30 sessions routed to RsiReversion in mean_reversion regime
- **No edge on breakout, trend-following, or Lorentzian strategies**
- The regime detector (`_sma_regime_heuristic`) classifies everything as CHOPPY as a default bias
- Edge exists only in choppy → mean_reversion on ES daily, with negative average Sharpe

### Risk Rating: 🟡 MEDIUM-HIGH
The infrastructure and policy framework are **well-designed and comprehensive**. The blocker is **empirical**: the strategies don't have enough edge to pass G6 consistently. The prop firm framework itself (governor, profiles, registry) is production-quality.

---

## 8. Summary Risk Matrix

| Area | Rating | Key Risk | Financial Impact |
|------|--------|----------|------------------|
| 1. Engine Parity | 🔴 HIGH | No cross-engine certification; G5 BLOCKED | Divergent backtest results → wrong strategy selection |
| 2. GA Evolution | 🔴 HIGH | Embargo not applied; no holdout set | Overfitting → negative live expectancy |
| 3. Result Metrics | 🔴 CRITICAL | Sharpe 207.84 from 10-day data | Misleading metric interpretation → false confidence |
| 4. Market Data | 🟡 MED-HIGH | No adjusted close check; survivorship bias | Historical bias in backtest results |
| 5. Regression Tests | 🔴 HIGH | Parity test is empty `pass` | Engine divergence undetected |
| 6. Risk Metrics | 🟡 MEDIUM | No VaR/CVaR in backtest pipeline | Incomplete risk picture for prop firm qualification |
| 7. Prop Firm Readiness | 🟡 MED-HIGH | Framework excellent, edge insufficient | 77% pass rate vs target 90%; 96% regime monoculture |

### Overall: RESEARCH-GRADE 🔴— not production-deployable

---

## 9. Specific Action Items

### P0 — Must Fix Before Any Live or Prop Firm
1. **Wire `embargo` parameter** from WalkForwardConfig into WalkForwardEngine.run() — prevents fold leakage
2. **Add holdout set** that is NEVER used during GA optimization (final validation only)
3. **Fix result metrics**: add minimum sample requirements (≥30 bars, ≥10 trades); add Sharpe 95% CI; flag extreme values
4. **Certify NautilusEngine**: remove silent `except: pass`, fix flat equity curve, verify parity at realistic costs
5. **Pin `ES_1d.parquet`** data (BL-001..003) — unblocks G5

### P1 — High Priority
6. **Add VaR/ES to BacktestResult** — both 95% and 99% from equity curve
7. **Add data quality gate** — verify adjusted close availability per source
8. **Fix regime detector calibration** (BL-010..014) — reduce CHOPPY bias from 96% to ~50%
9. **Run 100+ independent paper sessions** (BL-020) — sufficient for statistical significance

### P2 — Should Address
10. **Fix `_compute_equity_curve_from_account`** in NautilusEngine — per-bar equity, not flat
11. **Fix CAGR naming** in NautilusEngine result — `total_return=cagr` is a bug
12. **Change `_data_fingerprint`** to hash full close column or use file checksum
13. **Add Ulcer Index to BacktestResult**
