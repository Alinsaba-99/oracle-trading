"""Backtest result model — Pydantic, serializable to Parquet + Experiment Registry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from core.domain.trade import Trade


class BacktestResult(BaseModel):
    """Container for all outputs of a single backtest run.

    Fields mirror the standard set of performance metrics documented in
    the Phase 2 plan (F5).  The model is Pydantic-native so it can be
    serialised to Parquet and to the Experiment Registry without
    custom adapters.
    """

    # ── identification ──────────────────────────────────────────────

    run_id: str = ""
    strategy_name: str = ""
    engine: str = "vectorized"
    instrument: str = ""

    # ── time bounds ─────────────────────────────────────────────────

    start_time: datetime | None = None
    end_time: datetime | None = None

    # ── performance metrics ─────────────────────────────────────────

    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    cagr: float = 0.0

    # ── trade statistics ────────────────────────────────────────────

    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    # ── capital / curve ─────────────────────────────────────────────

    initial_capital: Decimal = Decimal("100000")
    final_equity: float = 0.0
    equity_curve: list[float] = Field(default_factory=list)

    # ── trade log ───────────────────────────────────────────────────

    trades: list[Trade] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Flat dict suitable for Experiment Registry logging."""
        return self.model_dump(mode="json")

    @staticmethod
    def from_metrics(
        *,
        run_id: str,
        strategy_name: str,
        instrument: str,
        start_time: datetime | None,
        end_time: datetime | None,
        total_return: float,
        sharpe_ratio: float,
        sortino_ratio: float,
        calmar_ratio: float,
        max_drawdown: float,
        volatility: float,
        cagr: float,
        total_trades: int,
        win_rate: float,
        profit_factor: float,
        avg_win: float,
        avg_loss: float,
        initial_capital: Decimal,
        final_equity: float,
        equity_curve: list[float],
        trades: list[Trade],
        engine: str = "vectorized",
    ) -> BacktestResult:
        """Builder-style factory for populating every field."""
        return BacktestResult(
            run_id=run_id,
            strategy_name=strategy_name,
            instrument=instrument,
            start_time=start_time,
            end_time=end_time,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            cagr=cagr,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            initial_capital=initial_capital,
            final_equity=final_equity,
            equity_curve=equity_curve,
            trades=trades,
            engine=engine,
        )
