from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/positions")
async def stream_positions(request: Request):
    """SSE endpoint for real-time position updates."""
    from apps.api.ws import sse_manager

    async def event_generator():
        queue = sse_manager.connect()
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            sse_manager.disconnect(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
