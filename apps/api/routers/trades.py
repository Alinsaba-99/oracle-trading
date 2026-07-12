from fastapi import APIRouter, Query

router = APIRouter(prefix="/trades", tags=["trades"])

@router.get("")
async def list_trades(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset: str | None = None,  # noqa: ARG001
    side: str | None = None,  # noqa: ARG001
    from_: str | None = Query(None, alias="from"),  # noqa: ARG001
    to: str | None = None,  # noqa: ARG001
):
    """List trades with pagination and filters."""
    # TODO: read from experiments.db
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/export")
async def export_trades(format: str = "csv"):  # noqa: ARG001
    """Export trades as CSV."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("timestamp,asset,side,qty,price,pnl\n", media_type="text/csv")


@router.get("/positions")
async def get_positions():
    """Return open positions."""
    return []
