"""Recompute BacktestResult metrics from the equity curve.

vectorbt's ``Sharpe Ratio`` (and friends) frequently return ``0.0`` when
it cannot infer the bar frequency — every Fase 6 sweep showed ``sharpe=0.0``
even for clearly profitable strategies.  This module overrides those
fields by recomputing them from the equity curve via our own
:class:`MetricsCalculator` (Polars-native, no frequency-inference
dependency), so strategy ranking reflects reality.

The per-bar returns are used as the P&L series for profit-factor /
win-rate — a close approximation for ranking; trade-level accuracy would
need the trade log (not populated by the sized backtest).
"""

from __future__ import annotations

import polars as pl

from analytics.backtest.metrics import MetricsCalculator
from analytics.backtest.result import BacktestResult


def recompute_metrics(result: BacktestResult) -> BacktestResult:
    """Return a copy of *result* with metrics recomputed from its equity curve."""
    eq = pl.Series("equity", result.equity_curve)
    if eq.len() < 2:
        return result

    returns = eq.pct_change().drop_nulls()
    maxdd = MetricsCalculator.max_drawdown(eq)

    return result.model_copy(
        update={
            "sharpe_ratio": MetricsCalculator.sharpe_ratio(returns),
            "sortino_ratio": MetricsCalculator.sortino_ratio(returns),
            "calmar_ratio": MetricsCalculator.calmar_ratio(returns, maxdd),
            "max_drawdown": maxdd,
            "volatility": MetricsCalculator.volatility(returns),
            "cagr": MetricsCalculator.cagr(eq),
            "total_return": MetricsCalculator.total_return(eq),
            "profit_factor": MetricsCalculator.profit_factor(returns),
            "win_rate": MetricsCalculator.win_rate(returns),
        }
    )
