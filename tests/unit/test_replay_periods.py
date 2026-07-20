"""Tests for deterministic M31 period selection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from analytics.qualification.models import MacroSurpriseEvent, ReplayRegime
from analytics.qualification.periods import select_replay_periods, slice_period


def _market_data(rows: int = 240) -> pl.DataFrame:
    timestamps = [datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index) for index in range(rows)]
    trend = np.concatenate(
        [
            np.linspace(100, 130, 60),
            np.linspace(130, 90, 60),
            np.linspace(90, 92, 60),
            92 + np.sin(np.arange(60)) * np.linspace(1, 12, 60),
        ]
    )
    volume = np.full(rows, 1_000.0)
    volume[200] = 50_000.0
    return pl.DataFrame(
        {
            "Date": timestamps,
            "Open": trend * 0.999,
            "High": trend * 1.01,
            "Low": trend * 0.99,
            "Close": trend,
            "Volume": volume,
        }
    )


def test_selects_five_market_regimes_and_blocks_missing_macro() -> None:
    selection = select_replay_periods(_market_data(), window_bars=30)

    assert {period.regime for period in selection.periods} == {
        ReplayRegime.BULL,
        ReplayRegime.BEAR,
        ReplayRegime.SIDEWAYS,
        ReplayRegime.HIGH_VOLATILITY,
        ReplayRegime.LIQUIDITY_SHOCK,
    }
    assert selection.blockers
    assert "Macro surprise" in selection.blockers[0]
    assert all(
        slice_period(selection.normalized_data, period).height == 30 for period in selection.periods
    )


def test_selects_macro_surprise_from_point_in_time_event() -> None:
    event_time = datetime(2025, 7, 20, 13, 30, tzinfo=UTC)
    event = MacroSurpriseEvent(
        event_time=event_time,
        available_at=event_time,
        indicator="CPI",
        actual=3.4,
        consensus=3.1,
        source="BLS release archive",
    )

    selection = select_replay_periods(_market_data(), window_bars=30, macro_events=[event])

    assert not selection.blockers
    macro_period = next(
        period for period in selection.periods if period.regime == ReplayRegime.MACRO_SURPRISE
    )
    assert macro_period.event_label == "CPI"
    assert macro_period.available_at == event_time


def test_macro_event_cannot_be_available_before_release() -> None:
    event_time = datetime(2025, 7, 20, 13, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="available_at"):
        MacroSurpriseEvent(
            event_time=event_time,
            available_at=event_time - timedelta(seconds=1),
            indicator="CPI",
            actual=3.4,
            consensus=3.1,
            source="BLS release archive",
        )


def test_slice_period_includes_only_requested_warmup_bars_before_start() -> None:
    data = _market_data()
    period = select_replay_periods(data, window_bars=30).periods[0]

    warm = slice_period(data, period, warmup_bars=7)

    assert warm.height == 37
    assert warm["timestamp"][7] == period.start
