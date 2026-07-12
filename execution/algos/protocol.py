"""Execution algo protocol — structural typing contract."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Protocol

from execution.market_data import MarketDataSnapshot
from execution.order_manager.types import FillReport


class ExecutionAlgo(Protocol):
    """Protocol for execution algorithms (VWAP, TWAP, Iceberg, etc.)."""

    async def execute(
        self, order: Any, market_data: MarketDataSnapshot
    ) -> AsyncGenerator[FillReport, None]: ...
