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


class ExperimentResult(BaseModel):
    """Fold-level backtest result from experiments.db."""
    time: str
    experiment_id: str
    fold: str
    engine: str
    total_return: float
    sharpe_ratio: float

    model_config = {"from_attributes": True}


class ExperimentList(BaseModel):
    """Paginated experiment result list."""
    items: list[ExperimentResult]
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
    pareto_front: list[dict[str, float]]
    convergence: list[dict[str, float]]
    best_params: dict[str, float]

    model_config = {"from_attributes": True}
