"""Tests for unified data sources."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestDataFetcher:
    """DataFetcher smoke tests (require network)."""

    def test_yfinance_futures(self) -> None:
        """Fetch ES futures data."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        df = f.yfinance_futures("ES", period="5d")
        assert len(df) > 0
        assert "Close" in df.columns or "close" in df.columns
        # Verify it was cached
        assert Path(f.DATA_DIR / "ES_1d.parquet").exists()

    def test_yfinance_equity(self) -> None:
        """Fetch SPY equity data."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        df = f.yfinance_equity("SPY", period="5d")
        assert len(df) > 0

    @pytest.mark.slow
    def test_ccxt_crypto(self) -> None:
        """Fetch BTC/USDT via CCXT."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        df = f.ccxt_ohlcv("binance", "BTC/USDT", "1d", limit=10)
        assert len(df) > 0
        assert "close" in df.columns

    def test_unified_fetch_futures(self) -> None:
        """Auto-detect ES as futures -> yfinance."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        df = f.fetch("ES", period="5d")
        assert len(df) > 0

    def test_unified_fetch_crypto(self) -> None:
        """Auto-detect BTC/USDT as crypto -> ccxt."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        df = f.fetch("BTC/USDT")
        assert len(df) > 0
