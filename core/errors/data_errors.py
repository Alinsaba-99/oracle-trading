"""Data-layer error classes (ingestion, sources)."""

from __future__ import annotations

from core.errors.base import OracleError


class IngestionError(OracleError):
    """Data ingestion error.

    Canonical home moved from ``analytics.common.errors`` (P0 cycle-break:
    ``market.ingestion`` is a lower layer than analytics and must not
    import it).  ``analytics.common.errors`` re-exports this class for
    backward compatibility.
    """
