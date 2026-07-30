# Architectural Analysis Report — oracle-trading

> Generated: 2026-07-30  
> Scope: import graph, fail-open patterns, storage, ADR-010, NATS

---

## 1. Import Graph — Dependency Rule Violations (ARCHITECTURE.md §3.1)

### 1.1 agents → analytics (REVERSE: agents imports analytics internals)

| Path | Line | Violation |
|------|------|-----------|
| `agents/oracle/oracle.py` | 15-16 | `from analytics.regime.config import RegimeSettings` + `from analytics.regime.detector import RegimeDetector` |

**Problem**: `agents/` (intelligence plane) imports directly from `analytics/` (research plane). Per ARCHITECTURE.md §4.1, intelligence should produce decision contracts, not import research internals.

### 1.2 analytics → execution (LATERAL: research imports safety-critical code)

| Path | Line | Violation |
|------|------|-----------|
| `analytics/qualification/execution.py` | 32-44 | `from execution.brokers.paper_engine import ...; from execution.order_manager.types import OrderRequest` |

**Problem**: `analytics/` (research plane) imports `execution/` (safety control plane). Creates a lateral dependency that makes the research path depend on order execution internals.

### 1.3 analytics → policy + market (MULTI-DIRECTIONAL IMPORTS)

| Path | Line | Violation |
|------|------|-----------|
| `analytics/strategy/sweep.py` | 27-28 | `from policy.prop_firm import THE5ERS; from policy.prop_firm.profile import PropFirmProfile` |
| `analytics/strategy/fitness.py` | 25-26 | `from policy.prop_firm import THE5ERS; from policy.prop_firm.profile import PropFirmProfile` |
| `analytics/backtest/challenge.py` | 24-25 | `from policy.prop_firm.governor import ...; from policy.prop_firm.profile import PropFirmProfile` |
| `analytics/backtest/challenge_intraday.py` | 21-22 | `from policy.prop_firm.governor import ...` |
| `analytics/backtest/data.py` | 16 | `from market.store import FeatureStore` |
| `analytics/orchestrator.py` | 12 | `from market.store.feature_store import FeatureStore` |

### 1.4 policy → execution (INWARD → OUTWARD)

| Path | Line | Violation |
|------|------|-----------|
| `policy/prop_firm/order_risk.py` | 8 | `from execution.order_manager.types import OrderRequest` |

**Problem**: Per ARCHITECTURE.md §3.1: "Policy non importa implementazioni OrderManager". But `order_risk.py` imports `execution.order_manager.types`, violating inward-only dependency rule.

### 1.5 market → analytics (LATERAL)

| Path | Line | Violation |
|------|------|-----------|
| `market/ingestion/__init__.py` | 27 | `from analytics.common.errors import IngestionError` |

**Problem**: `market/` imports from `analytics/`, creating the analytics↔market cycle described in ARCHITECTURE.md §2.1.

### 1.6 Contracts in `agents/` instead of `application/contracts/`

| Path | Description |
|------|-------------|
| `agents/protocol.py` | Contains `PortfolioDecision`, `RiskAssessment`, `MarketState` — contracts used by execution bridge |
| `agents/committee/contracts.py` | Contains `PortfolioPlan`, `TradeIntent`, `CommitteeTrigger` — decision contracts |

**Problem**: ARCHITECTURE.md §3.1 requires contracts in `application/contracts/`. They currently live in `agents/`, forcing execution to depend on the agents package.

---

## 2. Fail-Open Patterns

### 2.1 Risk Manager Bypass in MAS Graph (CRITICAL)

| Path | Line | Pattern |
|------|------|---------|
| `agents/orchestrator/graph.py` | 253-267 | `risk_manager=None` → creates a permissive `risk_node_sync` that **auto-approves** all risk (returns `approved=True, max_position_size=0.25`) |
| `agents/orchestrator/graph.py` | 394 | `risk_manager: Any \| None = None` — signature explicitly allows None |
| `agents/orchestrator/graph.py` | 410-415 | Docstring says "When ``None``, the risk node returns a permissive default assessment." |

**Evidence** (lines 253-267):
```python
def _make_risk_node(risk_manager: Any | None) -> Any:
    if risk_manager is None:
        def risk_node_sync(_state: GraphState) -> dict[str, Any]:
            return {
                "risk_assessment": {
                    "approved": True,        # ← auto-approves!
                    "max_position_size": 0.25,
                    ...
                }
            }
        return risk_node_sync
```

**Risk**: Any caller that creates a MAS graph without a risk_manager gets a permissive assessment. Combined with optional portfolio_manager (also defaults to None → HOLD), the graph silently fails open.

### 2.2 API Authentication Disabled Without Key

| Path | Line | Pattern |
|------|------|---------|
| `apps/api/main.py` | 52-57 | `ORACLE_API_KEY` empty → only logs a warning, continues with `auth_enabled` effectively disabled |
| `apps/api/main.py` | 45-50 | Production guard: only blocks when `settings.is_production AND not settings.auth_enabled` |

**Evidence** (lines 52-57):
```python
if not settings.api_key:
    logging.warning(
        "No ORACLE_API_KEY configured — API authentication is disabled. "
        "Set ORACLE_API_KEY environment variable for production."
    )
```

**Risk**: Dev/QA environments with empty API keys run with zero authentication. Any `/api/` endpoint is open.

### 2.3 Swallowed Exceptions (Bare `except Exception:` / `except Exception: pass`)

Count of bare `except Exception:` patterns across the codebase: **50+ locations**

Critical locations:

| Path | Line | Pattern |
|------|------|---------|
| `agents/analysts/macro.py` | 122 | `except Exception:` — analyst analysis failure silently returns empty |
| `agents/oracle/synthesizer.py` | 51 | `except Exception:` — LLM synthesis failure silently falls back |
| `agents/oracle/oracle.py` | 98 | `except Exception:` — state synthesis error silently absorbed |
| `agents/llm.py` | 118 | `except Exception:` — LLM call failure silently continues |
| `analytics/backtest/providers.py` | 72 | `except Exception:` in data provider — error silently returns fallback |
| `analytics/backtest/engines/nautilus.py` | 328, 474 | `except Exception:` in backtest engine — hard errors swallowed |
| `genetics/fitness/evaluator.py` | 160 | `except Exception:` in fitness evaluation |
| `analytics/strategy/researcher.py` | 194 | `except Exception:` in strategy research |
| `analytics/strategy/adaptive_ensemble.py` | 238, 256 | `except Exception:` in ensemble logic |
| `analytics/research/factor_timing.py` | 430 | `except Exception:` in factor timing |
| `execution/session_guards.py` | 99 | `except Exception:` in session guard |
| `agents/orchestrator/graph.py` | 56, 87, 217, 247, 301, 335 | Multiple `except Exception:` — graph node failures silently absorbed |
| `core/reconciliation.py` | 113, 172, 210, 245 | `except Exception as e:` in reconciliation |
| `core/recovery.py` | 96, 119, 133 | `except Exception as e:` in recovery |
| `core/kill.py` | 92, 112 | `except Exception as e:` in kill switch |
| `core/reconciliation_worker.py` | 78, 110-114 | `except Exception:` in reconciliation worker |

**Risk**: Errors in safety-critical paths (reconciliation, kill switch, recovery) are silently ignored. A failed reconciliation or kill operation would not raise, allowing inconsistent state.

### 2.4 OrderManager constructor: NOW fails-closed (previously fail-open)

The ARCHITECTURE.md §2.3 and AUDIT_FINDINGS.md cite OrderManager accepting `risk_manager=None`. The current code (audited) has been fixed:

| Path | Line | Status |
|------|------|--------|
| `execution/order_manager/manager.py` | 29-31 | ✅ Raises `ValueError` if `risk_manager is None` |
| `execution/order_manager/bridge.py` | 28-30 | ✅ Raises `ValueError` if `risk_manager is None` |

**Note**: A test `test_risk_gate_not_configured_passes_through` (line 151) has a misleading name — it actually tests with a wired mock risk, not with None.

---

## 3. Storage Analysis

### 3.1 SQLite Database Files

| File | Purpose |
|------|---------|
| `experiments/experiments.db` | Only real SQLite database file in the repo |

**SQLite-backed stores in code** (create DB at runtime):

| Path | Class/Module | Connection |
|------|-------------|-----------|
| `analytics/research/memory.py` | `ResearchMemory` | `sqlite3.connect()` |
| `analytics/strategy/experiments_store.py` | Experiment registry | `sqlite3.connect()` |
| `agents/committee/journal.py` | `SQLiteDecisionJournal` | SQLite |
| `core/oms_idempotency.py` | `SQLiteIdempotencyStore` | `sqlite3.connect()` |
| `core/domain/experiment.py` | ExperimentRegistry | `aiosqlite` |
| `apps/api/services/intelligence_service.py` | `SQLiteIntelligenceInbox` | SQLite |
| `apps/api/services/trade_service.py` | Trade service | `sqlite3.connect()` |

**Total**: 7 distinct SQLite-backed stores, 6 for application state, 1 for experiments.

### 3.2 Postgres Tests — FAIL

```
$ pytest tests/unit/test_ledger_postgres.py tests/unit/test_oms_postgres.py -v

ERROR collecting tests/unit/test_ledger_postgres.py
    ModuleNotFoundError: No module named 'asyncpg'
ERROR collecting tests/unit/test_oms_postgres.py
    ModuleNotFoundError: No module named 'asyncpg'
```

**Problem**: Both `core/ledger_postgres.py` and `core/oms_postgres.py` require `asyncpg`, which is not installed. Tests cannot run. This means:
- PostgreSQL ledger/OMS implementations are **untestable** in the current environment
- ADR-009's target (PostgreSQL as source of truth) has **no working test suite**

### 3.3 State Authority Gap

Per ARCHITECTURE.md §5 (state authority matrix):
- Account/balance/equity: **SQLite** (dev), **PostgreSQL** (target) — but Postgres is non-functional
- Order/fill: **SQLite** (dev) — no Postgres alternative working
- Ledger: **SQLite** — no production ledger exists

---

## 4. ADR-010 — Deterministic Execution Safety Boundary

### Status: PARTIALLY IMPLEMENTED

| ADR-010 Requirement | Status | Evidence |
|---------------------|--------|----------|
| Mode guard → fail-closed | ✅ Implemented | `core/domain/guard.py` — startup guard checks mode + credentials |
| Hard risk → deterministic | ✅ Implemented | `agents/decision/risk.py` — pure math, no LLM |
| Policy bridge → deterministic | ✅ Implemented | `agents/decision/policy.py` — checks risk_approved flag |
| OrderManager rejects None risk | ✅ Fixed | `execution/order_manager/manager.py:30-31` |
| Bypass matrix CLI/API/MAS/adapter | ❌ Missing | No bypass matrix test found |
| Property test G4 | ❌ Missing | No G4 property test found |
| Credential scope test | ❌ Missing | No credential isolation test found |
| Startup guard (submit CLI fail-closed) | ⚠️ Partial | ModeGuard exists but defaults to RESEARCH when unset |
| Kill switch separated from decision plane | ✅ Implemented | `core/kill.py` — dedicated kill switch |

### Current Fail-Open in MAS Graph (ADR-010 Violation)

The `build_mas_graph()` function in `agents/orchestrator/graph.py:389-438` explicitly defaults `risk_manager=None`, which creates a **permissive risk node** (see §2.1). This directly contradicts ADR-010's decision that "Mode guard, rule resolver, hard risk e OMS sono deterministici e obbligatori."

---

## 5. NATS — Real Usage vs Aspirational

### Status: IMPLEMENTED BUT NOT UNIVERSAL

| Aspect | Status | Evidence |
|--------|--------|----------|
| NATS client library | ✅ Real | `core/events/client.py` — imports nats-py, connect/publish/subscribe |
| JetStream | ✅ Implemented | `self._js = nc.jetstream()` — JetStream context acquired |
| Production usage | ✅ **Yes** | `market/ingestion/__init__.py:57` — `EventBusClient(settings.nats)` in IngestionPipeline |
| Production usage | ✅ **Yes** | `apps/cli/main.py:279` — `EventBusClient(settings.nats)` in CLI |
| 16 event types defined | ✅ Yes | `core/events/__init__.py` — market, order, portfolio, regime, policy, signal, etc. |
| Universal communication bus | ❌ **No** | Not used by analytics, genetics, policy, agents/committee, or execution |
| Transactional outbox | ❌ **Missing** | ARCHITECTURE.md §3.2 describes outbox pattern but it's not implemented |
| NATS as source of truth | ❌ **No** (correctly) | Per ADR-008 and ADR-009, NATS is transport only |

**Conclusion**: NATS isn't aspirational — it's **used in 2 production entry points** (market ingestion and CLI). But it's not the universal bus that ADR-001 envisioned. The `core/events/client.py` and 16 event types form a real foundation, but adoption is limited.

---

## 6. Summary of Critical Findings

| # | Severity | Finding | Path |
|---|----------|---------|------|
| 1 | 🔴 CRITICAL | MAS graph risk bypass: `risk_manager=None` auto-approves all trades | `agents/orchestrator/graph.py:253-267` |
| 2 | 🔴 CRITICAL | API auth disabled when `ORACLE_API_KEY` is empty (warning only) | `apps/api/main.py:52-57` |
| 3 | 🔴 CRITICAL | Postgres tests fail — `asyncpg` missing, ledger/OMS non-functional | `tests/unit/test_ledger_postgres.py`, `test_oms_postgres.py` |
| 4 | 🟡 HIGH | agents→analytics dependency (oracle imports regime detector) | `agents/oracle/oracle.py:15-16` |
| 5 | 🟡 HIGH | analytics→execution dependency (qualification imports order internals) | `analytics/qualification/execution.py:32-44` |
| 6 | 🟡 HIGH | policy→execution dependency (order_risk imports OrderRequest) | `policy/prop_firm/order_risk.py:8` |
| 7 | 🟡 HIGH | 50+ locations with `except Exception:` silently swallowing errors | Across `agents/`, `analytics/`, `core/`, `scripts/` |
| 8 | 🟡 HIGH | Contracts in `agents/protocol.py` instead of `application/contracts/` | `agents/protocol.py` |
| 9 | 🟡 HIGH | 7 SQLite-backed stores, no production PostgreSQL working | Multiple files |
| 10 | 🟡 HIGH | ADR-010 enforcement items (bypass matrix, G4 test, credential test) missing | Not implemented |
| 11 | 🟢 MEDIUM | analytics↔market cycle (bidirectional imports) | `analytics/backtest/data.py:16` ↔ `market/ingestion/__init__.py:27` |
| 12 | 🟢 MEDIUM | No transactional outbox pattern despite architectural commitment | Not implemented |
