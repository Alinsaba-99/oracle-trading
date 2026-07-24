"""Immutable audit export — tamper-evident trade and decision log.

Every decision, order, fill, and ledger update is recorded as an
immutable audit entry.  Entries are hashed in a chain so that
tampering with any entry breaks the chain hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AuditEntry:
    """A single immutable audit entry."""

    entry_id: str = ""
    trace_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    previous_hash: str = ""
    hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry (including previous_hash)."""
        content = json.dumps(
            {
                "entry_id": self.entry_id,
                "trace_id": self.trace_id,
                "event_type": self.event_type,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify this entry's hash matches its content."""
        return self.hash == self.compute_hash()


class AuditTrail:
    """Immutable chain of audit entries.

    Usage::

        audit = AuditTrail()
        audit.record("order.created", {"order_id": "123", "qty": 2})
        audit.record("order.filled", {"order_id": "123", "price": 5500})
        assert audit.verify_chain()  # True if no tampering
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._last_hash: str = ""

    def record(
        self, event_type: str, payload: dict[str, Any], trace_id: str = "", entry_id: str = ""
    ) -> AuditEntry:
        """Record an audit entry.

        Args:
            event_type: Type of event (order.created, order.filled, etc.)
            payload: Event data.
            trace_id: Trace ID for correlation.
            entry_id: Optional entry ID (auto-generated if empty).

        Returns:
            The created AuditEntry.
        """
        import uuid

        entry = AuditEntry(
            entry_id=entry_id or str(uuid.uuid4()),
            trace_id=trace_id,
            event_type=event_type,
            payload=payload,
            previous_hash=self._last_hash,
        )
        entry.hash = entry.compute_hash()
        self._entries.append(entry)
        self._last_hash = entry.hash
        return entry

    def verify_chain(self) -> bool:
        """Verify the entire chain of audit entries.

        Returns:
            True if all entries are valid and chain is intact.
        """
        prev_hash = ""
        for entry in self._entries:
            if entry.previous_hash != prev_hash:
                return False
            if not entry.verify():
                return False
            prev_hash = entry.hash
        return True

    def find_by_trace_id(self, trace_id: str) -> list[AuditEntry]:
        """Find all entries belonging to a trace."""
        return [e for e in self._entries if e.trace_id == trace_id]

    def find_by_event_type(self, event_type: str) -> list[AuditEntry]:
        """Find all entries of a specific event type."""
        return [e for e in self._entries if e.event_type == event_type]

    def export_json(self, path: str) -> None:
        """Export all entries as a JSON file."""
        import json

        data = []
        for entry in self._entries:
            data.append(
                {
                    "entry_id": entry.entry_id,
                    "trace_id": entry.trace_id,
                    "event_type": entry.event_type,
                    "payload": entry.payload,
                    "timestamp": entry.timestamp,
                    "previous_hash": entry.previous_hash,
                    "hash": entry.hash,
                }
            )

        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        self._entries.clear()
        self._last_hash = ""

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        return self._last_hash
