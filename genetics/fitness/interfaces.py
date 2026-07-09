"""External interface contracts for the GA fitness evaluator.

This reference file documents the exact signatures of external types
used by the fitness module.  All methods are stateless — safe for
multiprocessing workers.
"""

# mypy: ignore-errors

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

import polars as pl
from pydantic import BaseModel, Field

from core.domain.trade import Trade

# ---------------------------------------------------------------------------
# BacktestConfig — Pydantic model, serializable
# ---------------------------------------------------------------------------


class BacktestConfig(BaseModel):
    """Configuration for a single vectorized backtest run."""

    engine: str = "vectorized"
    slippage_bps: float = Field(default=5.0, ge=0)
    commission_pct: float = Field(default=0.001, ge=0, le=1)
    initial_capital: Decimal = Decimal("100000")

    def to_settings(self) -> dict[str, float | str | int]:
        ...


# ---------------------------------------------------------------------------
# BacktestResult — Pydantic model returned by every run
# ---------------------------------------------------------------------------


class BacktestResult(BaseModel):
    """Metrics container returned by the backtest engine."""

    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    cagr: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    initial_capital: Decimal = Decimal("100000")
    final_equity: float = 0.0
    equity_curve: list[float] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        ...

    @staticmethod
    def from_metrics(
        run_id: str = "",
        strategy_name: str = "",
        instrument: str = "",
        start_time: Any = None,
        end_time: Any = None,
        total_return: float = 0.0,
        sharpe_ratio: float = 0.0,
        sortino_ratio: float = 0.0,
        calmar_ratio: float = 0.0,
        max_drawdown: float = 0.0,
        volatility: float = 0.0,
        cagr: float = 0.0,
        total_trades: int = 0,
        win_rate: float = 0.0,
        profit_factor: float = 0.0,
        avg_win: float = 0.0,
        avg_loss: float = 0.0,
        initial_capital: Decimal = Decimal("100000"),
        final_equity: float = 0.0,
        equity_curve: list[float] | None = None,
        trades: list[Trade] | None = None,
    ) -> BacktestResult:
        ...


# ---------------------------------------------------------------------------
# BacktestSignal — structural typing protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BacktestSignal(Protocol):
    """Protocol for any signal function usable by the backtest engines."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Return -1, 0, or 1 for each row in *data*."""
        ...


# ---------------------------------------------------------------------------
# MetricsCalculator — stateless static methods
# ---------------------------------------------------------------------------


class MetricsCalculator:
    """Pure-method namespace for computing performance metrics."""

    @staticmethod
    def sharpe_ratio(returns: pl.Series, annualization_factor: int = 252) -> float: ...

    @staticmethod
    def sortino_ratio(returns: pl.Series, annualization_factor: int = 252) -> float: ...

    @staticmethod
    def calmar_ratio(returns: pl.Series, max_drawdown: float | None = None) -> float: ...

    @staticmethod
    def max_drawdown(equity: pl.Series) -> float: ...


# ---------------------------------------------------------------------------
# WalkForwardEngine — stateful, but the evaluator only calls run + metrics
# ---------------------------------------------------------------------------


class WalkForwardEngine:
    """Walk-forward validation engine using Combinatorial Purged CV."""

    def __init__(
        self,
        registry: Any = None,
        parent_experiment_id: str | None = None,
    ) -> None:
        ...

    def run(
        self,
        data: pl.DataFrame,
        signal: BacktestSignal,
        settings: BacktestConfig | None = None,
        n_splits: int = 5,
        n_test_splits: int = 1,
        purge_window: int = 5,
    ) -> list[BacktestResult]:
        """Return one BacktestResult per fold (out-of-sample test set)."""
        ...

    def combined_metrics(self) -> dict[str, Any]:
        """Aggregate metrics across folds as ``{metric_mean, metric_std, n_folds}``."""
        ...


# ---------------------------------------------------------------------------
# VectorizedEngine — single-fold backtest engine
# ---------------------------------------------------------------------------


class VectorizedEngine:
    """Single-fold vectorized backtest engine wrapping vectorbt."""

    def __init__(self) -> None:
        ...

    def run(
        self,
        data: pl.DataFrame,
        signal: BacktestSignal,
        settings: BacktestConfig | None = None,
    ) -> BacktestResult:
        ...
