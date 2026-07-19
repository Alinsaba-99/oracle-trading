"""Trade and position endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from apps.api.services.trade_service import list_trades

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def get_trades(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    engine: str | None = None,
    fold: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
) -> dict[str, object]:
    """List trade-like records from experiments.db."""
    result = list_trades(
        limit=limit, offset=offset, engine=engine, fold=fold, from_date=from_, to_date=to
    )
    return result


@router.get("/export")
async def export_trades(
    format: str = "csv",  # noqa: ARG001
    engine: str | None = None,
    fold: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
) -> PlainTextResponse:
    """Export filtered trades as CSV with proper quoting."""
    import csv
    import io

    result = list_trades(limit=10000, engine=engine, fold=fold, from_date=from_, to_date=to)

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(["time", "experiment_id", "fold", "engine", "total_return", "sharpe_ratio"])
    for item in result["items"]:
        writer.writerow(
            [
                item["time"],
                item["experiment_id"],
                item["fold"],
                item["engine"],
                item["total_return"],
                item["sharpe_ratio"],
            ]
        )

    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@router.get("/positions")
async def get_positions() -> JSONResponse:
    """Return open positions.

    Returns 503 when live position tracking is not yet wired.
    """
    return JSONResponse(
        status_code=503, content={"detail": "Live position tracking not yet implemented."}
    )
