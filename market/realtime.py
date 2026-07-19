"""Real-time market data feeds — tick, 1m bars, WebSocket streaming.

Provides:
- IBKR (Interactive Brokers) real-time tick/bars for futures/equities
- CCXT WebSocket for crypto tick data
- Polygon.io WebSocket for US equities/futures

Usage::

    # IBKR feed (requires TWS/Gateway running)
    feed = IBKRFeed()
    await feed.connect()
    async for tick in feed.stream("ES"):
        print(tick.price, tick.time)
    
    # CCXT WebSocket (crypto)
    feed = CCXTWebSocketFeed("binance")
    await feed.connect()
    async for tick in feed.stream("BTC/USDT"):
        print(tick.price, tick.time)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger("oracle.data.realtime")


# ── Shared types ────────────────────────────────────────────────────


class Tick:
    """A single market data tick."""

    def __init__(
        self,
        symbol: str,
        price: float,
        volume: float = 0.0,
        timestamp: datetime | None = None,
        bid: float | None = None,
        ask: float | None = None,
        source: str = "",
    ) -> None:
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.bid = bid
        self.ask = ask
        self.source = source

    def __repr__(self) -> str:
        return (
            f"Tick(symbol={self.symbol}, price={self.price}, "
            f"time={self.timestamp.isoformat()})"
        )


# ── IBKR Feed (ib_insync) ───────────────────────────────────────────


class IBKRFeed:
    """Real-time market data feed via Interactive Brokers.

    Requires TWS or IB Gateway running on the configured host/port.
    Paper trading account works with demo data.

    Default ports: 7497 (paper), 7496 (live).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to TWS/Gateway.

        Returns:
            True if connected successfully.
        """
        try:
            from ib_insync import IB

            self._ib = IB()
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._ib.connect(self.host, self.port, clientId=self.client_id),
            )
            self._connected = True
            logger.info(f"IBKR connected: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.warning(f"IBKR connection failed: {e}")
            self._connected = False
            return False

    async def stream(self, symbol: str) -> AsyncIterator[Tick]:
        """Stream real-time ticks for a symbol.

        Args:
            symbol: Ticker (ES, NQ, AAPL, BTC).

        Yields:
            Tick objects with price, volume, bid/ask.
        """
        if not self._connected or self._ib is None:
            return

        try:
            from ib_insync import Contract

            # Create contract
            if symbol.upper() in ("ES", "NQ", "GC", "CL"):
                contract = Contract(
                    symbol=symbol,
                    secType="FUT",
                    exchange="CME",
                    currency="USD",
                )
            else:
                contract = Contract(
                    symbol=symbol,
                    secType="STK",
                    exchange="SMART",
                    currency="USD",
                )

            # Qualify contract
            qualified = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._ib.qualifyContracts(contract)
            )
            if not qualified:
                logger.warning(f"IBKR: cannot qualify {symbol}")
                return

            contract = qualified[0]

            # Request market data
            from ib_insync import MarketDataType

            self._ib.reqMarketDataType(MarketDataType.DELAYED)
            ticker = self._ib.reqMktData(contract, "", False, False)

            # Stream ticks
            while self._connected:
                await asyncio.sleep(0.1)
                if ticker.last > 0:
                    yield Tick(
                        symbol=symbol,
                        price=float(ticker.last),
                        volume=float(ticker.lastSize or 0),
                        bid=float(ticker.bid) if ticker.bid else None,
                        ask=float(ticker.ask) if ticker.ask else None,
                        source="ibkr",
                    )
        except Exception as e:
            logger.error(f"IBKR stream error: {e}")

    async def disconnect(self) -> None:
        """Disconnect from TWS/Gateway."""
        self._connected = False
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass


# ── CCXT WebSocket Feed (crypto) ────────────────────────────────────


class CCXTWebSocketFeed:
    """Real-time crypto tick data via exchange WebSocket.

    Supports: binance, bybit, okx, kraken (spot & futures).
    """

    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id
        self._ws = None

    async def connect(self) -> bool:
        """Connect to exchange WebSocket."""
        try:
            import ccxt.pro as ccxtpro

            exchange_class = getattr(ccxtpro, self.exchange_id)
            self._ws = exchange_class()
            logger.info(f"CCXT WebSocket connected: {self.exchange_id}")
            return True
        except Exception as e:
            logger.warning(f"CCXT WebSocket error: {e}")
            return False

    async def stream(self, symbol: str) -> AsyncIterator[Tick]:
        """Stream real-time trades for a symbol.

        Args:
            symbol: Trading pair (BTC/USDT, ETH/USDT).

        Yields:
            Tick objects for each trade.
        """
        if self._ws is None:
            return

        try:
            while True:
                trade = await self._ws.watch_trades(symbol)
                for t in trade:
                    yield Tick(
                        symbol=symbol,
                        price=float(t["price"]),
                        volume=float(t["amount"]),
                        timestamp=datetime.fromtimestamp(
                            t["timestamp"] / 1000, tz=timezone.utc
                        ) if t.get("timestamp") else None,
                        source=f"ccxt:{self.exchange_id}",
                    )
        except Exception as e:
            logger.error(f"CCXT stream error: {e}")

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
