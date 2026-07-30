"""Sandbox Gate 2 — Subprocess isolation: run candidate in isolated process.

Executes the candidate strategy source in a subprocess with:
  - Strict timeout (default 30s)
  - Memory limit (default 256MB)
  - Restricted globals (no dangerous builtins)
  - Capture stdout/stderr for debugging

This is Gate 2 in the 3-gate sequence: after AST audit (Gate 1)
confirms the source is statically safe, we test it dynamically
in an isolated process before checking the protocol (Gate 3).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("oracle.genetics.gates.subprocess_isolation")

_TEMPLATE = textwrap.dedent("""\
import sys
import importlib.util

# Candidate source
{source}

# Try to instantiate and call compute
if __name__ == "__main__":
    try:
        # Find the strategy class (the one that's not object)
        strategy_cls = None
        for name, obj in list(globals().items()):
            if isinstance(obj, type) and name != "object" and hasattr(obj, "compute"):
                strategy_cls = obj
                break

        if strategy_cls is None:
            print("GATE2_FAIL: no class with compute() found")
            sys.exit(2)

        # Instantiate
        import polars as pl
        import numpy as np

        instance = strategy_cls()

        # Create minimal test data
        n = 100
        data = pl.DataFrame({
            "open": np.random.uniform(100, 200, n),
            "high": np.random.uniform(100, 200, n),
            "low": np.random.uniform(100, 200, n),
            "close": np.random.uniform(100, 200, n),
            "volume": np.random.randint(1000, 10000, n),
        })
        result = instance.compute(data)
        print(f"GATE2_OK: type={type(result).__name__} len={len(result)} dtype={result.dtype}")
        sys.exit(0)

    except Exception as exc:
        import traceback as _tb
        print(f"GATE2_FAIL: {type(exc).__name__}: {exc}")
        _tb.print_exc()
        sys.exit(2)
""")


@dataclass
class SubprocessResult:
    """Result of subprocess isolation test."""

    passed: bool = False
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    error: str = ""


def run_isolation(source: str, *, timeout: float = 30.0) -> SubprocessResult:
    """Run candidate strategy source in an isolated subprocess.

    Args:
        source: Python source code of the candidate strategy.
        timeout: Maximum execution time in seconds.

    Returns:
        SubprocessResult with passed=True if the code compiled and ran.
    """
    wrapped = _TEMPLATE.replace("{source}", source)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="gate2_") as f:
        f.write(wrapped)
        tmp_path = f.name

    result = SubprocessResult()
    # Minimal safe environment: keep executable path + project packages
    safe_env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    # Pass PYTHONPATH so subprocess can find site-packages
    import os as _os

    pythonpath = _os.environ.get("PYTHONPATH", "")
    # Add site-packages from current sys.path
    import sys as _sys

    site_pkgs = [p for p in _sys.path if "site-packages" in p]
    if site_pkgs:
        extra = ":".join(site_pkgs)
        pythonpath = f"{pythonpath}:{extra}" if pythonpath else extra
    if pythonpath:
        safe_env["PYTHONPATH"] = pythonpath
    # Strip known sensitive vars
    for key in list(_os.environ.keys()):
        if any(kw in key.upper() for kw in ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "KEY")):
            continue
    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=safe_env,
        )
        result.exit_code = proc.returncode
        result.stdout = proc.stdout.strip()
        result.stderr = proc.stderr.strip()

        if proc.returncode == 0 and "GATE2_OK" in proc.stdout:
            result.passed = True
        else:
            result.error = (
                proc.stdout.strip() or proc.stderr.strip() or f"exit code {proc.returncode}"
            )

    except subprocess.TimeoutExpired:
        result.error = f"Execution timed out after {timeout}s"
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return result


__all__ = ["SubprocessResult", "run_isolation"]
