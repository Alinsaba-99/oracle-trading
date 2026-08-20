"""Tests for unified data sources.

These are network smoke tests against third-party providers (yfinance,
Binance/ccxt).  Providers can geo-block or rate-limit CI runners (Binance
returns HTTP 451 from GitHub's US runners), so every live fetch skips
gracefully on connectivity errors instead of failing the build.  Local
runs with working network still exercise the real path.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest

# Errors that mean "provider unreachable / unavailable from here", not a
# defect in the code under test.  ccxt wraps many transport failures;
# BaseError covers ExchangeNotAvailable/NetworkError/etc.
try:
    import ccxt.base.errors as _ccxt_errors

    _NETWORK_ERRORS: tuple[type[Exception], ...] = (_ccxt_errors.BaseError,)
except ImportError:  # pragma: no cover - ccxt always present in dev env
    _NETWORK_ERRORS = ()


def _skip_on_network_error(exc: Exception) -> NoReturn:
    pytest.skip(f"network smoke skipped: {type(exc).__name__}: {exc}")


class TestDataFetcher:
    """DataFetcher smoke tests (require network)."""

    def test_yfinance_futures(self) -> None:
        """Fetch ES futures data."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        try:
            df = f.yfinance_futures("ES", period="5d")
        except _NETWORK_ERRORS as exc:
            _skip_on_network_error(exc)
        assert len(df) > 0
        assert "Close" in df.columns or "close" in df.columns
        # Verify it was cached
        assert Path(f.DATA_DIR / "ES_1d.parquet").exists()

    def test_yfinance_equity(self) -> None:
        """Fetch SPY equity data."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        try:
            df = f.yfinance_equity("SPY", period="5d")
        except _NETWORK_ERRORS as exc:
            _skip_on_network_error(exc)
        assert len(df) > 0

    @pytest.mark.slow
    def test_ccxt_crypto(self) -> None:
        """Fetch BTC/USDT via CCXT."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        try:
            df = f.ccxt_ohlcv("binance", "BTC/USDT", "1d", limit=10)
        except _NETWORK_ERRORS as exc:
            _skip_on_network_error(exc)
        assert len(df) > 0
        assert "close" in df.columns

    def test_unified_fetch_futures(self) -> None:
        """Auto-detect ES as futures -> yfinance."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        try:
            df = f.fetch("ES", period="5d")
        except _NETWORK_ERRORS as exc:
            _skip_on_network_error(exc)
        assert len(df) > 0

    def test_unified_fetch_crypto(self) -> None:
        """Auto-detect BTC/USDT as crypto -> ccxt."""
        from market.data_sources import DataFetcher

        f = DataFetcher()
        try:
            df = f.fetch("BTC/USDT")
        except _NETWORK_ERRORS as exc:
            _skip_on_network_error(exc)
        assert len(df) > 0
