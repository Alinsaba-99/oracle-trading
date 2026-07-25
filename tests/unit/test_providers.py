"""Tests for the R0.2/R0.4/R0.5 providers + DataRegistry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from analytics.backtest.providers import DataRegistry, _resample


def test_cache_path_layout(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    p = dr._cache_path("eurusd", "1h")
    assert p.name == "1h.parquet"
    assert p.parent.name == "EURUSD"


def test_unsupported_tf_raises(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported timeframe"):
        dr.get_ohlcv("EURUSD", tf="5m")


def test_resample_4h_from_1h() -> None:
    base = datetime(2026, 1, 5, 12, tzinfo=UTC)  # 12:00 UTC (epoch-aligned to 4h)
    hours = [base + timedelta(hours=i) for i in range(8)]
    df = pl.DataFrame(
        {
            "timestamp": hours,
            "open": [10.0, 11.0, 12.0, 13.0, 20.0, 21.0, 22.0, 23.0],
            "high": [11.0, 12.0, 13.0, 14.0, 21.0, 22.0, 23.0, 24.0],
            "low": [9.0, 10.0, 11.0, 12.0, 19.0, 20.0, 21.0, 22.0],
            "close": [11.0, 12.0, 13.0, 14.0, 21.0, 22.0, 23.0, 24.0],
            "volume": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        },
        schema={
            "timestamp": pl.Datetime,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    out = _resample(df, "4h")
    assert out.height == 2
    first = out.row(0, named=True)
    # first 4h window: open=10, high=14, low=9, close=14, volume=10
    assert first["open"] == 10.0
    assert first["high"] == 14.0
    assert first["low"] == 9.0
    assert first["close"] == 14.0
    assert first["volume"] == 10.0


def _network_available() -> bool:
    try:
        import socket

        socket.create_connection(("finance.yahoo.com", 443), timeout=5)
        return True
    except OSError:
        return False


network = pytest.mark.skipif(not _network_available(), reason="no network")


@network
def test_yfinance_daily_eurusd_caches(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    df = dr.get_ohlcv("EURUSD", tf="1d", period="1mo")
    if df.is_empty():
        pytest.skip("yfinance returned no data for EURUSD")
    assert {"timestamp", "open", "high", "low", "close"} <= set(df.columns)
    assert dr._cache_path("EURUSD", "1d").exists()
    # second call reads from cache (same height, no re-fetch)
    df2 = dr.get_ohlcv("EURUSD", tf="1d", period="1mo")
    assert df2.height == df.height


@network
def test_ccxt_btc_1h_caches(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    df = dr.get_ohlcv("BTC", tf="1h")
    if df.is_empty():
        pytest.skip("ccxt returned no data for BTC")
    assert df.height > 0
    assert dr._cache_path("BTC", "1h").exists()
