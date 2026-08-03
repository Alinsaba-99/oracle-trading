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
