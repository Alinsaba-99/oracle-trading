"""BL-023 T9/T10 — Liquidation mechanics on hard breach.

Verifies ENG F-01/F-11/F-12: after the first hard breach the replay
liquidates (position closed, no new trades, equity flat) and the
observation is flagged `liquidated` with an honest event count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import polars as pl
import pytest

from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.models import ReplayPeriod, ReplayRegime, ReplayVariant
from market.contracts import MES
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


class AlwaysLong:
    """Test signal: always target +1 (long bias) — forces a losing streak
    when prices fall, which trips the prop-firm daily/overall loss."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [1] * data.height)


def _falling_data(bars: int = 60, start: float = 5000.0, step: float = -8.0) -> pl.DataFrame:
    """Monotonic falling daily closes: -8pt/bar * $5/pt * qty2 = -$80/bar."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [start + step * i for i in range(bars)]
    return pl.DataFrame(
        {
            "timestamp": [base + timedelta(days=i) for i in range(bars)],
            "open": [c - 1 for c in closes],
            "high": [c + 2 for c in closes],
            "low": [c - 3 for c in closes],
            "close": closes,
            "volume": [1000.0] * bars,
        }
    )


def _gap_down_data(bars: int = 12) -> pl.DataFrame:
    """Flat market that gaps down 150pt on bar 2.

    Entry at bar 1 open (5000); bar 2 opens at 4850 which is BELOW the
    50pt stop (4950) — the stop fill price becomes the OPEN (gap through
    stop, execution.py:_stop_fill_price:756-757), realising a loss far
    larger than the projected risk. qty2 → (4850-5000)*$5*2 = -$1500
    which exceeds the $1000 daily-loss limit → genuine hard breach.
    """
    base = datetime(2025, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(bars):
        ts = base + timedelta(days=i)
        if i == 2:
            o, hi, lo, c = 4850.0, 4860.0, 4840.0, 4850.0
        else:
            o, hi, lo, c = 5000.0, 5005.0, 4995.0, 5000.0
        rows.append(
            {"timestamp": ts, "open": o, "high": hi, "low": lo, "close": c, "volume": 1000.0}
        )
    return pl.DataFrame(rows)


def _period(data: pl.DataFrame) -> ReplayPeriod:
    return ReplayPeriod(
        name="test-liquidate",
        regime=ReplayRegime.BEAR,
        start=data["timestamp"][0],
        end=data["timestamp"][-1],
        selection_metric="test",
        selection_score=1.0,
    )


def _runner(**kwargs: Any) -> EventDrivenQualificationRunner:
    defaults: dict[str, Any] = {
        "signal": AlwaysLong(),
        "contract": MES,
        "initial_capital": Decimal(str(TOPSTEP_TC_50K.account_size)),
        "stop_distance_points": Decimal("5"),
    }
    defaults.update(kwargs)
    return EventDrivenQualificationRunner(**defaults)


@pytest.mark.asyncio
async def test_hard_breach_triggers_liquidation_and_halts_trading() -> None:
    # Gap-through-stop: the loss (-$1500) exceeds the daily limit ($1000)
    # → genuine hard breach that the risk gate cannot pre-reject (the gap
    # fill price is worse than the projected stop price).
    data = _gap_down_data()
    runner = _runner(quantity=Decimal("2"), stop_distance_points=Decimal("50"))
    obs = await runner.run(data, _period(data), ReplayVariant.control())

    assert obs.metrics.liquidated is True
    assert obs.metrics.hard_breaches == 1  # event count, not type count
    # The position was closed at the breach bar.
    assert obs.execution_evidence is not None
    assert obs.execution_evidence.flattened


@pytest.mark.asyncio
async def test_no_new_trades_after_liquidation() -> None:
    data = _gap_down_data(bars=12)
    runner = _runner(quantity=Decimal("2"), stop_distance_points=Decimal("50"))
    obs = await runner.run(data, _period(data), ReplayVariant.control())

    # With liquidation, the run must NOT keep trading after the breach:
    # exactly one open + one close fill (the gap-stop close), then halt —
    # even though the signal stays long for the remaining bars.
    assert obs.execution_evidence is not None
    assert obs.execution_evidence.fills_recorded <= 2


@pytest.mark.asyncio
async def test_no_liquidation_without_breach() -> None:
    data = _falling_data(step=-0.5)  # tiny step: -0.5pt/bar, no breach
    runner = _runner(quantity=Decimal("1"))
    obs = await runner.run(data, _period(data), ReplayVariant.control())

    assert obs.metrics.liquidated is False
    assert obs.metrics.hard_breaches == 0


@pytest.mark.asyncio
async def test_liquidation_flag_can_be_disabled_for_legacy_parity() -> None:
    data = _falling_data()
    runner = _runner(quantity=Decimal("2"), liquidate_on_hard_breach=False)
    obs = await runner.run(data, _period(data), ReplayVariant.control())

    # Legacy behaviour: breach detected but the replay keeps running.
    assert obs.metrics.liquidated is False
