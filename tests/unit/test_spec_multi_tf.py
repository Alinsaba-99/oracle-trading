"""Tests for StrategySpec multi-TF extension (R2.4)."""

from __future__ import annotations

import pytest

from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.signals import DonchianBreakout, EmaTrend
from analytics.strategy.spec import ENTRY_TYPES, StrategySpec


class TestEntryTypes:
    def test_r1_signals_present(self) -> None:
        """R1 filter-capable signals are registered."""
        for name in ("adx_trend", "macd_trend", "pullback", "volume_breakout"):
            assert name in ENTRY_TYPES, f"missing {name}"


class TestSingleTFSpec:
    def test_default_no_filter(self) -> None:
        spec = StrategySpec(
            name="gold_donchian",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 20},
        )
        assert not spec.is_multi_tf
        signal = spec.build_signal()
        assert isinstance(signal, DonchianBreakout)

    def test_explicit_none_filter(self) -> None:
        spec = StrategySpec(
            name="gold_ema",
            instrument="GOLD",
            entry="ema_trend",
            entry_params={"fast": 20, "slow": 50},
            filter_tf=None,
        )
        assert not spec.is_multi_tf
        assert isinstance(spec.build_signal(), EmaTrend)


class TestMultiTFSpec:
    def test_builds_composite(self) -> None:
        spec = StrategySpec(
            name="gold_donchian_ema_filter",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 20},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 20, "slow": 50},
            filter_mode="gate",
        )
        assert spec.is_multi_tf
        signal = spec.build_signal()
        assert isinstance(signal, CompositeMTFSignal)
        assert signal.primary_tf == "1h"
        assert signal.filter_tf == "1d"
        assert signal.mode == "gate"

    def test_filter_tf_must_be_higher(self) -> None:
        spec = StrategySpec(
            name="bad",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1d",
            filter_tf="1h",  # wrong: filter < primary
            filter_entry="ema_trend",
        )
        with pytest.raises(ValueError, match="strictly higher"):
            spec.build_signal()

    def test_filter_tf_same_as_primary_raises(self) -> None:
        spec = StrategySpec(
            name="bad",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1h",
            filter_tf="1h",
            filter_entry="ema_trend",
        )
        with pytest.raises(ValueError, match="strictly higher"):
            spec.build_signal()

    def test_filter_entry_required(self) -> None:
        spec = StrategySpec(
            name="bad",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1h",
            filter_tf="1d",
            filter_entry=None,  # missing
        )
        with pytest.raises(ValueError, match="filter_entry"):
            spec.build_signal()

    def test_unknown_filter_entry_raises(self) -> None:
        spec = StrategySpec(
            name="bad",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1h",
            filter_tf="1d",
            filter_entry="not_a_signal",
        )
        with pytest.raises(ValueError, match="Unknown filter_entry"):
            spec.build_signal()

    def test_unknown_entry_raises(self) -> None:
        spec = StrategySpec(name="bad", instrument="GOLD", entry="not_a_signal")
        with pytest.raises(ValueError, match="Unknown entry type"):
            spec.build_signal()

    def test_invalid_filter_params_raises(self) -> None:
        spec = StrategySpec(
            name="bad",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"not_a_param": 42},
        )
        with pytest.raises(ValueError, match="Invalid filter_entry_params"):
            spec.build_signal()

    def test_all_filter_modes_accepted(self) -> None:
        for mode in ("gate", "confirm", "size"):
            spec = StrategySpec(
                name=f"multi_{mode}",
                instrument="GOLD",
                entry="donchian_breakout",
                timeframe="1h",
                filter_tf="1d",
                filter_entry="ema_trend",
                filter_mode=mode,
            )
            signal = spec.build_signal()
            assert isinstance(signal, CompositeMTFSignal)
            assert signal.mode == mode

    def test_filter_sign_minus_one(self) -> None:
        spec = StrategySpec(
            name="short_bias",
            instrument="GOLD",
            entry="donchian_breakout",
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_mode="gate",
            filter_sign=-1,
        )
        signal = spec.build_signal()
        assert isinstance(signal, CompositeMTFSignal)
        assert signal.filter_sign == -1


class TestSpecSerialization:
    """Multi-TF spec must remain pydantic-serializable (for LLM round-trips)."""

    def test_multi_tf_round_trip(self) -> None:
        spec = StrategySpec(
            name="round_trip",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 20},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="adx_trend",
            filter_entry_params={"period": 14},
            filter_mode="confirm",
            filter_sign=-1,
            rationale="test round-trip",
        )
        data = spec.model_dump()
        rebuilt = StrategySpec.model_validate(data)
        assert rebuilt.is_multi_tf
        assert rebuilt.filter_tf == "1d"
        assert rebuilt.filter_entry == "adx_trend"
        assert rebuilt.filter_mode == "confirm"
        assert rebuilt.filter_sign == -1
