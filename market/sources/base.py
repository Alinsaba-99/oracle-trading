"""Base source ABC for market data ingestion.

All market data sources inherit from :class:`BaseSource` and implement
the connection lifecycle and the subscribe/unsubscribe protocol.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class BaseSource(ABC):
    """Abstract base for a market data source.

    Concrete subclasses implement :meth:`connect`, :meth:`disconnect`,
    :meth:`subscribe`, and :meth:`unsubscribe`. Incoming data is placed
    on :attr:`events` as raw ``dict`` values that a downstream normalizer
    converts to typed events.
    """

    def __init__(self, name: str, instrument_ids: list[str] | None = None) -> None:
        self.name = name
        self.instrument_ids: list[str] = instrument_ids or []
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @abstractmethod
    async def connect(self) -> None:
        """Open a connection to the remote data source."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection and release resources."""
        ...

    @abstractmethod
    async def subscribe(self, instrument_ids: list[str]) -> None:
        """Subscribe to one or more instrument data streams.

        Args:
            instrument_ids: Symbols or identifiers to subscribe to.
        """
        ...

    @abstractmethod
    async def unsubscribe(self, instrument_ids: list[str]) -> None:
        """Unsubscribe from one or more instrument data streams.

        Args:
            instrument_ids: Symbols or identifiers to unsubscribe from.
        """
        ...
