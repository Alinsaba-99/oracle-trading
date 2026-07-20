"""Tests for analytics.strategy.timeframe (R2.1)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from analytics.strategy.timeframe import (
    TF_TO_TIMEDELTA,
    TIMEFRAME_ORDER,
    bars_per_filter_bar,
    is_higher_tf,
    tf_duration,
    tf_index,
    validate_pair,
)


class TestTFDuration:
    def test_all_supported(self) -> None:
        assert tf_duration("15m") == timedelta(minutes=15)
        assert tf_duration("1h") == timedelta(hours=1)
        assert tf_duration("4h") == timedelta(hours=4)
        assert tf_duration("1d") == timedelta(days=1)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown timeframe"):
            tf_duration("7m")

    def test_map_covers_order(self) -> None:
        assert set(TF_TO_TIMEDELTA) == set(TIMEFRAME_ORDER)


class TestTFIndex:
    def test_order(self) -> None:
        assert tf_index("15m") == 0
        assert tf_index("1h") == 1
        assert tf_index("4h") == 2
        assert tf_index("1d") == 3

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown timeframe"):
            tf_index("1w")


class TestIsHigherTF:
    def test_strictly_higher(self) -> None:
        assert is_higher_tf("15m", "1h") is True
        assert is_higher_tf("15m", "4h") is True
        assert is_higher_tf("15m", "1d") is True
        assert is_higher_tf("1h", "4h") is True
        assert is_higher_tf("1h", "1d") is True
        assert is_higher_tf("4h", "1d") is True

    def test_same_tf_is_false(self) -> None:
        assert is_higher_tf("1h", "1h") is False
        assert is_higher_tf("1d", "1d") is False

    def test_lower_is_false(self) -> None:
        assert is_higher_tf("1h", "15m") is False
        assert is_higher_tf("1d", "15m") is False
        assert is_higher_tf("4h", "1h") is False


class TestValidatePair:
    def test_valid_pairs(self) -> None:
        validate_pair("15m", "1h")
        validate_pair("15m", "1d")
        validate_pair("1h", "1d")
        validate_pair("4h", "1d")

    def test_same_tf_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly higher"):
            validate_pair("1h", "1h")

    def test_inverted_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly higher"):
            validate_pair("1d", "1h")


class TestBarsPerFilterBar:
    def test_15m_in_1h(self) -> None:
        assert bars_per_filter_bar("15m", "1h") == 4

    def test_15m_in_4h(self) -> None:
        assert bars_per_filter_bar("15m", "4h") == 16

    def test_15m_in_1d(self) -> None:
        assert bars_per_filter_bar("15m", "1d") == 96

    def test_1h_in_1d(self) -> None:
        assert bars_per_filter_bar("1h", "1d") == 24

    def test_4h_in_1d(self) -> None:
        assert bars_per_filter_bar("4h", "1d") == 6

    def test_invalid_pair_raises(self) -> None:
        with pytest.raises(ValueError):
            bars_per_filter_bar("1d", "1h")
