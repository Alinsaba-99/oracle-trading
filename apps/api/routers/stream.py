"""SSE endpoints — EventSourceResponse from sse-starlette (standard SSE)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/positions")
async def stream_positions(request: Request) -> EventSourceResponse:
    """SSE endpoint for real-time position updates.

    Uses sse-starlette's EventSourceResponse, which handles the SSE
    protocol (heartbeat pings, client disconnect detection, retry hints)
    instead of a hand-rolled StreamingResponse loop.
    """
    from apps.api.ws import sse_manager

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        queue = sse_manager.connect()
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield {"data": data}
        finally:
            sse_manager.disconnect(queue)

    return EventSourceResponse(event_generator())
