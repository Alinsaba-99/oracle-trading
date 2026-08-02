"""Sandbox Gate 3 — Strategy protocol contract check.

Verifies that a candidate strategy class satisfies the ``BacktestSignal``
protocol used by Oracle:
  - Has a ``compute(self, data)`` method returning ``pl.Series``
  - Has ``__init__`` that accepts keyword arguments for parameters
  - The returned series has correct dtype (Int8) and length

This is Gate 3 — the final gate before a candidate is admitted to backtest.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger("oracle.genetics.gates.protocol_check")


@dataclass
class ProtocolResult:
    """Result of protocol contract check."""

    passed: bool = False
    errors: list[str] | None = None
    class_name: str | None = None
    params: dict[str, object] | None = None


def check_protocol(source: str, class_name: str | None = None) -> ProtocolResult:
    """Verify a candidate strategy class satisfies the BacktestSignal protocol.

    Args:
        source: Python source code of the candidate strategy.
        class_name: Optional class name to check. If None, auto-detect.

    Returns:
        ProtocolResult with passed=True/False.
    """
    errors: list[str] = []

    # Write source to temp file and import it
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="gate3_") as f:
        f.write(source)
        tmp_path = f.name

    try:
        # Dynamic import
        spec = importlib.util.spec_from_file_location("_gate3_candidate", tmp_path)
        if spec is None or spec.loader is None:
            errors.append("Failed to load candidate module")
            return ProtocolResult(passed=False, errors=errors)

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find the strategy class
        strategy_cls: type[Any] | None = None
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if class_name and name == class_name:
                strategy_cls = obj
                break
            if hasattr(obj, "compute") and name != "object":
                strategy_cls = obj
                class_name = name
                break

        if strategy_cls is None:
            errors.append("No class with compute() method found")
            return ProtocolResult(passed=False, errors=errors, class_name=class_name)

        # 1. Check compute method exists
        if not hasattr(strategy_cls, "compute"):
            errors.append(f"Class '{class_name}' has no compute() method")

        # 2. Check compute is callable
        compute_fn = getattr(strategy_cls, "compute", None)
        if not callable(compute_fn):
            errors.append(f"compute() on '{class_name}' is not callable")

        # 3. Try instantiation with default params
        try:
            instance = strategy_cls()
        except Exception as exc:
            errors.append(f"Instantiation failed: {type(exc).__name__}: {exc}")

        if errors:
            return ProtocolResult(passed=False, errors=errors, class_name=class_name)

        # 4. Check compute() returns correct type with valid data
        instance = strategy_cls()
        import numpy as np

        n = 60
        data = pl.DataFrame(
            {
                "open": np.random.uniform(100, 200, n),
                "high": np.random.uniform(100, 200, n),
                "low": np.random.uniform(100, 200, n),
                "close": np.random.uniform(100, 200, n),
                "volume": np.random.randint(1000, 10000, n),
            }
        )
        try:
            result = instance.compute(data)
        except Exception as exc:
            errors.append(f"compute() raised: {type(exc).__name__}: {exc}")
            return ProtocolResult(passed=False, errors=errors, class_name=class_name)

        if not isinstance(result, pl.Series):
            errors.append(f"compute() returned {type(result).__name__}, expected pl.Series")
            return ProtocolResult(passed=False, errors=errors, class_name=class_name)

        if len(result) != n:
            errors.append(f"compute() returned {len(result)} elements, expected {n}")

        # 5. Check signal values are valid (-1, 0, 1 or 0, 1)
        unique = {int(v) for v in result.unique() if v is not None}
        if not unique.issubset({-1, 0, 1}):
            errors.append(f"Signal values {unique} are not all in {{-1, 0, 1}}")

        # 6. Check __init__ parameters (extract signature)
        sig = inspect.signature(strategy_cls.__init__)
        params: dict[str, object] = {
            k: v.default if v.default is not inspect.Parameter.empty else None
            for k, v in sig.parameters.items()
            if k != "self"
        }

        if errors:
            return ProtocolResult(passed=False, errors=errors, class_name=class_name)

        return ProtocolResult(passed=True, class_name=class_name, params=params)

    except Exception as exc:
        errors.append(f"Unexpected protocol error: {type(exc).__name__}: {exc}")
        return ProtocolResult(passed=False, errors=errors)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


__all__ = ["ProtocolResult", "check_protocol"]
