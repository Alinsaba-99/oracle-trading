"""NATS event bus client."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from nats import NATS  # type: ignore[attr-defined]
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription
from nats.js import JetStreamContext

from core.config.settings import NATSSettings
from core.errors.nats_errors import NATSConnectionError
from core.events.envelope import build_envelope
from core.events.system import SYSTEM_HEALTH, HealthEventPayload


class EventBusClient:
    """Client for publishing and subscribing to NATS events.

    Usage::

        client = EventBusClient(settings.nats)
        await client.connect()
        await client.publish("market.tick", {...})
        await client.close()
    """

    def __init__(self, settings: NATSSettings) -> None:
        self._settings = settings
        self._nc: NATS | None = None
        self._js: JetStreamContext | None = None

    async def connect(self) -> None:
        """Connect to NATS and publish a ``system.health`` event."""
        nc = NATS()
        try:
            await nc.connect(
                servers=[self._settings.url],
                connect_timeout=int(self._settings.timeout),
                max_reconnect_attempts=self._settings.max_reconnect,
            )
        except Exception as exc:
            raise NATSConnectionError(f"Failed to connect to NATS: {exc}") from exc

        self._nc = nc
        self._js = nc.jetstream()

        # Publish system.health to signal readiness
        health_payload = HealthEventPayload(status="healthy", components={"nats": "connected"})
        await self.publish(
            SYSTEM_HEALTH, health_payload.model_dump(mode="json"), source="oracle.core.events"
        )

    async def close(self) -> None:
        """Close the NATS connection."""
        if self._nc is not None:
            await self._nc.close()
            self._nc = None
            self._js = None

    async def publish(self, subject: str, data: dict[str, Any], **kwargs: Any) -> None:
        """Publish an event to NATS.

        Raises:
            NATSConnectionError: When not connected.
        """
        if self._nc is None:
            raise NATSConnectionError("Not connected")

        envelope = build_envelope(
            subject=subject,
            data=data,
            source=kwargs.get("source", "oracle"),
            version=kwargs.get("version", 1),
            trace_id=kwargs.get("trace_id"),
        )
        await self._nc.publish(subject, json.dumps(envelope).encode("utf-8"))

    async def subscribe(
        self, subject: str, handler: Callable[[Msg], Any], queue: str | None = None
    ) -> Subscription | None:
        """Subscribe to a NATS subject with an optional queue group.

        Raises:
            NATSConnectionError: When not connected.
        """
        if self._nc is None:
            raise NATSConnectionError("Not connected")

        return await self._nc.subscribe(subject, queue=queue or "", cb=handler)
