"""Point-in-time data lineage — immutable, timestamped data provenance.

Every data point in Oracle carries its full provenance chain:

- ``event_time``: when the real-world event occurred (exchange timestamp)
- ``published_at``: when the data was published by the source (e.g. exchange feed)
- ``available_at``: when the data was available for consumption (published + latency)
- ``ingested_at``: when Oracle ingested and persisted the data
- ``revision_id``: version identifier for revisionable data

Core invariant: no consumer can observe data whose ``available_at`` is
after the consumer's decision time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class DataProvenance:
    """Immutable provenance chain for a single data point.

    All timestamps are UTC.  Every data record in the system must
    carry a ``DataProvenance`` (or a compatible set of timestamp
    fields).
    """

    # ── Identity ────────────────────────────────────────────────────────
    record_id: str = field(default_factory=lambda: str(uuid4()))
    """Unique identifier for this specific data record."""

    revision_id: str | None = None
    """Version identifier for revisionable data (macro, earnings, …).
    None for non-revisionable data (trades, quotes)."""

    # ── Timestamps ──────────────────────────────────────────────────────
    event_time: datetime | None = None
    """Real-world event timestamp (exchange time)."""

    published_at: datetime | None = None
    """Timestamp when the data was published by the original source."""

    available_at: datetime | None = None
    """Timestamp when the data was available for consumption.
    Defaults to ``published_at`` if not set."""

    ingested_at: datetime = field(default_factory=_now)
    """Timestamp when Oracle ingested and persisted the data."""

    # ── Source attribution ──────────────────────────────────────────────
    source: str = ""
    """Source identifier (e.g. ``yfinance``, ``metaapi``, ``cme``)."""

    source_license: str = ""
    """Data license (e.g. ``CC BY 4.0``, ``commercial``, ``unknown``)."""

    provider_version: str = ""
    """Version of the provider/adapter that fetched the data."""

    # ── Data quality ────────────────────────────────────────────────────
    status: str = "normal"
    """Data quality status: ``normal``, ``duplicate``, ``gap``, ``outlier``."""

    def is_available_at(self, cutoff: datetime) -> bool:
        """Return True if this data was available by the ``cutoff`` time.

        Used for point-in-time queries::

            if not record.provenance.is_available_at(decision_time):
                raise DataNotAvailableError(record)
        """
        ref = self.available_at or self.published_at or self.ingested_at
        if ref is None:
            return False
        return ref <= cutoff

    def to_dict(self) -> dict[str, Any]:
        """Serialise to dict for storage/transport."""
        out: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out


# ── Data containers with provenance ──────────────────────────────────


@dataclass(frozen=True)
class ProvenancedRecord:
    """A data record with embedded provenance information."""

    provenance: DataProvenance
    data: dict[str, Any]


class DataLineage:
    """Raw → Normalized → Feature transformation lineage.

    Tracks every transformation applied to a raw data point so that
    the provenance can be traced back to the original source.
    """

    def __init__(self) -> None:
        self._steps: list[dict[str, Any]] = []

    def add_step(
        self,
        step_name: str,
        input_record_id: str,
        output_record_id: str,
        transform_params: dict[str, Any] | None = None,
    ) -> None:
        """Record a transformation step in the lineage."""
        self._steps.append(
            {
                "step": step_name,
                "input_id": input_record_id,
                "output_id": output_record_id,
                "params": transform_params or {},
                "timestamp": _now().isoformat(),
            }
        )

    def to_dict(self) -> list[dict[str, Any]]:
        return list(self._steps)


# ── Query guard ──────────────────────────────────────────────────────


class DataNotAvailableError(RuntimeError):
    """Raised when a query attempts to access data not yet available."""


def require_cutoff(cutoff: datetime | None = None) -> datetime:
    """Require an explicit cutoff timestamp for backtest queries.

    In research mode, falls back to current time.  In backtest mode,
    ``cutoff`` is mandatory.

    Raises:
        DataNotAvailableError: If no cutoff is provided in backtest mode.
    """
    if cutoff is not None:
        return cutoff
    # In research/analysis, use current time as cutoff
    return _now()
