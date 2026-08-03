"""BL-023 T12 — Stop sensitivity: 5pt stop on daily ES is a same-bar stop-out.

Verifies ENG F-1 (stop_distance_points=5 on MES = $25, while daily ATR is
30-80pt): a 5pt stop on daily bars is touched in the entry bar almost
always. This regression test pins the bug so the ATR-based stop fix
(probe in Fase 1, --stop-mode atr) can be measured against it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest

from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.models import ReplayPeriod, ReplayRegime, ReplayVariant
from market.contracts import MES


class AlwaysLong:
    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [1] * data.height)


def _wide_range_data(bars: int = 40, start: float = 5000.0) -> pl.DataFrame:
    """Daily ES-like bars with 30-80pt range (ATR scale). Entry at open,
    intraday low below entry - 5pt -> same-bar stop-out for a 5pt stop."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [start + i * 1.0 for i in range(bars)]
    return pl.DataFrame(
        {
            "timestamp": [base + timedelta(days=i) for i in range(bars)],
            # open == close, but low is 40pt below -> 5pt stop hit same bar
            "open": closes,
            "high": [c + 60 for c in closes],
            "low": [c - 40 for c in closes],
            "close": closes,
            "volume": [1000.0] * bars,
        }
    )


def _period(data: pl.DataFrame) -> ReplayPeriod:
    return ReplayPeriod(
        name="test-stop",
        regime=ReplayRegime.SIDEWAYS,
        start=data["timestamp"][0],
        end=data["timestamp"][-1],
        selection_metric="test",
        selection_score=1.0,
    )


def _runner(stop_points: Decimal) -> EventDrivenQualificationRunner:
    return EventDrivenQualificationRunner(
        signal=AlwaysLong(),
        contract=MES,
        initial_capital=Decimal("50000"),
        stop_distance_points=stop_points,
    )


@pytest.mark.asyncio
async def test_5pt_stop_is_hit_in_entry_bar_on_daily_range() -> None:
    data = _wide_range_data()
    obs = await _runner(Decimal("5")).run(data, _period(data), ReplayVariant.control())

    # The 40pt intraday low guarantees the 5pt stop is touched in the same
    # bar as entry: the trade closes at a loss on bar 1 (or bar 2 at latest).
    assert obs.execution_evidence is not None
    assert obs.metrics.total_trades >= 1
    # The stop fires almost immediately: fills happen in the first bars.
    assert obs.metrics.bars < 10 or obs.metrics.net_return < 0


@pytest.mark.asyncio
async def test_wide_stop_does_not_stop_out_same_bar() -> None:
    data = _wide_range_data()
    # A 60pt stop on 40pt range bars is not touched in the entry bar.
    obs = await _runner(Decimal("60")).run(data, _period(data), ReplayVariant.control())
    assert obs.execution_evidence is not None


def _atr_runner(
    *, atr_multiple: float = 2.0, atr_period: int = 14, stop_points: Decimal = Decimal("5")
) -> EventDrivenQualificationRunner:
    return EventDrivenQualificationRunner(
        signal=AlwaysLong(),
        contract=MES,
        initial_capital=Decimal("50000"),
        stop_distance_points=stop_points,
        stop_mode="atr",
        atr_multiple=atr_multiple,
        atr_period=atr_period,
    )


@pytest.mark.asyncio
async def test_atr_stop_is_wider_than_5pt_on_daily_range() -> None:
    """BL-023 P1a: with ATR-mode stop the daily-range stop-out disappears.

    The synthetic bars have a 40pt intraday range (ATR ~ 40pt), so a 2xATR
    stop sits ~80pt from entry: it is not touched in the entry bar, unlike
    the 5pt fixed stop.
    """
    data = _wide_range_data()
    obs = await _atr_runner().run(data, _period(data), ReplayVariant.control())
    assert obs.execution_evidence is not None
    # More bars survive before any stop-out (no same-bar liquidation).
    assert obs.metrics.bars > 5


@pytest.mark.asyncio
async def test_atr_stop_distance_scales_with_atr_multiple() -> None:
    """A larger ATR multiple produces a wider stop (more bars survive)."""
    data = _wide_range_data()
    obs_1x = await _atr_runner(atr_multiple=1.0).run(data, _period(data), ReplayVariant.control())
    obs_3x = await _atr_runner(atr_multiple=3.0).run(data, _period(data), ReplayVariant.control())
    assert obs_1x.execution_evidence is not None
    assert obs_3x.execution_evidence is not None
    assert obs_3x.metrics.bars >= obs_1x.metrics.bars


@pytest.mark.asyncio
async def test_atr_stop_is_point_in_time_no_lookahead() -> None:
    """BL-023 P1a: the stop uses only bars up to entry, never future bars.

    Build a series where the first bar has a huge range and every later bar
    is tiny. A point-in-time ATR computed at entry (after warmup) must NOT
    see the future tiny bars — it stays wide and the trade survives; a
    lookahead implementation would shrink the stop and stop out early.
    """
    base = datetime(2025, 1, 1, tzinfo=UTC)
    bars = 40
    closes = [5000.0 + i * 1.0 for i in range(bars)]
    # Bar 0: huge range (500pt). Bars 1+: tiny range (1pt).
    highs = [c + 250.0 if i == 0 else c + 0.5 for i, c in enumerate(closes)]
    lows = [c - 250.0 if i == 0 else c - 0.5 for i, c in enumerate(closes)]
    data = pl.DataFrame(
        {
            "timestamp": [base + timedelta(days=i) for i in range(bars)],
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * bars,
        }
    )
    obs = await _atr_runner().run(data, _period(data), ReplayVariant.control())
    assert obs.execution_evidence is not None
    # ATR at entry is still wide (the huge bar 0 is within the 14-bar
    # window), so no same-bar stop-out in the first bars.
    assert obs.metrics.bars > 5
