"""Pydantic models for API responses."""
from __future__ import annotations

from pydantic import BaseModel


class PerformanceSummary(BaseModel):
    """Aggregate performance metrics."""
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    profit_factor: float
    cagr: float
    total_return: float

    model_config = {"from_attributes": True}


class EquityPoint(BaseModel):
    """Single point on the equity curve."""
    date: str
    equity: float
    drawdown: float

    model_config = {"from_attributes": True}


class EquityCurve(BaseModel):
    """Full equity curve."""
    points: list[EquityPoint]

    model_config = {"from_attributes": True}


class TradeModel(BaseModel):
    """Trade record."""
    time: str
    asset: str
    side: str
    qty: float
    price: float
    pnl: float
    status: str
    trade_id: str

    model_config = {"from_attributes": True}


class TradeList(BaseModel):
    """Paginated trade list."""
    items: list[TradeModel]
    total: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}


class PositionModel(BaseModel):
    """Open position."""
    asset: str
    side: str
    qty: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float

    model_config = {"from_attributes": True}


class GARunSummary(BaseModel):
    """Genetic algorithm run summary."""
    run_id: str
    seed: int
    generations: int
    status: str
    timing_s: float

    model_config = {"from_attributes": True}


class GARunDetail(BaseModel):
    """Detailed GA run with Pareto front and convergence."""
    run_id: str
    seed: int
    status: str
    pareto_front: list
    convergence: list
    best_params: dict

    model_config = {"from_attributes": True}
