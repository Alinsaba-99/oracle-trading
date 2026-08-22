"""BL-711 smoke: synthetic equity → HTML tearsheet + ffn stats.

Writes ``logs/edge-factory/bl711-smoke.html`` (gitignored output).
Run: uv run python scripts/smoke_tearsheet_bl711.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.research.factory.tearsheet import ffn_stats, render_html_tearsheet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "edge-factory" / "bl711-smoke.html"


def _synthetic_equity(n: int = 300, seed: int = 11) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", name="date")
    rng = np.random.default_rng(seed)
    rets = 0.0008 + 0.010 * rng.standard_normal(n)
    return pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx, name="equity")


def main() -> int:
    equity = _synthetic_equity()
    path = render_html_tearsheet(equity, OUT, "BL-711 smoke")
    stats = ffn_stats(equity)
    print(f"OK wrote {path} size={path.stat().st_size}")
    print("ffn_stats", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
