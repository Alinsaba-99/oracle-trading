from fastapi import APIRouter

router = APIRouter(prefix="/performance", tags=["performance"])

@router.get("/summary")
async def get_summary():
    """Return current performance metrics."""
    # TODO: read from latest checkpoint or BacktestResult
    return {
        "sharpe": 1.24,
        "sortino": 0.89,
        "calmar": 1.67,
        "max_drawdown": 0.123,
        "profit_factor": 1.50,
        "cagr": 0.086,
        "total_return": 0.29,
    }

@router.get("/equity")
async def get_equity():
    """Return equity curve data."""
    # TODO: read from latest checkpoint
    return {"points": []}

@router.get("/today")
async def get_today():
    """Return today's trade summary."""
    return {"trades": 0, "wins": 0, "losses": 0, "profit_factor": 0.0, "pnl": 0.0}
