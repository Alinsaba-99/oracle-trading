"""Statistical diagnostics for M31 historical replay."""

from __future__ import annotations

from math import sqrt

import numpy as np


def returns_from_values(values: list[float]) -> np.ndarray:
    """Convert a value curve to finite periodic returns."""
    curve = np.asarray(values, dtype=float)
    if curve.size < 2:
        return np.asarray([], dtype=float)
    previous = curve[:-1]
    current = curve[1:]
    valid = np.isfinite(previous) & np.isfinite(current) & (previous != 0)
    returns = np.zeros_like(previous, dtype=float)
    returns[valid] = current[valid] / previous[valid] - 1.0
    return np.asarray(returns[np.isfinite(returns)], dtype=np.float64)


def factor_attribution(
    strategy_returns: np.ndarray, market_returns: np.ndarray, *, periods_per_year: int = 252
) -> dict[str, float]:
    """Estimate single-factor alpha, beta, correlation, and R-squared."""
    length = min(strategy_returns.size, market_returns.size)
    if length < 3:
        return {}
    strategy = strategy_returns[-length:]
    market = market_returns[-length:]
    valid = np.isfinite(strategy) & np.isfinite(market)
    strategy = strategy[valid]
    market = market[valid]
    if strategy.size < 3:
        return {}

    market_variance = float(np.var(market, ddof=1))
    beta = 0.0
    if market_variance > 0:
        covariance = float(np.cov(strategy, market, ddof=1)[0, 1])
        beta = covariance / market_variance
    periodic_alpha = float(np.mean(strategy) - beta * np.mean(market))
    annualized_alpha = periodic_alpha * periods_per_year

    strategy_std = float(np.std(strategy, ddof=1))
    market_std = float(np.std(market, ddof=1))
    correlation = 0.0
    if strategy_std > 0 and market_std > 0:
        correlation = float(np.corrcoef(strategy, market)[0, 1])

    return {
        "annualized_alpha": annualized_alpha,
        "market_beta": beta,
        "market_correlation": correlation,
        "r_squared": correlation**2,
    }


def bootstrap_luck_p_value(
    returns: np.ndarray, *, samples: int = 500, seed: int = 42, periods_per_year: int = 252
) -> float | None:
    """Estimate the probability a null process matches the observed Sharpe."""
    clean = returns[np.isfinite(returns)]
    if clean.size < 8:
        return None
    observed = _sharpe(clean, periods_per_year)
    if observed <= 0:
        return 1.0

    centered = clean - float(np.mean(clean))
    block_length = max(2, int(sqrt(clean.size)))
    random = np.random.default_rng(seed)
    exceedances = 0
    for _ in range(samples):
        sampled: list[float] = []
        while len(sampled) < clean.size:
            start = int(random.integers(0, clean.size))
            indices = (start + np.arange(block_length)) % clean.size
            sampled.extend(centered[indices].tolist())
        simulated = np.asarray(sampled[: clean.size], dtype=float)
        if _sharpe(simulated, periods_per_year) >= observed:
            exceedances += 1
    return (exceedances + 1) / (samples + 1)


def _sharpe(returns: np.ndarray, periods_per_year: int) -> float:
    standard_deviation = float(np.std(returns, ddof=1))
    mean_return = float(np.mean(returns))
    if standard_deviation == 0:
        return float("inf") if mean_return > 0 else 0.0
    return mean_return / standard_deviation * sqrt(periods_per_year)
