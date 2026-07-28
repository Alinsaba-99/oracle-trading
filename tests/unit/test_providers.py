"""Tests for the R0.2/R0.4/R0.5 providers + DataRegistry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from analytics.backtest.providers import DataRegistry, _period_to_timedelta, _resample


def test_cache_path_layout(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    p = dr._cache_path("eurusd", "1h")
    assert p.name == "1h.parquet"
    assert p.parent.name == "EURUSD"


def test_unsupported_tf_raises(tmp_path: object) -> None:
    dr = DataRegistry(root=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported timeframe"):
        dr.get_ohlcv("EURUSD", tf="5m")


@pytest.mark.parametrize(
    ("period", "days"), [("60d", 60.0), ("2y", 730.5), ("1mo", 30.44), ("3wk", 21.0)]
)
def test_period_to_timedelta_parses_units(period: str, days: float) -> None:
    span = _period_to_timedelta(period)
    assert span is not None
    assert span.total_seconds() == pytest.approx(days * 86400.0)


@pytest.mark.parametrize("period", ["max", "ytd", "garbage", "xy"])
def test_period_to_timedelta_unbounded_or_invalid(period: str) -> None:
    assert _period_to_timedelta(period) is None


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


def _write_lake_month(root: Path, symbol: str, tf: str, ts: list[datetime]) -> None:
    """Write one lake partition so read_from_lake can pick it up."""
    part = root / f"symbol={symbol}" / f"tf={tf}" / f"year={ts[0].year}"
    part.mkdir(parents=True, exist_ok=True)
    n = len(ts)
    pl.DataFrame(
        {
            "timestamp": ts,
            "open": [1.0] * n,
            "high": [2.0] * n,
            "low": [0.5] * n,
            "close": [1.5] * n,
            "volume": [10.0] * n,
        }
    ).write_parquet(part / f"month={ts[0].month:02d}.parquet")


def test_read_from_lake_honours_period(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A period must trim the lake read, not silently return full history."""
    import analytics.backtest.providers as prov

    start = datetime(2026, 1, 1, tzinfo=UTC)
    days = [start + timedelta(days=i) for i in range(90)]
    monkeypatch.setattr(prov, "NORM_ROOT", tmp_path)
    _write_lake_month(tmp_path, "TESTFX", "1d", days)

    full = prov.read_from_lake("TESTFX", "1d")
    assert full is not None and full.height == 90

    trimmed = prov.read_from_lake("TESTFX", "1d", period="30d")
    assert trimmed is not None
    # Window is inclusive of the boundary bar, so 30d spans 31 daily bars.
    assert trimmed.height == 31
    assert trimmed.select(pl.col("timestamp").max()).item() == days[-1]

    # An explicit start wins over period.
    windowed = prov.read_from_lake("TESTFX", "1d", start=days[10], period="5d")
    assert windowed is not None and windowed.height == 80


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
    # force=True bypasses both the parquet cache and the data lake, so this
    # exercises the live yfinance fetch + cache-write path. Without it the lake
    # (which carries EURUSD 1d from 2003) serves the read and nothing is cached.
    df = dr.get_ohlcv("EURUSD", tf="1d", period="1mo", force=True)
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
