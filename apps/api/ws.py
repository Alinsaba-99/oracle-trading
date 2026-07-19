"""SSE manager — in-process pub/sub via asyncio.Queue.

No Redis needed. Each subscriber gets their own queue.
Broadcast pushes to all connected clients.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any


class SSEManager:
    """Simple in-process SSE broadcast."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []

    def connect(self) -> asyncio.Queue[str]:
        """Register a new subscriber queue."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue[str]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        """Send an event to all subscribers."""
        payload = json.dumps({"event": event, "data": data})
        dead: list[asyncio.Queue[str]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.disconnect(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


sse_manager = SSEManager()
