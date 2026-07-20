"""Tests for the auditable M31 event-driven replay path."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest

from analytics.backtest.engines.vectorized import sma_crossover_signal
from analytics.qualification import build_offline_intelligence_artifact
from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.models import ReplayPeriod, ReplayRegime, ReplayVariant
from market.contracts import ES


def _data() -> pl.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [10, 9, 8, 9, 10, 11, 10, 9, 8, 9, 10, 11]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=index) for index in range(len(closes))],
            "open": [float(value) for value in closes],
            "high": [float(value) + 1 for value in closes],
            "low": [float(value) - 1 for value in closes],
            "close": [float(value) for value in closes],
            "volume": [1000.0] * len(closes),
        }
    )


def _period(data: pl.DataFrame) -> ReplayPeriod:
    return ReplayPeriod(
        name="test-period",
        regime=ReplayRegime.SIDEWAYS,
        start=data["timestamp"][0],
        end=data["timestamp"][-1],
        selection_metric="test",
        selection_score=1.0,
    )


@pytest.mark.asyncio
async def test_replay_exercises_and_reconciles_full_state_chain() -> None:
    data = _data()
    runner = EventDrivenQualificationRunner(
        signal=sma_crossover_signal(fast=2, slow=3),
        contract=ES,
        initial_capital=Decimal("50000"),
        stop_distance_points=Decimal("1"),
    )

    observation = await runner.run(data, _period(data), ReplayVariant.control())

    evidence = observation.execution_evidence
    assert evidence is not None
    assert evidence.risk_checks > 0
    assert evidence.orders_persisted > 0
    assert evidence.fills_recorded > 0
    assert evidence.ledger_entries >= evidence.fills_recorded
    assert evidence.reconciliation_runs == 1
    assert evidence.reconciliation_clean
    assert evidence.reconciliation_mismatches == 0
    assert evidence.flattened
    assert observation.metrics.decision_latency_ms_p95 is not None
    assert observation.metrics.factor_attribution
    assert observation.metrics.luck_p_value is not None


@pytest.mark.asyncio
async def test_replay_computes_signals_only_on_historical_prefixes() -> None:
    data = _data()

    class RecordingSignal:
        def __init__(self) -> None:
            self.heights: list[int] = []

        def compute(self, prefix: pl.DataFrame) -> pl.Series:
            self.heights.append(prefix.height)
            return pl.Series("signal", [0] * prefix.height)

    signal = RecordingSignal()
    runner = EventDrivenQualificationRunner(
        signal=signal, contract=ES, initial_capital=Decimal("50000")
    )

    await runner.run(data, _period(data), ReplayVariant.control())

    assert signal.heights == list(range(1, data.height))


@pytest.mark.asyncio
async def test_replay_refuses_to_fabricate_intelligence_variant() -> None:
    data = _data()
    runner = EventDrivenQualificationRunner(
        signal=sma_crossover_signal(fast=2, slow=3), contract=ES, initial_capital=Decimal("50000")
    )

    with pytest.raises(ValueError, match="cannot fabricate intelligence variant"):
        await runner.run(data, _period(data), ReplayVariant.factorial()[1])


@pytest.mark.asyncio
async def test_replay_accepts_matching_hashed_offline_intelligence_artifact() -> None:
    data = _data()
    period = _period(data)
    variant = ReplayVariant.factorial()[1]
    artifact = build_offline_intelligence_artifact(period, variant)
    runner = EventDrivenQualificationRunner(
        signal=sma_crossover_signal(fast=2, slow=3), contract=ES, initial_capital=Decimal("50000")
    )

    observation = await runner.run(data, period, variant, artifact)

    assert observation.execution_evidence is not None
    assert observation.execution_evidence.intelligence_artifact == artifact


@pytest.mark.asyncio
async def test_replay_executes_protective_stop_inside_bar() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    data = pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=index) for index in range(4)],
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [100.0, 100.0, 101.0, 101.0],
            "low": [100.0, 100.0, 90.0, 99.0],
            "close": [100.0, 100.0, 90.0, 100.0],
            "volume": [1000.0] * 4,
        }
    )

    class AlwaysLong:
        def compute(self, prefix: pl.DataFrame) -> pl.Series:
            return pl.Series("signal", [1] * prefix.height)

    runner = EventDrivenQualificationRunner(
        signal=AlwaysLong(),
        contract=ES,
        initial_capital=Decimal("50000"),
        stop_distance_points=Decimal("1"),
    )
    observation = await runner.run(data, _period(data), ReplayVariant.control())

    assert observation.metrics.hard_breaches == 0
    assert observation.execution_evidence is not None
    assert observation.execution_evidence.flattened
