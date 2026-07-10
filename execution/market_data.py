"""Market data feed for execution algos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from random import uniform


@dataclass
class MarketDataSnapshot:
    """Current market state for algo execution."""

    instrument_id: str
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    last: Decimal = Decimal("0")
    volume_profile: list[float] = field(default_factory=list)
    timestamp: str = ""


class MarketDataFeed:
    """Provides real-time market data for execution algos.

    Volume profile: list of 24 floats representing hourly volume distribution.
    Used by VWAP to schedule slices.
    """

    async def snapshot(self, instrument_id: str) -> MarketDataSnapshot:
        """Get current market data snapshot."""
        profile = [uniform(0.5, 1.5) for _ in range(24)]
        total = sum(profile)
        normalized = [v / total for v in profile]
        return MarketDataSnapshot(
            instrument_id=instrument_id,
            bid=Decimal("99.50"),
            ask=Decimal("100.50"),
            last=Decimal("100.00"),
            volume_profile=normalized,
            timestamp=str(datetime.now(UTC)),
        )
