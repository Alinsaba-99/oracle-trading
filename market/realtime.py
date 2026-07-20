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
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import websockets

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


# ── Polygon.io WebSocket Feed (futures) ──────────────────────────────


class PolygonWebSocketFeed:
    """Real-time futures data via Polygon.io WebSocket.

    Provides streaming trades (T.*), quotes (Q.*), and minute-aggregates
    (A.*) for CME futures (ES, NQ, GC, CL, etc.).

    Requires ``ORACLE_DATA_POLYGON_KEY`` env var or ``polygon_key`` arg.

    Usage::

        feed = PolygonWebSocketFeed(api_key="...")
        await feed.connect()
        async for tick in feed.stream("ES"):
            print(tick.price, tick.bid, tick.ask)
    """

    # Polygon WebSocket endpoints
    WS_URL = "wss://socket.polygon.io/futures"

    # Map our root symbols to Polygon ticker format
    # Polygon futures format: {ROOT}*{MULTIPLIER} where *5 = E-mini, *1 = Micro
    TICKER_MAP: dict[str, str] = {
        "ES": "ES*5",   # E-mini S&P 500 (multipler 50)
        "MES": "ES",    # Micro E-mini (ticker ES with multiplier 1)
        "NQ": "NQ*5",   # E-mini Nasdaq 100
        "MNQ": "NQ",    # Micro E-mini Nasdaq
        "GC": "GC*5",   # Gold futures
        "MGC": "GC",    # Micro Gold
        "CL": "CL*5",   # Crude Oil
        "MCL": "CL",    # Micro Crude Oil
    }

    def __init__(
        self,
        api_key: str | None = None,
        channels: tuple[str, ...] = ("T", "Q", "A"),
    ) -> None:
        """Initialize the Polygon WebSocket feed.

        Args:
            api_key: Polygon.io API key. Falls back to ``ORACLE_DATA_POLYGON_KEY``.
            channels: Channel prefixes to subscribe to (T=trades, Q=quotes, A=aggregates).
        """
        if api_key is None:
            import os

            api_key = os.environ.get("ORACLE_DATA_POLYGON_KEY", "")
        if not api_key:
            raise ValueError(
                "Polygon API key required — set ORACLE_DATA_POLYGON_KEY or pass api_key"
            )
        self._api_key = api_key
        self._channels = channels
        self._ws: Any = None
        self._connected = False
        self._running = False

    async def connect(self) -> bool:
        """Connect to Polygon.io WebSocket and authenticate.

        Returns:
            True if connected and authenticated.
        """
        try:
            self._ws = await websockets.connect(
                self.WS_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )

            # Polygon sends a "connected" status immediately on connect.
            # Consume it before sending auth.
            import json as _json

            try:
                init_resp = await asyncio.wait_for(self._ws.recv(), timeout=5)
                init_data = _json.loads(init_resp)
                if isinstance(init_data, list) and init_data[0].get("status") == "connected":
                    logger.info(f"Polygon WebSocket: {init_data[0].get('message', 'connected')}")
            except (asyncio.TimeoutError, _json.JSONDecodeError):
                pass

            # Send authentication
            auth_msg = {"action": "auth", "params": self._api_key}
            await self._ws.send(_json.dumps(auth_msg))

            # Read auth response(s) — loop until we get auth_success or auth_failed
            deadline = asyncio.get_event_loop().time() + 10
            while asyncio.get_event_loop().time() < deadline:
                try:
                    resp = await asyncio.wait_for(self._ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning("Polygon auth timed out")
                    break

                try:
                    data = _json.loads(resp)
                except _json.JSONDecodeError:
                    continue

                if not isinstance(data, list):
                    data = [data]

                for msg in data:
                    status = msg.get("status", msg.get("ev", ""))
                    message = msg.get("message", "")
                    if status == "auth_success":
                        self._connected = True
                        self._running = True
                        logger.info("Polygon WebSocket authenticated")
                        return True
                    elif status == "auth_failed":
                        logger.warning(f"Polygon auth failed: {message}")
                        logger.warning("WebSocket requires paid Polygon plan (Basic $29/mo+)")
                        return False
                    elif status != "connected":
                        logger.debug(f"Polygon msg while waiting auth: {status}")

            return False
        except Exception as e:
            logger.warning(f"Polygon WebSocket connection failed: {e}")
            self._connected = False
            return False

    async def stream(self, symbol: str) -> AsyncIterator[Tick]:
        """Stream real-time ticks for a futures symbol.

        Args:
            symbol: Root symbol (ES, NQ, GC, CL) or micro (MES, MNQ).

        Yields:
            Tick objects with price, volume, bid, ask, timestamp.
        """
        if not self._connected or self._ws is None:
            return

        # Map symbol to Polygon ticker
        poly_ticker = self.TICKER_MAP.get(symbol.upper(), symbol.upper())

        # Subscribe to requested channels
        channels_to_sub = [f"{ch}.{poly_ticker}" for ch in self._channels]
        sub_msg = {"action": "subscribe", "params": ",".join(channels_to_sub)}
        try:
            await self._ws.send(json.dumps(sub_msg))
            logger.info(f"Polygon subscribed: {channels_to_sub}")
        except Exception as e:
            logger.error(f"Polygon subscribe failed: {e}")
            return

        # Stream messages
        while self._running and self._connected:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                logger.debug("Polygon: keepalive (no data for 30s)")
                continue
            except Exception as e:
                logger.warning(f"Polygon stream recv error: {e}")
                break

            try:
                messages = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                ev = msg.get("ev", "")
                if ev in ("T", "Q", "A"):
                    yield Tick(
                        symbol=symbol.upper(),
                        price=float(msg.get("p", 0) or msg.get("c", 0) or 0),
                        volume=float(msg.get("s", 0) or 0),
                        timestamp=datetime.fromtimestamp(
                            msg.get("t", msg.get("start", 0)) / 1000,
                            tz=timezone.utc,
                        ) if msg.get("t") or msg.get("start") else None,
                        bid=float(msg.get("bp", 0)) if msg.get("bp") else None,
                        ask=float(msg.get("ap", 0)) if msg.get("ap") else None,
                        source="polygon",
                    )

    async def rest_poll(
        self,
        symbol: str,
        interval_sec: float = 12.0,
        timespan: str = "minute",
    ) -> AsyncIterator[Tick]:
        """Fallback: poll Polygon REST API for latest prices.

        Works with free Polygon plan (5 calls/min → 12s intervals).
        Handles rate limiting (429) with exponential backoff.

        Args:
            symbol: Root symbol (ES, NQ, GC, CL).
            interval_sec: Seconds between polls (min 12 for free plan).
            timespan: Bar size (minute, hour, day).

        Yields:
            Tick objects with price from latest close.
        """
        import httpx

        poly_ticker = self.TICKER_MAP.get(symbol.upper(), symbol.upper())
        self._running = True
        last_tick: Tick | None = None
        backoff = interval_sec

        while self._running:
            try:
                url = (
                    f"https://api.polygon.io/v2/aggs/ticker/"
                    f"{poly_ticker}/prev?adjusted=true&apiKey={self._api_key}"
                )
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url)

                    if resp.status_code == 429:
                        logger.warning(f"Polygon rate limited — backing off {backoff:.0f}s")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 1.5, 60.0)  # exponential backoff, max 60s
                        continue

                    backoff = interval_sec  # reset on success

                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            bar = results[-1]
                            tick = Tick(
                                symbol=symbol.upper(),
                                price=float(bar.get("c", 0)),
                                volume=float(bar.get("v", 0)),
                                timestamp=datetime.fromtimestamp(
                                    bar["t"] / 1000, tz=timezone.utc
                                ) if "t" in bar else None,
                                bid=float(bar.get("l", 0)),
                                ask=float(bar.get("h", 0)),
                                source="polygon_rest",
                            )
                            # Only yield if price changed (avoid duplicate ticks)
                            if last_tick is None or last_tick.price != tick.price:
                                last_tick = tick
                                yield tick
            except Exception as exc:
                logger.debug(f"Polygon REST poll error: {exc}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 60.0)
                continue

            await asyncio.sleep(interval_sec)

    async def stream_or_poll(
        self,
        symbol: str,
        rest_interval: float = 12.0,
        rest_timespan: str = "minute",
    ) -> AsyncIterator[Tick]:
        """Dual-mode feed: try WebSocket first, fall back to REST polling.

        Usa WebSocket se disponibile (piano Basic+), altrimenti
        REST polling ogni 12s (piano free, 5 call/min).

        Args:
            symbol: Root symbol (ES, NQ, GC, CL).
            rest_interval: Secondi tra polling REST (default 12s).
            rest_timespan: Bar size per REST (minute, hour, day).

        Yields:
            Tick objects dalla fonte disponibile.
        """
        # Try WebSocket first
        ws_ok = await self.connect()
        if ws_ok:
            logger.info(f"Polygon WebSocket OK — streaming {symbol} live")
            async for tick in self.stream(symbol):
                yield tick
        else:
            logger.info(f"Polygon WebSocket unavailable — REST polling {symbol} every {rest_interval}s")
            async for tick in self.rest_poll(symbol, rest_interval, rest_timespan):
                yield tick

    async def disconnect(self) -> None:
        """Disconnect from Polygon WebSocket."""
        self._running = False
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
