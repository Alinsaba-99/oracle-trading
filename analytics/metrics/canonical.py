"""Oracle canonical metrics module — the single source of truth (P1-A).

Background (dossier architetturale 2026-08-19, finding F-01): the codebase
grew five independent Sharpe implementations with *divergent edge-case
semantics* (``+inf`` vs ``0.0`` vs ``nan`` for a zero-variance series,
hard-coded 252 annualization even for monthly/hourly data).  After the R5
31x Sharpe-inflation incident, a wrong verdict on a gate run is the most
expensive defect this repo can produce — so metric semantics are now:

1. defined exactly once, here;
2. pinned by golden vectors in ``tests/unit/test_metrics_canonical.py``;
3. delegated to by every caller (no local re-derivations).

Semantics decided (ADR-021):

* ``sharpe = mean / std(ddof=1) * sqrt(periods_per_year)``
* ``n < 2`` observations → ``0.0`` (undefined, reported as zero, not NaN)
* ``std == 0``: ``+inf`` if mean > 0, ``-inf`` if mean < 0, ``0.0`` if
  mean == 0.  A constant-positive stream has *infinite* risk-adjusted
  return; collapsing it to 0.0 hid it from gate comparisons.
* ``periods_per_year`` is REQUIRED to be explicit at every gate boundary
  (252 daily, 12 monthly, 1560 hourly-equity, …).  The default 252 is a
  convenience for daily research code only.

Vectorized equity-curve engines compute log-return Sharpe with a float
``periods_per_year`` derived from actual bar spacing (vectorized.py
``_risk_metrics_from_equity``); that path is the documented exception and
delegates nothing here because its input is an equity curve, not returns.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "calmar_ratio",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
]

#: Daily trading days — the research default only.  Gate code must pass
#: the factor that matches its data frequency explicitly.
DEFAULT_PERIODS_PER_YEAR: int = 252


def _as_numpy(returns: npt.ArrayLike | Sequence[float]) -> npt.NDArray[np.float64]:
    arr = np.asarray(returns, dtype=np.float64)
    return arr[np.isfinite(arr)]


def sharpe_ratio(
    returns: npt.ArrayLike | Sequence[float], *, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Annualised Sharpe ratio (excess over 0, no risk-free adjustment).

    The ONE canonical implementation.  See module docstring for the
    semantics contract; golden vectors live in
    ``tests/unit/test_metrics_canonical.py``.
    """
    clean = _as_numpy(returns)
    if clean.size < 2:
        return 0.0
    std = float(np.std(clean, ddof=1))
    mean = float(np.mean(clean))
    if std == 0.0:
        if mean > 0:
            return math.inf
        if mean < 0:
            return -math.inf
        return 0.0
    return mean / std * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: npt.ArrayLike | Sequence[float], *, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Annualised Sortino ratio (downside deviation of negative periods).

    ``n < 2`` → 0.0.  No negative periods → ``+inf`` if mean > 0, else 0.0.
    Downside std zero (all negatives equal) follows the Sharpe zero-var
    rule.  Otherwise ``mean / downside_std * sqrt(ppy)``.
    """
    clean = _as_numpy(returns)
    if clean.size < 2:
        return 0.0
    mean = float(np.mean(clean))
    downside = clean[clean < 0]
    if downside.size == 0:
        if mean > 0:
            return math.inf
        return 0.0
    if downside.size == 1:
        # Downside deviation with a single observation is undefined
        # (ddof=1 divides by zero); follow the zero-variance rule.
        if mean > 0:
            return math.inf
        if mean < 0:
            return -math.inf
        return 0.0
    ds = float(np.std(downside, ddof=1))
    if ds == 0.0:
        if mean > 0:
            return math.inf
        if mean < 0:
            return -math.inf
        return 0.0
    return mean / ds * math.sqrt(periods_per_year)


def calmar_ratio(
    returns: npt.ArrayLike | Sequence[float],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    max_drawdown: float | None = None,
) -> float:
    """Calmar ratio: annualised compound return / max drawdown.

    ``max_drawdown`` is a positive fraction (0.25 = 25 % peak-to-trough).
    When omitted it is computed from the compounded equity curve of the
    supplied returns.  Zero drawdown or ``n < 2`` → 0.0.
    """
    clean = _as_numpy(returns)
    if clean.size < 2:
        return 0.0
    growth = float(np.prod(1.0 + clean))
    if growth <= 0:
        return 0.0
    ann_return = growth ** (periods_per_year / clean.size) - 1.0
    if max_drawdown is None:
        max_drawdown = max_drawdown_from_returns(clean)
    if max_drawdown <= 0.0:
        return 0.0
    return float(ann_return / max_drawdown)


def max_drawdown_from_returns(returns: npt.ArrayLike | Sequence[float]) -> float:
    """Maximum drawdown as a positive fraction from a return series."""
    clean = _as_numpy(returns)
    if clean.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    drawdowns = 1.0 - equity / np.where(peak > 0, peak, 1.0)
    return float(np.max(drawdowns)) if drawdowns.size else 0.0


# Backward-compatible aliases used by older modules during the migration.
max_drawdown = max_drawdown_from_returns
