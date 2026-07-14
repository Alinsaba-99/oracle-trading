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

    @staticmethod
    def total_return(equity: pl.Series) -> float:
        """Compute total return from an equity curve.

        Args:
            equity: Series of equity values (first element = initial capital).

        Returns:
            Total return as a decimal (e.g. 0.15 for +15%). Returns 0.0
            if there are fewer than 2 observations or the initial value
            is zero.
        """
        if len(equity) < 2:
            return 0.0
        initial = _to_float(equity[0])
        if initial == 0.0:
            return 0.0
        final = _to_float(equity[-1])
        return (final - initial) / initial

    @staticmethod
    def volatility(returns: pl.Series, annualization_factor: int = 252) -> float:
        """Compute annualised volatility (std-dev of returns).

        Args:
            returns: Series of periodic returns.
            annualization_factor: Number of periods per year (default 252).

        Returns:
            Annualised standard deviation of returns, or 0.0 if there are
            fewer than 2 observations.
        """
        if len(returns) < 2:
            return 0.0
        polars_std = returns.std()
        if polars_std is None:
            return 0.0
        return _to_float(polars_std) * (annualization_factor**0.5)  # type: ignore[no-any-return]

    @staticmethod
    def cagr(equity: pl.Series, periods_per_year: int = 252) -> float:
        """Compute Compound Annual Growth Rate from an equity curve.

        Args:
            equity: Series of equity values (first = initial capital).
            periods_per_year: Number of observations per year (default 252).

        Returns:
            CAGR as a decimal (e.g. 0.20 for +20%/yr). Returns -1.0 for
            total capital loss, 0.0 for fewer than 2 observations or a
            non-positive starting balance.
        """
        if len(equity) < 2:
            return 0.0
        initial = _to_float(equity[0])
        if initial <= 0.0:
            return 0.0
        final = _to_float(equity[-1])
        n = len(equity) - 1
        if final <= 0.0:
            return -1.0  # total loss of capital
        return (final / initial) ** (periods_per_year / n) - 1.0  # type: ignore[no-any-return]

    @staticmethod
    def profit_factor(returns: pl.Series) -> float:
        """Compute profit factor (gross profit / gross loss).

        Args:
            returns: Series of per-trade or per-period P&L.

        Returns:
            Gross profit divided by gross loss. Returns ``inf`` when there
            are no losing periods, and 0.0 when there are no profits.
        """
        if len(returns) == 0:
            return 0.0
        gains = returns.filter(returns > 0)
        losses = returns.filter(returns < 0)
        gross_profit = _to_float(gains.sum()) if len(gains) > 0 else 0.0
        gross_loss = _to_float((-losses).sum()) if len(losses) > 0 else 0.0
        if gross_loss == 0.0:
            return float("inf") if gross_profit > 0.0 else 0.0
        return gross_profit / gross_loss

    @staticmethod
    def win_rate(returns: pl.Series) -> float:
        """Compute win rate (fraction of strictly positive observations).

        Args:
            returns: Series of per-trade or per-period P&L.

        Returns:
            Win rate in [0, 1]. Returns 0.0 for an empty series.
        """
        n = len(returns)
        if n == 0:
            return 0.0
        wins = len(returns.filter(returns > 0))
        return wins / n

    @staticmethod
    def expectancy(returns: pl.Series) -> float:
        """Compute expectancy (mean P&L per observation).

        Args:
            returns: Series of per-trade or per-period P&L.

        Returns:
            Arithmetic mean of the series, or 0.0 if empty.
        """
        if len(returns) == 0:
            return 0.0
        return _to_float(returns.mean())

    @staticmethod
    def max_consecutive_losses(returns: pl.Series) -> int:
        """Compute the longest run of consecutive negative observations.

        Args:
            returns: Series of per-trade or per-period P&L.

        Returns:
            Length of the longest losing streak (0 if none).
        """
        worst = 0
        current = 0
        for v in returns.to_list():
            if v < 0:
                current += 1
                if current > worst:
                    worst = current
            else:
                current = 0
        return worst

    @staticmethod
    def ulcer_index(equity: pl.Series) -> float:
        """Compute the Ulcer Index (RMS of percentage drawdowns).

        Args:
            equity: Series of equity values.

        Returns:
            Root-mean-square of the percentage drawdowns, measuring both
            the depth and duration of drawdowns. Returns 0.0 if there are
            fewer than 2 observations.
        """
        if len(equity) < 2:
            return 0.0
        running_max = equity.cum_max()
        drawdown_pct = ((equity - running_max) / running_max) * 100.0
        dd_sq_mean = _to_float((drawdown_pct * drawdown_pct).mean())
        return (max(dd_sq_mean, 0.0)) ** 0.5  # type: ignore[no-any-return]
