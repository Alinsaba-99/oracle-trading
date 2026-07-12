"""Performance metrics endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from apps.api.services.checkpoint_reader import (
    get_equity_curve,
    get_latest_run_summary,
)

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary")
async def get_summary():
    """Return performance metrics from latest GA run."""
    summary = get_latest_run_summary()
    if summary is None:
        return {
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "cagr": 0.0,
            "total_return": 0.0,
            "run_id": "",
            "run_seed": 0,
            "run_generations": 0,
        }
    return summary


@router.get("/equity")
async def get_equity():
    """Return equity curve (currently placeholder)."""
    return {"points": get_equity_curve()}


@router.get("/today")
async def get_today():
    """Return today's trade summary."""
    return {"trades": 0, "wins": 0, "losses": 0, "profit_factor": 0.0, "pnl": 0.0}
