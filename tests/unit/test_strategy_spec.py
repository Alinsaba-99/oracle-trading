"""Offline tests for StrategySpec + the LLM JSON parser."""

from __future__ import annotations

import pytest

from analytics.strategy.researcher import _parse_specs
from analytics.strategy.signals import DonchianBreakout, EmaTrend
from analytics.strategy.spec import StrategySpec


class TestSpec:
    def test_ticker_resolution(self) -> None:
        s = StrategySpec(name="g", instrument="GOLD", entry="donchian_breakout")
        assert s.ticker() == "GC=F"

    def test_build_signal_with_params(self) -> None:
        s = StrategySpec(
            name="d", instrument="SILVER", entry="donchian_breakout", entry_params={"period": 25}
        )
        sig = s.build_signal()
        assert isinstance(sig, DonchianBreakout) and sig.period == 25

    def test_invalid_entry_raises(self) -> None:
        with pytest.raises(ValueError):
            StrategySpec(name="x", instrument="GOLD", entry="bogus").build_signal()


class TestParse:
    def test_parse_plain_array(self) -> None:
        text = (
            '[{"name":"a","instrument":"GOLD","entry":"donchian_breakout",'
            '"entry_params":{"period":20}}]'
        )
        specs = _parse_specs(text, 5)
        assert len(specs) == 1 and specs[0].instrument == "GOLD"

    def test_parse_with_code_fence(self) -> None:
        text = (
            "```json\n"
            '[{"name":"a","instrument":"GOLD","entry":"ema_trend","entry_params":{"fast":10,"slow":30}}]'
            "\n```"
        )
        specs = _parse_specs(text, 5)
        assert len(specs) == 1 and specs[0].entry == "ema_trend"
        assert isinstance(specs[0].build_signal(), EmaTrend)

    def test_parse_drops_malformed(self) -> None:
        # A spec missing a required field (entry) fails pydantic -> dropped.
        text = (
            '[{"name":"a","instrument":"GOLD"},'
            '{"name":"b","instrument":"SILVER","entry":"donchian_breakout"}]'
        )
        specs = _parse_specs(text, 5)
        assert len(specs) == 1  # malformed dropped, valid kept

    def test_parse_returns_empty_on_garbage(self) -> None:
        assert _parse_specs("not json at all", 3) == []
