"""Tests for fetch_pair helper (R2.5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl
import pytest

from analytics.strategy.multi_tf import fetch_pair


def _bars(start: datetime, tf_delta: timedelta, n: int) -> pl.DataFrame:
    ts = [start + i * tf_delta for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0] * n,
            "high": [100.5] * n,
            "low": [99.5] * n,
            "close": [100.25] * n,
            "volume": [1000.0] * n,
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime(time_unit="us")))


class TestFetchPair:
    def test_returns_primary_and_filter(self) -> None:
        registry = MagicMock()
        primary_df = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 10)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)

        def _get(_instrument_id: str, tf: str, **_kwargs: object) -> pl.DataFrame:
            return primary_df if tf == "1h" else filter_df

        registry.get_ohlcv.side_effect = _get

        p, f = fetch_pair(registry, "GOLD", "1h", "1d")
        assert p.height == 10
        assert f.height == 3
        assert registry.get_ohlcv.call_count == 2

    def test_calls_with_correct_tfs(self) -> None:
        registry = MagicMock()
        registry.get_ohlcv.return_value = _bars(
            datetime(2026, 1, 1, tzinfo=UTC), timedelta(hours=1), 5
        )
        fetch_pair(registry, "EURUSD", "15m", "4h")
        calls = [c.args[1] for c in registry.get_ohlcv.call_args_list]
        assert calls == ["15m", "4h"]

    def test_forwards_kwargs(self) -> None:
        registry = MagicMock()
        registry.get_ohlcv.return_value = _bars(
            datetime(2026, 1, 1, tzinfo=UTC), timedelta(hours=1), 5
        )
        fetch_pair(registry, "GOLD", "1h", "1d", period="730d", force=True)
        for call in registry.get_ohlcv.call_args_list:
            assert call.kwargs["period"] == "730d"
            assert call.kwargs["force"] is True

    def test_invalid_pair_raises(self) -> None:
        registry = MagicMock()
        with pytest.raises(ValueError, match="strictly higher"):
            fetch_pair(registry, "GOLD", "1d", "1h")
        # Registry never called when pair invalid.
        registry.get_ohlcv.assert_not_called()
