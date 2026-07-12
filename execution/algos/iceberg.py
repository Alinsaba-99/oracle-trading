"""Iceberg execution algo — shows only portion of total quantity at a time."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from execution.order_manager.types import FillReport


class IcebergAlgo:
    """Iceberg execution: shows only portion of total quantity at a time."""

    def __init__(
        self, display_size: Decimal = Decimal("100"), refresh_interval_s: float = 5.0
    ) -> None:
        self._display_size = display_size
        self._refresh = refresh_interval_s

    async def execute(self, order: Any, market_data: Any) -> AsyncGenerator[FillReport, None]:
        """Execute order in display_size chunks."""
        remaining = order.quantity
        while remaining > 0:
            qty = min(remaining, self._display_size)
            yield FillReport(
                order_id="",
                broker_order_id="",
                fill_id=str(uuid4()),
                quantity=qty,
                price=market_data.last,
                filled_at=str(datetime.now(UTC)),
            )
            remaining -= qty
            await asyncio.sleep(self._refresh)
