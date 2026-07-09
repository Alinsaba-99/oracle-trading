"""Binance WebSocket source — real-time kline data.

Uses the public Binance WebSocket API at ``wss://stream.binance.com:9443/ws``.
No API key required.  Subscribes to ``{symbol}@kline_1m`` streams and
places parsed kline dicts on the :attr:`events` queue.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import websockets

from market.sources.base import BaseSource

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0


class BinanceWebSocketSource(BaseSource):
    """Real-time kline data via Binance WebSocket streams.

    Parameters
    ----------
    instrument_ids:
        Lowercase symbol names, e.g. ``["btcusdt", "ethusdt"]``.
        The connector will subscribe to ``{symbol}@kline_1m``.
    """

    def __init__(self, instrument_ids: list[str] | None = None) -> None:
        super().__init__(name="binance", instrument_ids=instrument_ids)
        self._ws: Any = None
        self._running = False
        self._reader_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Open the WebSocket connection and start the reader loop."""
        self._running = True
        streams = [f"{inv.lower()}@kline_1m" for inv in self.instrument_ids]
        params = "/".join(streams)
        url = f"{BINANCE_WS_URL}/{params}"
        self._ws = await websockets.connect(url)
        logger.info("Connected to Binance WebSocket (%d streams)", len(streams))
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def disconnect(self) -> None:
        """Close the WebSocket and cancel the reader task."""
        self._running = False
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        logger.info("Disconnected from Binance WebSocket")

    async def subscribe(self, instrument_ids: list[str]) -> None:
        """Subscribe to additional streams via a WebSocket JSON command.

        .. note:: Binance requires a single combined stream URL at connect
                  time.  This implementation sends a ``SUBSCRIBE`` JSON
                  message over the open connection.
        """
        if self._ws is None:
            msg = "Not connected"
            raise RuntimeError(msg)
        params = [f"{inv.lower()}@kline_1m" for inv in instrument_ids]
        payload = {"method": "SUBSCRIBE", "params": params, "id": 1}
        await self._ws.send(json.dumps(payload))
        self.instrument_ids.extend(instrument_ids)

    async def unsubscribe(self, instrument_ids: list[str]) -> None:
        """Unsubscribe from streams via a WebSocket JSON command."""
        if self._ws is None:
            return
        params = [f"{inv.lower()}@kline_1m" for inv in instrument_ids]
        payload = {"method": "UNSUBSCRIBE", "params": params, "id": 2}
        await self._ws.send(json.dumps(payload))
        self.instrument_ids = [i for i in self.instrument_ids if i not in instrument_ids]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _reader_loop(self) -> None:
        """Continuously read messages, reconnecting on failure."""
        delay = RECONNECT_BASE_DELAY
        while self._running:
            try:
                if self._ws is None:
                    await self._reconnect()
                    delay = RECONNECT_BASE_DELAY

                raw = await self._ws.recv()
                data = json.loads(raw)
                parsed = self._parse_kline(data)
                if parsed is not None:
                    await self.events.put(parsed)
                delay = RECONNECT_BASE_DELAY  # reset on success
            except websockets.ConnectionClosed:
                logger.warning("Binance WS disconnected, reconnecting in %.1fs", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
                self._ws = None
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected error in Binance reader loop")
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _reconnect(self) -> None:
        """Re-establish the WebSocket connection."""
        streams = [f"{inv.lower()}@kline_1m" for inv in self.instrument_ids]
        params = "/".join(streams)
        url = f"{BINANCE_WS_URL}/{params}"
        self._ws = await websockets.connect(url)
        logger.info("Reconnected to Binance WebSocket")

    @staticmethod
    def _parse_kline(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a Binance kline WebSocket message into a normalized dict.

        Returns ``None`` when the message is not a kline event.
        """
        if raw.get("e") != "kline":
            return None

        k = raw.get("k", {})
        return {
            "source": "binance",
            "instrument_id": raw.get("s", "").lower(),
            "event_type": "kline",
            "timestamp": k.get("t"),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "quote_volume": float(k.get("q", 0)),
            "trades": int(k.get("n", 0)),
            "taker_buy_volume": float(k.get("V", 0)),
            "taker_buy_quote_volume": float(k.get("Q", 0)),
            "is_final": k.get("x", False),
        }
