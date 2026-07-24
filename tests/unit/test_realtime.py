"""Tests for real-time market data feeds."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from market.realtime import CCXTWebSocketFeed, IBKRFeed, PolygonWebSocketFeed, Tick


class TestTick:
    """Tick data model — shared type for all feeds."""

    def test_create(self) -> None:
        t = Tick(symbol="ES", price=5000.0, volume=100, bid=4999.5, ask=5000.5)
        assert t.symbol == "ES"
        assert t.price == 5000.0
        assert t.volume == 100.0
        assert t.bid == 4999.5
        assert t.ask == 5000.5
        assert t.source == ""

    def test_default_timestamp(self) -> None:
        t = Tick(symbol="ES", price=5000.0)
        assert t.timestamp is not None

    def test_repr(self) -> None:
        t = Tick(symbol="ES", price=5000.0)
        r = repr(t)
        assert "ES" in r
        assert "5000" in r


class TestIBKRFeed:
    """IBKR feed — requires TWS/Gateway, tested via mocks."""

    @patch("market.realtime.IBKRFeed.connect", return_value=True)
    async def test_connect_success(self, mock_connect: MagicMock) -> None:
        feed = IBKRFeed()
        ok = await feed.connect()
        assert ok is True

    @patch("market.realtime.IBKRFeed.connect", return_value=False)
    async def test_connect_failure(self, mock_connect: MagicMock) -> None:
        feed = IBKRFeed(host="bad-host")
        ok = await feed.connect()
        assert ok is False

    async def test_disconnect_noop(self) -> None:
        """Disconnect without connect should not raise."""
        feed = IBKRFeed()
        await feed.disconnect()  # should not raise


class TestCCXTWebSocketFeed:
    """CCXT crypto WebSocket feed."""

    @patch("market.realtime.CCXTWebSocketFeed.connect", return_value=True)
    async def test_connect_success(self, mock_connect: MagicMock) -> None:
        feed = CCXTWebSocketFeed("binance")
        ok = await feed.connect()
        assert ok is True

    async def test_disconnect_noop(self) -> None:
        feed = CCXTWebSocketFeed()
        await feed.disconnect()  # should not raise


class TestPolygonWebSocketFeed:
    """Polygon.io WebSocket feed for futures.

    WebSocket requires a paid Polygon plan (Basic $29/mo+).
    Free tier falls back gracefully with REST polling.
    """

    def test_missing_api_key(self) -> None:
        with pytest.raises(ValueError, match="Polygon API key required"):
            PolygonWebSocketFeed(api_key="")

    @patch.object(PolygonWebSocketFeed, "connect", new_callable=AsyncMock)
    async def test_connect_success(self, mock_connect: AsyncMock) -> None:
        """Connect returns True for successful auth."""
        mock_connect.return_value = True
        feed = PolygonWebSocketFeed(api_key="test-key")
        ok = await feed.connect()
        assert ok is True

    @patch.object(PolygonWebSocketFeed, "connect", new_callable=AsyncMock)
    async def test_connect_failure(self, mock_connect: AsyncMock) -> None:
        """Connect returns False for auth failure."""
        mock_connect.return_value = False
        feed = PolygonWebSocketFeed(api_key="test-key")
        ok = await feed.connect()
        assert ok is False

    async def test_do_connect_auth_success(self) -> None:
        """Test the actual WebSocket auth flow with a mock socket."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            side_effect=[
                json.dumps([{"ev": "status", "status": "connected", "message": "Connected"}]),
                json.dumps(
                    [{"ev": "status", "status": "auth_success", "message": "Authenticated"}]
                ),
            ]
        )
        mock_ws.send = AsyncMock()

        async def fake_connect(*args: object, **kwargs: object) -> AsyncMock:
            return mock_ws

        with patch("market.realtime.websockets.connect", side_effect=fake_connect):
            feed = PolygonWebSocketFeed(api_key="test-key")
            ok = await feed.connect()

        assert ok is True
        assert feed._connected is True
        # Should have sent auth message
        sent_calls = mock_ws.send.call_args_list
        assert any("auth" in str(c) for c in sent_calls)

    async def test_do_connect_auth_failed(self) -> None:
        """Free plan auth failure is handled gracefully."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            side_effect=[
                json.dumps([{"ev": "status", "status": "connected"}]),
                json.dumps(
                    [
                        {
                            "ev": "status",
                            "status": "auth_failed",
                            "message": "WebSocket not in your plan",
                        }
                    ]
                ),
            ]
        )
        mock_ws.send = AsyncMock()

        async def fake_connect(*args: object, **kwargs: object) -> AsyncMock:
            return mock_ws

        with patch("market.realtime.websockets.connect", side_effect=fake_connect):
            feed = PolygonWebSocketFeed(api_key="free-key")
            ok = await feed.connect()

        assert ok is False
        assert feed._connected is False

    async def test_stream_ticks(self) -> None:
        """Stream parses Polygon messages into Tick objects."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            side_effect=[
                json.dumps([{"ev": "status", "status": "connected"}]),
                json.dumps([{"ev": "status", "status": "auth_success"}]),
                json.dumps([{"ev": "T", "sym": "ES*5", "p": 5500.25, "s": 10, "t": 1784545200000}]),
                json.dumps([{"ev": "Q", "sym": "ES*5", "bp": 5500.0, "ap": 5500.5}]),
            ]
        )
        mock_ws.send = AsyncMock()

        async def fake_connect(*args: object, **kwargs: object) -> AsyncMock:
            return mock_ws

        with patch("market.realtime.websockets.connect", side_effect=fake_connect):
            feed = PolygonWebSocketFeed(api_key="test-key", channels=("T", "Q"))
            await feed.connect()

            ticks = []
            async for tick in feed.stream("ES"):
                ticks.append(tick)
                if len(ticks) >= 2:
                    break

        assert len(ticks) == 2
        assert ticks[0].symbol == "ES"
        assert ticks[0].price == 5500.25
        assert ticks[0].source == "polygon"
        assert ticks[1].bid == 5500.0
        assert ticks[1].ask == 5500.5

        await feed.disconnect()

    async def test_stream_without_connect(self) -> None:
        """Stream without connect yields nothing."""
        feed = PolygonWebSocketFeed(api_key="test-key")
        ticks = []
        async for tick in feed.stream("ES"):
            ticks.append(tick)
        assert len(ticks) == 0

    async def test_rest_poll(self) -> None:
        """REST polling fallback works with mock HTTP response."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "results": [
                    {"c": 5500.25, "h": 5501.0, "l": 5499.5, "v": 10000, "t": 1784545200000}
                ]
            }
        )

        async def fake_get(*args: object, **kwargs: object) -> MagicMock:
            return mock_response

        with patch("httpx.AsyncClient", autospec=True) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=fake_get)
            mock_client_cls.return_value = mock_client

            feed = PolygonWebSocketFeed(api_key="test-key")
            feed._running = True

            ticks = []
            async for tick in feed.rest_poll("ES", interval_sec=0.1):
                ticks.append(tick)
                if len(ticks) >= 1:
                    feed._running = False

            assert len(ticks) == 1
            assert ticks[0].symbol == "ES"
            assert ticks[0].price == 5500.25
            assert ticks[0].source == "polygon_rest"
            assert ticks[0].volume == 10000.0

    async def test_stream_or_poll_websocket(self) -> None:
        """stream_or_poll usa WebSocket quando disponibile."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            side_effect=[
                json.dumps([{"ev": "status", "status": "connected"}]),
                json.dumps([{"ev": "status", "status": "auth_success"}]),
                json.dumps([{"ev": "T", "sym": "ES*5", "p": 5500.0, "s": 5, "t": 1784545200000}]),
            ]
        )
        mock_ws.send = AsyncMock()

        async def fake_connect(*args: object, **kwargs: object) -> AsyncMock:
            return mock_ws

        with patch("market.realtime.websockets.connect", side_effect=fake_connect):
            feed = PolygonWebSocketFeed(api_key="test-key", channels=("T",))

            ticks = []
            async for tick in feed.stream_or_poll("ES", rest_interval=0.1):
                ticks.append(tick)
                if len(ticks) >= 1:
                    break

            assert len(ticks) == 1
            assert ticks[0].source == "polygon"
            await feed.disconnect()

    async def test_stream_or_poll_rest_fallback(self) -> None:
        """stream_or_poll usa REST polling quando WebSocket fallisce."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "results": [
                    {"c": 5500.25, "h": 5501.0, "l": 5499.5, "v": 10000, "t": 1784545200000}
                ]
            }
        )

        async def fake_get(*args: object, **kwargs: object) -> MagicMock:
            return mock_response

        with (
            patch("market.realtime.websockets.connect", side_effect=Exception("no ws")),
            patch("httpx.AsyncClient", autospec=True) as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=fake_get)
            mock_client_cls.return_value = mock_client

            feed = PolygonWebSocketFeed(api_key="test-key")

            ticks = []
            async for tick in feed.stream_or_poll("ES", rest_interval=0.1):
                ticks.append(tick)
                if len(ticks) >= 1:
                    break

            assert len(ticks) == 1
            assert ticks[0].source == "polygon_rest"

    async def test_disconnect_noop(self) -> None:
        feed = PolygonWebSocketFeed(api_key="test-key")
        await feed.disconnect()
