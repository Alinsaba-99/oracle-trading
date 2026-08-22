"""BL-711 — Tearsheet rendering (quantstats + ffn) for edge-factory reports.

quantstats renders the HTML tearsheet; ffn computes the summary stats
table.  Diagnostic layer only: ``analytics/metrics/canonical.py`` (ADR-021)
stays the single source of truth for every qualification number.
"""

from __future__ import annotations

from pathlib import Path

import ffn
import pandas as pd
import quantstats as qs


def _require_datetime_index(equity: pd.Series) -> None:
    if not isinstance(equity.index, pd.DatetimeIndex):
        raise TypeError("equity series must have a DatetimeIndex")


def _to_returns(equity: pd.Series) -> pd.Series:
    _require_datetime_index(equity)
    rets = equity.pct_change().dropna()
    rets.name = "strategy"
    return rets


def render_html_tearsheet(equity: pd.Series, out_path: str | Path, title: str) -> Path:
    """Write a quantstats HTML tearsheet for *equity*; returns the path."""
    rets = _to_returns(equity)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # quantstats 0.0.81 ships untyped API wrappers; the runtime behavior
    # is covered by test_html_tearsheet_written.
    qs.reports.html(rets, output=str(out), title=title)  # type: ignore[no-untyped-call]
    return out


def ffn_stats(equity: pd.Series) -> dict[str, float]:
    """ffn summary stats (diagnostic; canonical metrics live elsewhere)."""
    _require_datetime_index(equity)
    st = ffn.calc_stats(equity)
    return {
        "cagr": float(st.cagr),
        "calmar": float(st.calmar),
        "max_drawdown": float(st.max_drawdown),
        "sharpe": float(st.daily_sharpe),
    }
