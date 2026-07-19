"""Abstract base broker with exponential-back-off reconnection."""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

from core.logging import get_logger
from execution.brokers.config import BrokerConfig

logger = get_logger(__name__)


class BaseBroker(ABC):
    """Broker skeleton that every concrete broker should inherit from.

    Provides shared connect / disconnect lifecycle management and a
    reconnection loop with capped exponential back-off.
    """

    def __init__(self, config: BrokerConfig | None = None) -> None:
        self._config = config or BrokerConfig()
        self._connected = False
        self._reconnect_attempts = 0

    # ------------------------------------------------------------------
    # Subclass responsibilities
    # ------------------------------------------------------------------
    @abstractmethod
    async def _do_connect(self) -> None:
        """Perform the actual connection work (transport / handshake)."""

    @abstractmethod
    async def _do_disconnect(self) -> None:
        """Tear down the transport cleanly."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        await self._do_connect()
        self._connected = True
        self._reconnect_attempts = 0

    async def disconnect(self) -> None:
        await self._do_disconnect()
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def health(self) -> dict[str, Any]:
        return {"connected": self._connected, "reconnect_attempts": self._reconnect_attempts}

    # ------------------------------------------------------------------
    # Reconnection (exponential back-off with jitter)
    # ------------------------------------------------------------------
    async def _reconnect(self) -> None:
        """Attempt reconnection up to ``reconnect_max_retries`` times.

        Raises
        ------
        ConnectionError
            When all retries are exhausted.
        """
        for i in range(self._config.reconnect_max_retries):
            delay = min(
                self._config.reconnect_base_delay_s * (2**i) + random.uniform(0, 0.1),
                self._config.reconnect_max_delay_s,
            )
            await asyncio.sleep(delay)
            try:
                await self._do_connect()
                self._connected = True
                self._reconnect_attempts = i + 1
                return
            except Exception:
                logger.exception(
                    "Reconnection attempt %d/%d failed", i + 1, self._config.reconnect_max_retries
                )
                continue
        self._connected = False
        msg = f"Failed to reconnect after {self._config.reconnect_max_retries} attempts"
        raise ConnectionError(msg)
