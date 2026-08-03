"""BL-023 T11 — Sharpe/Sortino/Calmar annualization parameterized by timeframe.

Verifies ENG F-17: sqrt(252) hardcoded overstated 1h Sharpe by ~4.8x.
The runner must scale by periods_per_year (252 daily, ~5796 1h).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest

from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.models import ReplayPeriod, ReplayRegime, ReplayVariant
from analytics.strategy.signals import EmaTrend
from market.contracts import ES


def _data() -> pl.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [100 + i * 0.1 for i in range(60)]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=i) for i in range(len(closes))],
            "open": [c - 0.1 for c in closes],
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(closes),
        }
    )


def _period(data: pl.DataFrame) -> ReplayPeriod:
    return ReplayPeriod(
        name="test-ann",
        regime=ReplayRegime.BULL,
        start=data["timestamp"][0],
        end=data["timestamp"][-1],
        selection_metric="test",
        selection_score=1.0,
    )


def _make_runner(ppy: int) -> EventDrivenQualificationRunner:
    return EventDrivenQualificationRunner(
        signal=EmaTrend(fast=3, slow=5),
        contract=ES,
        initial_capital=Decimal("50000"),
        stop_distance_points=Decimal("10"),
        periods_per_year=ppy,
    )


@pytest.mark.asyncio
async def test_sharpe_scales_with_periods_per_year() -> None:
    data = _data()
    period = _period(data)
    daily = await _make_runner(252).run(data, period, ReplayVariant.control())
    hourly = await _make_runner(5796).run(data, period, ReplayVariant.control())

    assert daily.metrics.sharpe_ratio is not None
    assert hourly.metrics.sharpe_ratio is not None
    # sqrt(5796/252) ~= 4.796 — the 1h Sharpe must be much larger than daily
    # on the same return series (annualization factor, not overstatement).
    assert hourly.metrics.sharpe_ratio > daily.metrics.sharpe_ratio * 3


@pytest.mark.asyncio
async def test_default_periods_per_year_is_252() -> None:
    data = _data()
    runner = EventDrivenQualificationRunner(
        signal=EmaTrend(fast=3, slow=5),
        contract=ES,
        initial_capital=Decimal("50000"),
        stop_distance_points=Decimal("10"),
    )
    obs = await runner.run(data, _period(data), ReplayVariant.control())
    default = obs.metrics.sharpe_ratio
    explicit = await _make_runner(252).run(data, _period(data), ReplayVariant.control())
    assert default == explicit.metrics.sharpe_ratio


@pytest.mark.asyncio
async def test_invalid_periods_per_year_rejected() -> None:
    with pytest.raises(ValueError):
        EventDrivenQualificationRunner(
            signal=EmaTrend(fast=3, slow=5),
            contract=ES,
            initial_capital=Decimal("50000"),
            periods_per_year=0,
        )
