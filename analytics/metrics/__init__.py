"""Analytics metrics — canonical performance metrics + robustness.

``canonical`` is the single source of truth for Sharpe/Sortino/Calmar
semantics (P1-A, ADR-021).  ``robustness`` carries the overfitting and
bootstrap diagnostics that consume them.
"""

from analytics.metrics.canonical import (
    DEFAULT_PERIODS_PER_YEAR,
    calmar_ratio,
    max_drawdown,
    max_drawdown_from_returns,
    sharpe_ratio,
    sortino_ratio,
)

__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "calmar_ratio",
    "max_drawdown",
    "max_drawdown_from_returns",
    "sharpe_ratio",
    "sortino_ratio",
]
