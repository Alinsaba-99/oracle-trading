"""Backtest performance metrics — Polars-native implementations."""

from __future__ import annotations

from typing import Any

import polars as pl


def _to_float(val: Any) -> float:
    """Safely cast a Polars scalar return value to float."""
    if val is None:
        return 0.0
    return float(val)


class MetricsCalculator:
    """Calculator for common backtest performance metrics.

    All methods use Polars-native operations; no external dependencies
    such as quantstats are required.
    """

    @staticmethod
    def sharpe_ratio(returns: pl.Series, annualization_factor: int = 252) -> float:
        """Compute the annualised Sharpe ratio from a return series.

        Args:
            returns: Series of periodic (e.g. daily) returns.
            annualization_factor: Number of periods per year (default 252
                for daily data).

        Returns:
            The annualised Sharpe ratio. Returns infinity for constant
            positive returns, -infinity for constant negative returns,
            and 0.0 if there are fewer than 2 observations or returns
            are constant-zero.
        """
        if len(returns) < 2:
            return 0.0
        polars_std = returns.std()
        if polars_std is None:
            return 0.0
        mean = _to_float(returns.mean())
        std = _to_float(polars_std)
        if std == 0.0:
            if mean > 0:
                return float("inf")
            if mean < 0:
                return float("-inf")
            return 0.0
        return mean / std * (annualization_factor**0.5)  # type: ignore[no-any-return]

    @staticmethod
    def sortino_ratio(returns: pl.Series, annualization_factor: int = 252) -> float:
        """Compute the annualised Sortino ratio from a return series.

        The Sortino ratio uses only downside deviation (negative returns)
        instead of total standard deviation.

        Args:
            returns: Series of periodic returns.
            annualization_factor: Number of periods per year (default 252).

        Returns:
            The annualised Sortino ratio. Returns infinity if there are
            no negative returns, and 0.0 if there are fewer than 2
            observations.
        """
        if len(returns) < 2:
            return 0.0
        mean = _to_float(returns.mean())
        negative = returns.filter(returns < 0)
        if len(negative) < 1:
            return float("inf")
        polars_ds = negative.std()
        if polars_ds is None:
            if mean > 0:
                return float("inf")
            if mean < 0:
                return float("-inf")
            return 0.0
        ds = _to_float(polars_ds)
        if ds == 0.0:
            if mean > 0:
                return float("inf")
            if mean < 0:
                return float("-inf")
            return 0.0
        return mean / ds * (annualization_factor**0.5)  # type: ignore[no-any-return]

    @staticmethod
    def calmar_ratio(returns: pl.Series, max_drawdown: float | None = None) -> float:
        """Compute the Calmar ratio (annualised return / max drawdown).

        Args:
            returns: Series of periodic returns.
            max_drawdown: Pre-computed max drawdown (positive, e.g. 0.25
                for 25 % drawdown). If None, it is calculated from the
                equity curve implied by cumulative returns.

        Returns:
            The Calmar ratio, or 0.0 if the max drawdown is zero or there
            are fewer than 2 observations.
        """
        if len(returns) < 2:
            return 0.0
        total_ret = _to_float(returns.sum())
        n = len(returns)
        ann_return = total_ret / n * 252

        if max_drawdown is None:
            equity = (1 + returns).cum_prod()
            running_max = equity.cum_max()
            drawdown = (equity - running_max) / running_max
            max_drawdown = _to_float(-drawdown.min())  # type: ignore[operator]

        if max_drawdown == 0.0:
            return 0.0
        return ann_return / max_drawdown

    @staticmethod
    def max_drawdown(equity: pl.Series) -> float:
        """Compute the maximum drawdown from an equity curve.

        Args:
            equity: Series of equity values (e.g. cumulative portfolio
                values).

        Returns:
            The maximum drawdown as a positive decimal (e.g. 0.25 for
            25 % peak-to-trough decline).
        """
        if len(equity) < 2:
            return 0.0
        running_max = equity.cum_max()
        drawdown = (equity - running_max) / running_max
        return _to_float(-drawdown.min())  # type: ignore[operator]
