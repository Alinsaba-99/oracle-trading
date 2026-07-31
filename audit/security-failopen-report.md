# Security Audit Report: Fail-Open Patterns

**Project:** oracle-trading  
**Date:** 2026-07-30  
**Scope:** `execution/`, `apps/`, `agents/`, `core/`, `market/`, `scripts/`  
**Focus:** Fail-open patterns — absent risk_manager, disabled auth, silent exceptions  

---

## Executive Summary

The codebase shows a **deliberate architectural awareness** of security concerns — production guards exist, the OrderManager explicitly rejects `risk_manager=None`, and there is even a unit test (`test_parity.py`) that checks for bare `except: pass`. However, **multiple fail-open gaps remain**, particularly in broker exception handling, orchestration risk bypass, and API auth configuration. Three **CRITICAL** issues were found in production-facing paths.

**Total issues found: 47**  
**By severity:** CRITICAL: 3 | HIGH: 5 | MEDIUM: 18 | LOW: 21

---

## Issue Table

| # | Severity | Category | File | Line | Pattern | Description |
|---|----------|----------|------|------|---------|-------------|
| 1 | **CRITICAL** | Fail-Open: Auth | `apps/api/config.py` | 31–38 | `auth_enabled = bool(self.api_key)` | Auth is **completely disabled** when `ORACLE_API_KEY` is empty. In dev mode (`debug=True`), API routes have **zero authentication**. |
| 2 | **CRITICAL** | Fail-Open: Auth | `apps/api/main.py` | 97–105 | `if ... and settings.auth_enabled` | Auth middleware gate is conditional on `auth_enabled`. When key is missing, **all `/api/` endpoints are accessible without any credential**. |
| 3 | **CRITICAL** | Fail-Open: Risk Bypass | `agents/orchestrator/graph.py` | 253–267 | `risk_manager is None → permissive default` | When `risk_manager=None` (the default, line 394), the risk node returns `{"approved": True}` with max position 25% and no limits. **All trades auto-approved. No log warning.** |
| 4 | **HIGH** | Silent Degradation | `execution/brokers/ccxt_broker.py` | 60–66 | `except Exception: return False` | `cancel_order()` returns `False` on ANY exception. Cannot distinguish "order not found" from "exchange auth failure" or "connection lost". |
| 5 | **HIGH** | Silent Degradation | `execution/brokers/ccxt_broker.py` | 73–79 | `except Exception: return "unknown"` | `order_status()` returns `"unknown"` on any exception. Masked failures could cause incorrect position tracking. |
| 6 | **HIGH** | Silent Degradation | `execution/brokers/ccxt_broker.py` | 84–89 | `except Exception: return []` | `positions()` returns empty list on connection/auth failure. Caller cannot distinguish "no positions" from "exchange unreachable". |
| 7 | **HIGH** | Silent Swallow | `apps/api/main.py` | 123–124 | `except Exception: pass` | JSON sanitization middleware silently swallows ALL parsing errors. Malformed JSON responses bypass sanitization without any log entry. |
| 8 | **HIGH** | Silent Swallow | `analytics/backtest/walk_forward.py` | 216–217 | `except Exception: pass  # OOS metrics are best-effort` | Walk-forward silently discards ALL OOS metrics on any error. Comment acknowledges best-effort but no logging. |
| 9 | **MEDIUM** | Silent Degradation | `execution/session_guards.py` | 97–101 | `except Exception: self._record_failure(); return None` | `SignalProviderCircuit.call()` returns `None` on any exception. Caller can't distinguish "circuit open" from "auth error" from "timeout". |
| 10 | **MEDIUM** | Silent Continue | `execution/order_manager/manager.py` | 144–145 | `except Exception: logger.exception(...)` | `reconcile()` catches ALL exceptions and continues. Reconciliation silently fails — position mismatches are never detected. |
| 11 | **MEDIUM** | Silent Redaction | `execution/brokers/base.py` | 79–83 | `except Exception: logger.exception(...)` | Reconnection loop catches all exceptions. While behavior is logged, the specific error type is lost. |
| 12 | **MEDIUM** | Silent Continue | `core/reconciliation.py` | 113–115 | `except Exception as e: logger.error(...)` | `reconcile()` catches ALL errors, marks broker disconnected, but continues processing. Fatal position discrepancies are masked. |
| 13 | **MEDIUM** | Silent Continue | `core/reconciliation.py` | 172–173 | `except Exception as e: logger.warning(...)` | Position reconciliation errors silently logged as warning. Processing continues. |
| 14 | **MEDIUM** | Silent Continue | `core/reconciliation.py` | 210–211 | `except Exception as e: logger.warning(...)` | Order reconciliation errors silently logged as warning. Processing continues. |
| 15 | **MEDIUM** | Silent Continue | `core/reconciliation.py` | 245–246 | `except Exception as e: logger.warning(...)` | Cash reconciliation errors silently logged as warning. Processing continues. |
| 16 | **MEDIUM** | Silent Switch | `core/reconciliation_worker.py` | 110–111 | `except Exception: logger.exception(...)` | `on_mismatch` callback failure swallowed with log. Worker continues. |
| 17 | **MEDIUM** | Silent Continue | `core/reconciliation_worker.py` | 114–123 | `except Exception: logger.exception(...)` | Reconciliation loop continues on error, stops after N consecutive. OK pattern but all exception types lumped together. |
| 18 | **MEDIUM** | Silent Continue | `core/plugin/discovery.py` | 45–46 | `except Exception: continue` | Plugin class scanning silently skips malformed modules. |
| 19 | **MEDIUM** | Silent Continue | `core/plugin/discovery.py` | 120–121 | `except Exception: continue` | Plugin module import failure silently skipped. |
| 20 | **MEDIUM** | Silent Continue | `core/plugin/discovery.py` | 157–158 | `except Exception: continue` | Plugin file loading failure silently skipped. |
| 21 | **MEDIUM** | Silent Degradation | `core/observability.py` | 170–172 | `except Exception as e: logging.warning(...)` | OpenTelemetry init failure gracefully degrades. OK for observability but should be CRITICAL in production. |
| 22 | **MEDIUM** | Silent Swallow | `market/data_sources.py` | 312–313 | `except Exception: pass` | Funding rate fetch failure silently ignored. |
| 23 | **MEDIUM** | Silent Return | `market/sentiment.py` | 50–52 | `except Exception: return []` | AlphaAI news fetch failure silently returns empty list. |
| 24 | **MEDIUM** | Silent Return | `market/sentiment.py` | 68–70 | `except Exception: return {...}` | AlphaAI sentiment fetch failure silently returns default. |
| 25 | **MEDIUM** | Silent Return | `market/macro.py` | 98–100 | `except Exception: return []` | GDELT fetch failure silently returns empty list. |
| 26 | **MEDIUM** | Silent Continue | `agents/orchestrator/graph.py` | 56–57 | `except Exception as exc: return {"errors": [...]}` | Oracle analysis failure returns error in state but continues pipeline. |
| 27 | **MEDIUM** | Silent Continue | `agents/orchestrator/graph.py` | 217–218 | `except Exception as exc: return {"error": ...}` | Analyst failure sets error but continues to next analyst. |
| 28 | **LOW** | Silent Degradation | `apps/cli/main.py` | 192–195 | `except Exception: ver = "0.1.0"` | Version detection failure silently falls back to hardcoded default. |
| 29 | **LOW** | Silent Degradation | `apps/cli/main.py` | 452–453 | `except Exception: return None` | Experiment load failure silently returns None. |
| 30 | **LOW** | Silent Degradation | `apps/cli/agent_commands.py` | 255–256 | `except Exception: return None` | Data fetch failure silently returns None. |
| 31 | **LOW** | Silent Continue | `scripts/run_ga_evolution.py` | 111–112 | `except Exception: pass` | GA signal conversion failure silently skipped. |
| 32 | **LOW** | Silent Continue | `scripts/run_ga_evolution.py` | 125–126 | `except Exception: pass` | GA signal conversion failure silently skipped. |
| 33 | **LOW** | Silent Continue | `scripts/run_sweep_strategies.py` | 63–64 | `except Exception: pass` | Strategy discovery silent skip. |
| 34 | **LOW** | Silent Continue | `scripts/run_sweep_strategies.py` | 94–95 | `except Exception: pass` | Asset loading silent skip. |
| 35 | **LOW** | Silent Continue | `scripts/run_sweep_strategies.py` | 121–122 | `except Exception: ...` | Strategy test failure silent skip. |
| 36 | **LOW** | Silent Continue | `scripts/run_sweep_strategies.py` | 199 | `except Exception: continue` | Data load failure silent skip. |
| 37 | **LOW** | Silent Continue | `scripts/run_sweep_strategies.py` | 207–208 | `except Exception: continue` | Strategy test failure silent skip. |
| 38 | **LOW** | Silent Continue | `scripts/run_portfolio_v2.py` | 99–100 | `except Exception: continue` | Strategy compute failure silent skip. |
| 39 | **LOW** | Silent Continue | `scripts/run_portfolio_v2.py` | 118 | `except Exception as exc: ... continue` | Session failure continues to next. |
| 40 | **LOW** | Silent Degradation | `scripts/validate_best_dna.py` | 101–102 | `except Exception: signals[...] = np.zeros(...)` | Signal conversion failure silently zeroes data. |
| 41 | **LOW** | Silent Degradation | `scripts/validate_best_dna.py` | 110–111 | `except Exception: signals[...] = np.zeros(...)` | Alpha signal failure silently zeroes data. |
| 42 | **LOW** | Silent Return | `scripts/test_excess_sharpe.py` | 75–76 | `except Exception: return None` | Data load fails silently. |
| 43 | **LOW** | Silent Degradation | `scripts/test_excess_sharpe.py` | 110–111 | `except Exception: return (0.0, 0)` | Strategy test failure silently returns zeros. |
| 44 | **LOW** | Silent Return | `scripts/validate_4edge.py` | 85–86 | `except Exception: return None` | Data load fails silently. |
| 45 | **LOW** | Silent Return | `scripts/validate_4edge.py` | 114–115 | `except Exception: return []` | Strategy test failure silently returns empty. |
| 46 | **LOW** | Silent Continue | `scripts/simulate_mff_challenge.py` | 109–110 | `except Exception: continue` | Session failure silently skipped. |
| 47 | **LOW** | Silent Continue | `scripts/run_sweep_all.py` | 108–109 | `except Exception: return None` | Data load silently returns None. |

---

## Category Metrics

| Category | Count | Description |
|----------|-------|-------------|
| **Fail-Open: Auth Disabled** | 2 | API auth completely bypassed when no `ORACLE_API_KEY`. Production guard protects only `debug=False`. |
| **Fail-Open: Risk Bypass** | 2 | Orchestrator risk node returns permissive default when no risk_manager configured. Default is `None`. |
| **Fail-Open: Broker Silent Degradation** | 4 | CCXT broker returns generic falsy values on ANY exception. Connection/auth failures indistinguishable. |
| **Bare `except: pass`** | 0 ✅ | No bare `except:` in production code (test at `tests/unit/test_parity.py` enforces this). |
| **`except Exception: pass`** | 5 | Errors silently consumed with no logging. |
| **`except Exception: return None/False/0/[]`** | 21 | Errors silently degraded to empty/falsy return values. |
| **`except Exception: continue`** | 10 | Errors silently skipped in loops. |
| **`except Exception` with log only** | 12 | Errors logged but execution continues without recovery. |

---

## Detailed Findings

### 🔴 CRITICAL 1: API Auth Completely Optional

**Files:** `apps/api/config.py:31-38`, `apps/api/main.py:45-58, 89-105`

The auth middleware only activates when `settings.auth_enabled` is `True`, which requires `settings.api_key` to be non-empty. In development mode (`debug=True`), the production guard at line 45-50 is skipped. **The API starts with zero authentication.**

```python
# config.py:32-38
@property
def auth_enabled(self) -> bool:
    return bool(self.api_key)  # Empty string → False
```

The production guard does catch the case of `debug=False` without a key, but the warning in dev mode is just a `logging.warning()` — the API still runs open.

**Remediation:** Enable auth by default with a known development key or require explicit `--no-auth` flag. Alternatively, bind to `localhost:8000` instead of `0.0.0.0:8000` when auth is disabled.

---

### 🔴 CRITICAL 2: Orchestrator Risk Bypass

**Files:** `agents/orchestrator/graph.py:253-267, 394-412`

When `risk_manager=None` (the default), the risk node returns a **permissively approved assessment** without any warning:

```python
def _make_risk_node(risk_manager: Any | None) -> Any:
    if risk_manager is None:
        def risk_node_sync(_state: GraphState) -> dict[str, Any]:
            return {
                "risk_assessment": {
                    "approved": True,     # ← Always True!
                    "max_position_size": 0.25,
                    ...
                }
            }
        return risk_node_sync
```

The `risk_manager` parameter in `make_graph()` defaults to `None` (line 394), meaning the orchestrator explicitly allows running without risk checks. The docstring even says: "When None, the risk node returns a permissive default assessment."

**Remediation:** If no risk manager is configured, the orchestrator should **fail closed** — return a rejected assessment with reason "No risk manager configured" — or at minimum issue a CRITICAL log warning.

---

### 🔴 CRITICAL 3: CCXT Broker Silent Auth/Connection Failure

**Files:** `execution/brokers/ccxt_broker.py:60-89`

Three methods — `cancel_order`, `order_status`, and `positions` — wrap their entire body in `try/except Exception` and return non-descriptive defaults:

```python
async def cancel_order(self, broker_order_id: str) -> bool:
    try:
        await self._exchange.cancel_order(broker_order_id)
        return True
    except Exception:
        return False  # ← Could be auth failure, rate limit, connection lost


async def order_status(self, broker_order_id: str) -> str:
    try:
        order = await self._exchange.fetch_order(broker_order_id)
        return str(order.get("status", "unknown"))
    except Exception:
        return "unknown"  # ← "unknown" is also a valid exchange status


async def positions(self) -> list[Any]:
    try:
        return list(await self._exchange.fetch_positions())
    except Exception:
        return []  # ← Empty list could also be "no positions"
```

**Impact:** These patterns make it impossible for callers (like the OrderManager or reconciliation engine) to distinguish between legitimate empty/no-op results and **actual failures** (expired API keys, exchange downtime, rate limits). An expired API key would silently cause `cancel_order` to return `False`, `order_status` to return `"unknown"`, and `positions` to return `[]`.

**Remediation:** Let exceptions propagate to callers, or wrap in a typed broker error (e.g., `BrokerAuthError`, `BrokerConnectionError`) so callers can handle appropriately.

---

### 🟠 HIGH: API JSON Sanitization `except Exception: pass`

**File:** `apps/api/main.py:123-124`

```python
try:
    ...
    cleaned = SafeJSONEncoder.clean(data)
    return JSONResponse(content=cleaned, status_code=response.status_code)
except Exception:
    pass  # ← Silent. No log. Original response returned.
```

If the JSON sanitization middleware fails for any reason, the error is **completely silent**. This means if `SafeJSONEncoder.clean()` encounters an unhandled type, or the response body can't be parsed, the middleware silently returns the original (potentially unsafe) response. In production, this could expose `NaN`/`Infinity` values that bypass the encoder.

**Remediation:** Log the exception, preserve the original response as fallback but with a warning. Never `pass` silently in middleware.

---

### 🟠 HIGH: Walk-Forward Silent OOS Metric Drop

**File:** `analytics/backtest/walk_forward.py:216-217`

```python
except Exception:
    pass  # OOS metrics are best-effort
```

When calculating out-of-sample metrics, ALL exceptions are silently swallowed. This means if one fold's OOS metrics fail, they are silently treated as non-existent — potentially biasing walk-forward results toward folds that don't crash.

**Remediation:** Log the exception and set OOS metrics to `None` explicitly, so consumers can distinguish "not computed" from "computed and is 0".

---

### 🟡 MEDIUM: Reconciliation Silently Degrades on Error

**File:** `core/reconciliation.py:113-115`

```python
try:
    await self._reconcile_positions(report)
    await self._reconcile_orders(report)
    await self._reconcile_cash(report)
except Exception as e:
    logger.error(f"Reconciliation failed: {e}")
    report.broker_connected = False
```

If position reconciliation crashes mid-way, orders and cash are never checked, but the report is still returned as if the reconciliation completed. The individual `_reconcile_*` methods also have `try/except` that silently degrades:

```python
except Exception as e:
    logger.warning(f"Position reconciliation error: {e}")
```

**Impact:** Fatal mismatches between broker and OMS can go undetected because the error is demoted from "this is a problem" to "processing continues without this data".

**Remediation:** At minimum, flag the report as incomplete. Consider making position reconciliation errors escalate to `FATAL` severity.

---

## Good Patterns Found

Despite the issues above, the codebase does some things well:

1. **`tests/unit/test_parity.py`**: Contains an AST-level check for `except Exception: pass` in the Nautilus engine. This shows security awareness.
2. **OrderManager**: Explicitly rejects `risk_manager=None` with a `ValueError` ("a missing risk gate is a safety violation").
3. **PortfolioBridge**: Also rejects `risk_manager=None` with the same pattern.
4. **Production guard**: `apps/api/main.py:45-50` prevents starting in production mode without auth — **fail-closed for production**.
5. **Security headers middleware**: Sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
6. **ReconciliationWorker**: Counts consecutive errors and stops after threshold — properly fail-closed.
7. **SignalProviderCircuit**: Has a well-designed circuit breaker pattern with proper state management.

---

## Recommendations (Priority Order)

1. **CRITICAL — Make orchestration fail-closed**: The orchestrator risk node should reject all trades when no risk manager is configured, not auto-approve them. At minimum, emit a CRITICAL log entry on every bypass.

2. **CRITICAL — Let broker errors propagate**: Stop catching all `Exception` in `CCXTBroker.cancel_order()`, `.order_status()`, and `.positions()`. Let callers handle typed errors, or at minimum wrap in `BrokerError`.

3. **HIGH — Enable auth by default**: Bind to `localhost` or require an explicit opt-out for unauthenticated API access. The production guard is good, but the dev-mode default should not be "open to all networks".

4. **MEDIUM — Log every `except Exception: pass`**: All silent exception handlers should at minimum log at `warning` level with the exception context. The five `pass` instances are bugs waiting to happen.

5. **MEDIUM — Flag incomplete reconciliation**: When reconciliation partially fails, mark the report as incomplete so consumers (e.g., the order gating logic) can distinguish "all checked" from "some checks skipped due to errors".

6. **LOW — Remove test script risk bypasses**: The `_AllowAll` class in `scripts/run_regime_paper_smoke.py` should log each bypass it grants.

---

*Report generated by automated security audit of oracle-trading.*
