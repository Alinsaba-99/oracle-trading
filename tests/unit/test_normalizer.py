"""Tests for market data normalizer."""

from __future__ import annotations

import pytest

from market.normalizer import Normalizer


class TestNormalizeTick:
    """Tick normalization tests."""

    def test_basic_tick(self) -> None:
        """A basic tick with price and volume is normalized."""
        raw = {"instrument_id": "BTCUSD", "price": 50000.0, "volume": 1.5}
        result = Normalizer.normalize_tick(raw)
        assert result["instrument_id"] == "BTCUSD"
        assert result["price"] == 50000.0
        assert result["volume"] == 1.5
        assert "timestamp" in result

    def test_fallback_to_close(self) -> None:
        """When price is absent, close is used."""
        raw = {"instrument_id": "BTCUSD", "close": 50500.0, "volume": 2.0}
        result = Normalizer.normalize_tick(raw)
        assert result["price"] == 50500.0

    def test_fallback_to_symbol(self) -> None:
        """When instrument_id is absent, symbol is used."""
        raw = {"symbol": "BTCUSD", "price": 50000.0, "volume": 1.0}
        result = Normalizer.normalize_tick(raw)
        assert result["instrument_id"] == "BTCUSD"

    def test_missing_instrument_id_raises(self) -> None:
        """Missing instrument_id raises ValueError."""
        raw = {"price": 50000.0, "volume": 1.0}
        with pytest.raises(ValueError, match="Missing instrument_id"):
            Normalizer.normalize_tick(raw)

    def test_missing_price_raises(self) -> None:
        """Missing both price and close raises ValueError."""
        raw = {"instrument_id": "BTCUSD", "volume": 1.0}
        with pytest.raises(ValueError, match="Missing price"):
            Normalizer.normalize_tick(raw)

    def test_negative_price_raises(self) -> None:
        """Negative price raises ValueError."""
        raw = {"instrument_id": "BTCUSD", "price": -100.0, "volume": 1.0}
        with pytest.raises(ValueError, match="Negative"):
            Normalizer.normalize_tick(raw)

    def test_negative_volume_raises(self) -> None:
        """Negative volume raises ValueError."""
        raw = {"instrument_id": "BTCUSD", "price": 100.0, "volume": -1.0}
        with pytest.raises(ValueError, match="Negative"):
            Normalizer.normalize_tick(raw)

    def test_non_numeric_price_raises(self) -> None:
        """Non-numeric price raises ValueError."""
        raw = {"instrument_id": "BTCUSD", "price": "not-a-number", "volume": 1.0}
        with pytest.raises(ValueError, match="Non-numeric"):
            Normalizer.normalize_tick(raw)

    def test_nan_price_raises(self) -> None:
        """NaN price raises ValueError."""
        raw = {"instrument_id": "BTCUSD", "price": float("nan"), "volume": 1.0}
        with pytest.raises(ValueError, match="NaN/Inf"):
            Normalizer.normalize_tick(raw)

    def test_non_dict_input_raises(self) -> None:
        """Non-dict input raises ValueError."""
        with pytest.raises(ValueError, match="must be a dict"):
            Normalizer.normalize_tick("not a dict")  # type: ignore[arg-type]

    def test_preserves_extra_fields(self) -> None:
        """Extra fields from raw data are preserved."""
        raw = {"instrument_id": "ETHUSD", "price": 3000.0, "volume": 10.0, "exchange": "binance"}
        result = Normalizer.normalize_tick(raw)
        assert result["exchange"] == "binance"

    def test_timestamp_added_when_missing(self) -> None:
        """Timestamp is auto-generated when absent."""
        raw = {"instrument_id": "BTCUSD", "price": 50000.0, "volume": 1.0}
        result = Normalizer.normalize_tick(raw)
        assert result["timestamp"] is not None
        assert isinstance(result["timestamp"], str)
        assert "T" in result["timestamp"]  # ISO format


class TestAggregateBars:
    """OHLCV bar aggregation tests."""

    def test_basic_aggregation(self) -> None:
        """Basic tick-to-bar aggregation produces correct OHLCV."""
        ticks = [
            {"instrument_id": "BTCUSD", "price": 100.0, "volume": 1.0, "timestamp": "t1"},
            {"instrument_id": "BTCUSD", "price": 105.0, "volume": 2.0, "timestamp": "t2"},
            {"instrument_id": "BTCUSD", "price": 95.0, "volume": 0.5, "timestamp": "t3"},
            {"instrument_id": "BTCUSD", "price": 102.0, "volume": 1.5, "timestamp": "t4"},
        ]
        bar = Normalizer.aggregate_bars(ticks, "1m")
        assert bar["open"] == 100.0
        assert bar["high"] == 105.0
        assert bar["low"] == 95.0
        assert bar["close"] == 102.0
        assert bar["volume"] == 5.0  # sum of volumes
        assert bar["trades"] == 4
        assert bar["timeframe"] == "1m"
        assert bar["instrument_id"] == "BTCUSD"

    def test_empty_ticks_raises(self) -> None:
        """Empty tick list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            Normalizer.aggregate_bars([], "1m")

    def test_single_tick(self) -> None:
        """A single tick produces a flat bar."""
        ticks = [{"instrument_id": "ETHUSD", "price": 2000.0, "volume": 5.0, "timestamp": "t1"}]
        bar = Normalizer.aggregate_bars(ticks, "5m")
        assert bar["open"] == 2000.0
        assert bar["high"] == 2000.0
        assert bar["low"] == 2000.0
        assert bar["close"] == 2000.0
        assert bar["volume"] == 5.0

    def test_timeframe_preserved(self) -> None:
        """The specified timeframe is stored verbatim."""
        ticks = [{"instrument_id": "XRPUSD", "price": 1.0, "volume": 100.0, "timestamp": "t1"}]
        bar = Normalizer.aggregate_bars(ticks, "1h")
        assert bar["timeframe"] == "1h"


class TestValidateBar:
    """Bar validation tests."""

    def test_valid_bar(self) -> None:
        """A valid bar passes validation."""
        bar = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise

    def test_missing_field_raises(self) -> None:
        """Missing required field raises ValueError."""
        bar = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0}  # missing volume
        with pytest.raises(ValueError, match="Missing required"):
            Normalizer.validate_bar(bar)

    def test_nan_in_open_raises(self) -> None:
        """NaN in open field raises ValueError."""

        bar = {"open": float("nan"), "high": 110.0, "low": 95.0, "close": 105.0, "volume": 1000.0}
        with pytest.raises(ValueError, match="Invalid numeric"):
            Normalizer.validate_bar(bar)

    def test_inf_in_high_raises(self) -> None:
        """Infinity in high field raises ValueError."""

        bar = {"open": 100.0, "high": float("inf"), "low": 95.0, "close": 105.0, "volume": 1000.0}
        with pytest.raises(ValueError, match="Invalid numeric"):
            Normalizer.validate_bar(bar)

    def test_high_below_max_open_close_raises(self) -> None:
        """High below max(open, close) raises ValueError."""
        bar = {"open": 100.0, "high": 90.0, "low": 85.0, "close": 105.0, "volume": 1000.0}
        with pytest.raises(ValueError, match="High"):
            Normalizer.validate_bar(bar)

    def test_low_above_min_open_close_raises(self) -> None:
        """Low above min(open, close) raises ValueError."""
        bar = {"open": 100.0, "high": 110.0, "low": 105.0, "close": 95.0, "volume": 1000.0}
        with pytest.raises(ValueError, match="Low"):
            Normalizer.validate_bar(bar)

    def test_negative_volume_raises(self) -> None:
        """Negative volume raises ValueError."""
        bar = {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": -100.0}
        with pytest.raises(ValueError, match="Negative volume"):
            Normalizer.validate_bar(bar)

    def test_at_boundary_high_equals_close(self) -> None:
        """High == close is valid."""
        bar = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 105.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise
        bar = {"open": 100.0, "high": 100.0, "low": 95.0, "close": 100.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise

    def test_at_boundary_low_equals_close(self) -> None:
        """Low == close is valid."""
        bar = {"open": 100.0, "high": 110.0, "low": 100.0, "close": 105.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise
        bar = {"open": 100.0, "high": 110.0, "low": 100.0, "close": 100.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise

    def test_at_boundary_low_equals_open(self) -> None:
        """Low == open is valid."""
        bar = {"open": 100.0, "high": 110.0, "low": 100.0, "close": 105.0, "volume": 1000.0}
        Normalizer.validate_bar(bar)  # no raise
