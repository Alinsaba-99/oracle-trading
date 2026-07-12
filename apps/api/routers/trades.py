"""Trade and position endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from apps.api.services.trade_service import list_trades

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def get_trades(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset: str | None = None,
    side: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
):
    """List trades (fold experiments) with pagination."""
    result = list_trades(
        limit=limit,
        offset=offset,
        asset=asset,
        side=side,
        from_date=from_,
        to_date=to,
    )
    return result


@router.get("/export")
async def export_trades(format: str = "csv"):  # noqa: ARG001
    """Export trades as CSV."""
    result = list_trades(limit=10000)
    lines = ["time,experiment_id,fold,engine,total_return,sharpe_ratio"]
    for item in result["items"]:
        lines.append(
            f'{item["time"]},{item["experiment_id"]},{item["fold"]},'
            f'{item["engine"]},{item["total_return"]},{item["sharpe_ratio"]}'
        )
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/csv")


@router.get("/positions")
async def get_positions():
    """Return open positions (not yet persisted)."""
    return []
