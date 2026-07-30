"""Forecast scaling — map raw signals to continuous size forecasts.

Inspired by Rob Carver's pysystemtrade.  The core idea:
  - Every raw signal (-1, 0, 1) is scaled to a forecast in [-10, +10]
  - Forecasts from different strategies become comparable
  - Combined forecast drives position sizing via vol target

The scaling factor ensures that the average absolute forecast is ~10,
making forecasts from different strategies directly comparable.
"""

from __future__ import annotations

import numpy as np


def compute_forecast_scalar(
    raw_signals: np.ndarray, target_abs: float = 10.0, *, min_periods: int = 20
) -> float:
    """Compute the forecast scalar that maps raw signals to target scale.

    The scalar is ``target_abs / avg_abs(raw_signal)``.  This ensures
    that on average the forecast magnitude equals ``target_abs``,
    making forecasts comparable across strategies.

    Args:
        raw_signals: Historical raw signal values (e.g. -1, 0, 1).
        target_abs: Target average absolute forecast (default 10, Carver).
        min_periods: Minimum observations for a meaningful scalar.

    Returns:
        Forecast scalar multiplier.  If insufficient data, returns 1.0.
    """
    if len(raw_signals) < min_periods:
        return 1.0
    avg_abs = float(np.mean(np.abs(raw_signals)))
    if avg_abs < 1e-9:
        return 1.0
    return target_abs / avg_abs


def scale_forecast(raw: float, scalar: float) -> float:
    """Scale a single raw signal to a continuous forecast.

    Args:
        raw: Raw signal (-1, 0, 1).
        scalar: Forecast scalar from ``compute_forecast_scalar``.

    Returns:
        Scaled forecast in [-scalar, +scalar].
    """
    return raw * scalar


def cap_forecast(forecast: float, max_abs: float = 20.0) -> float:
    """Cap a forecast to prevent extreme positioning.

    Carver recommends capping individual forecasts at ±20.
    """
    return max(-max_abs, min(max_abs, forecast))


# ── Pooled forecast ───────────────────────────────────────────────────


def compute_pooled_forecast(
    scaled_forecasts: dict[str, np.ndarray], weights: dict[str, float]
) -> np.ndarray:
    """Combine multiple scaled forecasts into one pooled forecast.

    The pooled forecast is a weighted average of individual forecasts.
    Each forecast has already been scaled and capped individually.

    Args:
        scaled_forecasts: Dict mapping strategy name → scaled forecast array.
        weights: Dict mapping strategy name → allocation weight (sums to 1).

    Returns:
        Array of pooled forecast values.
    """
    if not scaled_forecasts or not weights:
        return np.array([])

    # Align lengths to the shortest
    min_len = min(len(v) for v in scaled_forecasts.values())
    pooled = np.zeros(min_len)

    total_weight = sum(weights.values())
    if total_weight <= 0:
        return pooled

    for name, forecast in scaled_forecasts.items():
        w = weights.get(name, 0.0)
        if w > 0:
            pooled += w * forecast[:min_len].astype(float)

    return pooled / total_weight


# ── Instrument Diversification Multiplier (IDM) ──────────────────────


def compute_idm(correlation_matrix: np.ndarray, max_idm: float = 2.5) -> float:
    """Compute Instrument Diversification Multiplier.

    IDM = 1 / sqrt(avg_correlation)

    When strategies are uncorrelated → IDM up to ``max_idm``.
    When perfectly correlated → IDM = 1.

    Args:
        correlation_matrix: NxN correlation matrix of strategy returns.
        max_idm: Maximum allowed IDM (Carver recommends 2.5).

    Returns:
        IDM value between 1.0 and ``max_idm``.
    """
    n = correlation_matrix.shape[0]
    if n <= 1:
        return 1.0
    # Average off-diagonal correlation
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += correlation_matrix[i, j]
            count += 1
    avg_corr = total / count if count > 0 else 0.0
    idm = 1.0 / np.sqrt(avg_corr) if avg_corr > 0 else max_idm
    return min(max_idm, max(1.0, float(idm)))


__all__ = [
    "cap_forecast",
    "compute_forecast_scalar",
    "compute_idm",
    "compute_pooled_forecast",
    "scale_forecast",
]
