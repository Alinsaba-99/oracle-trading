"""Volatility target — systematic position sizing from risk budget.

Inspired by Rob Carver's pysystemtrade.  Computes:
  - Annual cash vol target (e.g. 25% of capital)
  - Daily cash vol target
  - Position size from forecast × vol target / current vol

This plugs into Oracle's existing RiskManager as an additional sizing
layer — it does NOT replace the risk kernel's hard limits.
"""

from __future__ import annotations

import numpy as np


def annual_cash_vol_target(capital: float, vol_pct: float = 0.25) -> float:
    """Annual cash volatility target.

    Args:
        capital: Account capital in account currency.
        vol_pct: Fraction of capital to risk per year (default 25%).

    Returns:
        Annual cash vol target.
    """
    return capital * vol_pct


def daily_cash_vol_target(capital: float, vol_pct: float = 0.25, trading_days: int = 256) -> float:
    """Daily cash volatility target.

    Args:
        capital: Account capital in account currency.
        vol_pct: Fraction of capital to risk per year.
        trading_days: Number of trading days per year.

    Returns:
        Daily cash vol target = annual_target / sqrt(trading_days).
    """
    annual = annual_cash_vol_target(capital, vol_pct)
    result: float = annual / np.sqrt(trading_days)
    return float(result)


def compute_position_from_forecast(
    forecast: float,
    daily_vol_target: float,
    current_vol: float,
    idm: float = 1.0,
    contract_size: float = 1.0,
    point_value: float = 1.0,
) -> float:
    """Compute position size from forecast, vol target, and current vol.

    Position = (forecast × daily_vol_target × IDM) / (10 × current_vol × contract_value)

    Where contract_value = contract_size × point_value.
    The division by 10 normalises for the forecast scale (avg abs = 10).

    Args:
        forecast: Combined forecast value (e.g. 3.5 from a [-10, +10] range).
        daily_vol_target: Daily cash vol target (from ``daily_cash_vol_target``).
        current_vol: Current daily volatility estimate (e.g. ATR / close).
        idm: Instrument Diversification Multiplier (1.0 to 2.5).
        contract_size: Units per contract (e.g. 1 for MES).
        point_value: $ per point (e.g. 5 for MES, 50 for ES).

    Returns:
        Fractional position size (can be < 1 for small accounts).
    """
    contract_value = contract_size * point_value
    if contract_value <= 0 or current_vol <= 0:
        return 0.0
    raw_pos = forecast * daily_vol_target * idm / (10.0 * current_vol * contract_value)
    return max(0.0, float(raw_pos))


def estimate_current_vol(close_prices: np.ndarray, span: int = 20) -> float:
    """Estimate current daily volatility from close prices using EWMA.

    Uses exponentially-weighted standard deviation of daily returns,
    which responds more quickly to changing volatility than a simple
    rolling standard deviation.

    Args:
        close_prices: Array of daily close prices.
        span: EWMA span (default 20 days, Carver's standard).

    Returns:
        Current daily vol estimate as a fraction of price.
    """
    if len(close_prices) < 2:
        return 0.0
    returns = np.diff(close_prices) / close_prices[:-1]
    if len(returns) < span:
        return float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    # EWMA of squared returns (similar to RiskMetrics)
    weights = np.exp(-np.arange(len(returns)) / span)
    weights = weights[::-1] / weights.sum()  # more weight on recent
    weighted_var = np.average(returns**2, weights=weights[-len(returns) :])
    return float(np.sqrt(weighted_var))


__all__ = [
    "annual_cash_vol_target",
    "compute_position_from_forecast",
    "daily_cash_vol_target",
    "estimate_current_vol",
]
