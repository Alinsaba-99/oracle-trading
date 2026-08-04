"""Tests for deterministic M31 period selection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise

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


def test_top3_windows_per_regime_yields_honest_n_curves() -> None:
    # BL-023 Fase 5 (ADR-016 §6): top-3 non-overlapping windows per regime
    # = 18 unique curves (6 regimes x 3), not 6. Same-regime windows must
    # never overlap (minimum gap == window_bars), so the N counts
    # independent curves, not re-slices of the same window.
    base = datetime(2025, 1, 1, tzinfo=UTC)
    events = [
        MacroSurpriseEvent(
            event_time=base + timedelta(days=offset, hours=13, minutes=30),
            available_at=base + timedelta(days=offset, hours=13, minutes=30),
            indicator=f"INDICATOR_{offset}",
            actual=float(offset),
            consensus=float(offset - 2),
            source="test archive",
        )
        for offset in (60, 120, 180)
    ]

    selection = select_replay_periods(
        _market_data(), window_bars=30, macro_events=events, windows_per_regime=3
    )

    assert not selection.blockers
    assert len(selection.periods) == 18  # 6 regimes x 3 windows
    regimes = {period.regime for period in selection.periods}
    assert len(regimes) == 6
    for regime in regimes:
        windows = sorted(
            (period for period in selection.periods if period.regime == regime),
            key=lambda period: period.start,
        )
        assert len(windows) == 3, f"{regime}: expected 3 windows"
        for previous, current in pairwise(windows):
            assert current.start > previous.end, f"{regime}: overlapping windows"
        assert all(
            slice_period(selection.normalized_data, period).height == 30 for period in windows
        )
