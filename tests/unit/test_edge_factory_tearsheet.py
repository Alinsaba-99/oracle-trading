"""BL-711 — quantstats+ffn tearsheet smoke.

Diagnostic only; ADR-021 canonical metrics stay authoritative.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.research.factory.tearsheet import ffn_stats, render_html_tearsheet


def _synthetic_equity(n: int = 300, seed: int = 11) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", name="date")
    rng = np.random.default_rng(seed)
    rets = 0.0008 + 0.010 * rng.standard_normal(n)
    return pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx, name="equity")


def test_html_tearsheet_written(tmp_path: Path) -> None:
    out = render_html_tearsheet(_synthetic_equity(), tmp_path / "t.html", "BL-711 smoke")
    assert out.exists()
    assert out.stat().st_size > 5_000
    html = out.read_text(encoding="utf-8")
    assert "Sharpe" in html


def test_ffn_stats_finite() -> None:
    stats = ffn_stats(_synthetic_equity())
    assert set(stats) == {"cagr", "calmar", "max_drawdown", "sharpe"}
    assert all(math.isfinite(v) for v in stats.values())


def test_tearsheet_does_not_import_canonical_metrics() -> None:
    """AC BL-711: NON sostituisce analytics/metrics/canonical.py."""
    import analytics.research.factory.tearsheet as mod

    src = Path(sys.modules[mod.__name__].__file__ or "").read_text(encoding="utf-8")
    assert "analytics.metrics" not in src
