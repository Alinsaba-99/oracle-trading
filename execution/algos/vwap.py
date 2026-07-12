"""VWAP execution algo — slices order according to volume profile."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from execution.algos.scheduler import AlgoScheduler
from execution.order_manager.types import FillReport


class VWAPAlgo:
    """VWAP execution: slices order according to volume profile."""

    def __init__(self, n_slices: int = 12) -> None:
        self._n_slices = n_slices
        self._scheduler = AlgoScheduler()

    async def execute(self, order: Any, market_data: Any) -> AsyncGenerator[FillReport, None]:
        """Execute order sliced by volume profile."""
        slices = self._scheduler.volume_slices(
            order.quantity, market_data.volume_profile, self._n_slices
        )
        delay = 3600 / max(len(slices), 1)
        for qty in slices:
            if qty <= 0:
                continue
            price = (market_data.bid + market_data.ask) / 2
            yield FillReport(
                order_id="",
                broker_order_id="",
                fill_id=str(uuid4()),
                quantity=qty,
                price=price,
                filled_at=str(datetime.now(UTC)),
            )
            await asyncio.sleep(delay)
