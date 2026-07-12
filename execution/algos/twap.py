"""TWAP execution algo — slices order across equal time intervals."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from execution.algos.scheduler import AlgoScheduler
from execution.order_manager.types import FillReport


class TWAPAlgo:
    """TWAP execution: slices order across equal time intervals."""

    def __init__(self, n_slices: int = 12) -> None:
        self._n_slices = n_slices
        self._scheduler = AlgoScheduler()

    async def execute(self, order: Any, market_data: Any) -> AsyncGenerator[FillReport, None]:
        """Execute order sliced by equal time intervals."""
        slices = self._scheduler.time_slices(3600, self._n_slices)
        qty_per_slice = order.quantity / max(len(slices), 1)
        for delay_sec in slices:
            yield FillReport(
                order_id="",
                broker_order_id="",
                fill_id=str(uuid4()),
                quantity=qty_per_slice,
                price=market_data.last,
                filled_at=str(datetime.now(UTC)),
            )
            await asyncio.sleep(delay_sec / self._n_slices if delay_sec else 1)
