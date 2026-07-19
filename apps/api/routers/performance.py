"""Performance metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from apps.api.services.checkpoint_reader import get_equity_curve, get_latest_run_summary

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/summary")
async def get_summary() -> dict[str, object]:
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
async def get_equity() -> JSONResponse:
    """Return equity curve.

    Returns 503 when no equity data has been persisted yet.
    """
    points = get_equity_curve()
    if not points:
        return JSONResponse(
            status_code=503, content={"detail": "Equity curve not yet persisted.", "points": []}
        )
    return JSONResponse(status_code=200, content={"points": points})


@router.get("/today")
async def get_today() -> JSONResponse:
    """Return today's trade summary.

    Returns 503 when live trade data is not yet wired.
    """
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Live trade ingestion not yet implemented.",
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "profit_factor": 0.0,
            "pnl": 0.0,
        },
    )
