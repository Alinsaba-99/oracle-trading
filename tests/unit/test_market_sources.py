"""Tests for market data sources."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from market.sources.base import BaseSource
from market.sources.binance import BinanceWebSocketSource
from market.sources.coinpaprika import CoinPaprikaSource
from market.sources.yfinance_source import yfinanceSource


class TestBaseSource:
    """BaseSource ABC contract tests."""

    def test_abstract_instantiation(self) -> None:
        """Cannot instantiate BaseSource directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseSource("test")  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        """Concrete subclass works with default args."""

        class ConcreteSource(BaseSource):
            async def connect(self) -> None: ...
            async def disconnect(self) -> None: ...
            async def subscribe(self, instrument_ids: list[str]) -> None: ...
            async def unsubscribe(self, instrument_ids: list[str]) -> None: ...

        source = ConcreteSource("test", instrument_ids=["BTCUSD"])
        assert source.name == "test"
        assert source.instrument_ids == ["BTCUSD"]
        assert source.events.qsize() == 0


class TestBinanceWebSocketSource:
    """Binance WS source tests."""

    @pytest.mark.asyncio
    async def test_parse_kline_valid(self) -> None:
        """Parsing a valid kline message returns a normalized dict."""
        raw = {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": 1234567890000,
                "o": "50000.00",
                "h": "51000.00",
                "l": "49000.00",
                "c": "50500.00",
                "v": "100.5",
                "q": "5000000",
                "n": 250,
                "V": "50.2",
                "Q": "2500000",
                "x": True,
            },
        }
        result = BinanceWebSocketSource._parse_kline(raw)
        assert result is not None
        assert result["source"] == "binance"
        assert result["instrument_id"] == "btcusdt"
        assert result["open"] == 50000.0
        assert result["high"] == 51000.0
        assert result["low"] == 49000.0
        assert result["close"] == 50500.0
        assert result["volume"] == 100.5
        assert result["trades"] == 250
        assert result["is_final"] is True

    @pytest.mark.asyncio
    async def test_parse_kline_intermediate_is_tick(self) -> None:
        """An open kline remains a tick and retains its non-final state."""
        raw = {
            "e": "kline",
            "s": "ETHUSDT",
            "k": {"t": 1234567890000, "c": "3500.25", "v": "12.5", "x": False},
        }

        result = BinanceWebSocketSource._parse_kline(raw)

        assert result == {
            "source": "binance",
            "instrument_id": "ethusdt",
            "event_type": "tick",
            "timestamp": 1234567890000,
            "price": 3500.25,
            "volume": 12.5,
            "is_final": False,
        }

    @pytest.mark.asyncio
    async def test_parse_kline_non_kline(self) -> None:
        """Non-kline messages return None."""
        raw = {"e": "trade", "s": "BTCUSDT", "p": "50000"}
        assert BinanceWebSocketSource._parse_kline(raw) is None

    @pytest.mark.asyncio
    async def test_parse_kline_empty(self) -> None:
        """Empty dict returns None."""
        assert BinanceWebSocketSource._parse_kline({}) is None

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self) -> None:
        """Connect and disconnect lifecycle."""
        source = BinanceWebSocketSource(instrument_ids=["btcusdt"])

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value = mock_ws

            await source.connect()
            mock_connect.assert_called_once()
            assert source._running is True

            await source.disconnect()
            assert source._running is False


class TestyfinanceSource:
    """yfinance source tests."""

    def test_initialization(self) -> None:
        """Source initializes with default state."""
        source = yfinanceSource(instrument_ids=["AAPL"])
        assert source.name == "yfinance"
        assert source.instrument_ids == ["AAPL"]

    @pytest.mark.asyncio
    async def test_fetch_history_shape(self) -> None:
        """fetch_history returns a Polars DataFrame with expected columns."""
        source = yfinanceSource()

        # Mock yfinance to return a known pandas DataFrame
        mock_df = pl.DataFrame(
            {
                "Open": [150.0, 151.0],
                "High": [152.0, 153.0],
                "Low": [149.0, 150.0],
                "Close": [151.0, 152.0],
                "Volume": [1000000, 1100000],
                "Dividends": [0.0, 0.0],
                "Stock Splits": [0.0, 0.0],
            }
        ).to_pandas()

        mock_ticker = MagicMock()
        mock_ticker.history = MagicMock(return_value=mock_df)

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await source.fetch_history("AAPL", period="5d", interval="1d")

        assert isinstance(result, pl.DataFrame)
        expected_cols = {"open", "high", "low", "close", "volume", "instrument_id", "source"}
        assert expected_cols.issubset(set(result.columns))
        assert result["instrument_id"].to_list() == ["AAPL", "AAPL"]
        assert result["source"].to_list() == ["yfinance", "yfinance"]

    @pytest.mark.asyncio
    async def test_fetch_history_empty_raises(self) -> None:
        """Empty response raises ValueError."""
        source = yfinanceSource()
        mock_ticker = MagicMock()
        mock_ticker.history = MagicMock(return_value=None)

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            pytest.raises(ValueError, match="No data for"),
        ):
            await source.fetch_history("INVALID")


class TestCoinPaprikaSource:
    """CoinPaprika source tests."""

    @pytest.mark.asyncio
    async def test_get_ticker_structure(self) -> None:
        """get_ticker returns normalized ticker data."""
        source = CoinPaprikaSource()

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "id": "btc-bitcoin",
                "name": "Bitcoin",
                "symbol": "BTC",
                "quotes": {
                    "USD": {
                        "price": 50000.0,
                        "volume_24h": 30000000000.0,
                        "market_cap": 1000000000000.0,
                    }
                },
                "circulating_supply": 19000000.0,
                "total_supply": 21000000.0,
                "max_supply": 21000000.0,
                "last_updated": "2024-01-01T00:00:00Z",
            }
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        source._client = mock_client
        result = await source.get_ticker("btc-bitcoin")

        assert result["source"] == "coinpaprika"
        assert result["instrument_id"] == "btc-bitcoin"
        assert result["price"] == 50000.0
        assert result["volume_24h"] == 30000000000.0
        assert isinstance(result["timestamp"], str)

    @pytest.mark.asyncio
    async def test_get_ticker_not_connected(self) -> None:
        """Calling get_ticker without connect raises RuntimeError."""
        source = CoinPaprikaSource()
        with pytest.raises(RuntimeError, match="Not connected"):
            await source.get_ticker("btc-bitcoin")

    @pytest.mark.asyncio
    async def test_get_historical_ohlcv(self) -> None:
        """get_historical_ohlcv returns normalized list of OHLCV dicts."""
        source = CoinPaprikaSource()

        mock_response = MagicMock()
        mock_response.json = MagicMock(
            return_value=[
                {
                    "time_open": "2024-01-01T00:00:00Z",
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "volume": 1000000.0,
                    "market_cap": 1000000000000.0,
                }
            ]
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        source._client = mock_client
        result = await source.get_historical_ohlcv("btc-bitcoin", interval="1d", limit=1)

        assert len(result) == 1
        assert result[0]["instrument_id"] == "btc-bitcoin"
        assert result[0]["open"] == 50000.0
        assert result[0]["close"] == 50500.0
