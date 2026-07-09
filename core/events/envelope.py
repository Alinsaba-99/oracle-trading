"""Event envelope builder for NATS publishing."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def build_envelope(
    subject: str, data: dict[str, Any], source: str, version: int = 1, trace_id: str | None = None
) -> dict[str, Any]:
    """Build a standard event envelope dict for NATS publishing.

    Args:
        subject: NATS subject (e.g. ``system.health``).
        data: Event-specific payload dict.
        source: Service or plugin that emits the event.
        version: Schema version (default ``1``).
        trace_id: Optional trace ID; auto-generated as UUID4 when ``None``.

    Returns:
        Envelope dict conforming to the Oracle event schema.
    """
    return {
        "subject": subject,
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "trace_id": trace_id or str(uuid4()),
        "data": data,
    }
