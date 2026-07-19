#!/usr/bin/env bash
# Verify the project runs on the correct Python with required packages.
# Exit non-zero if any check fails. Source: scripts/check_env.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python interpreter not found at '$PYTHON'."
    echo "Create/sync it with: uv sync --frozen --all-extras --all-groups"
    exit 1
fi

PY_VERSION="$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PY_VERSION" != "3.12" ]; then
    echo "ERROR: Python 3.12.x required, got $PY_VERSION"
    exit 1
fi
echo "OK: Python $PY_VERSION"

missing=0
for pkg in talib vectorbt deap langgraph polars numpy pandas ruff mypy pytest; do
    if ! "$PYTHON" -c "import $pkg" 2>/dev/null; then
        echo "MISSING: $pkg"
        missing=$((missing + 1))
    fi
done

if [ "$missing" -gt 0 ]; then
    echo "ERROR: $missing required package(s) missing."
    echo "Run: uv sync --frozen --all-extras --all-groups"
    exit 1
fi

echo "OK: all required packages importable"
echo "Environment ready."
