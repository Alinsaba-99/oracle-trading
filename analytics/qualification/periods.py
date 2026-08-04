"""Point-in-time period selection for historical replay qualification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import sqrt

import numpy as np
import pandas as pd
import polars as pl

from analytics.qualification.models import MacroSurpriseEvent, ReplayPeriod, ReplayRegime


@dataclass(frozen=True)
class PeriodSelection:
    """Selected periods, normalized data, and fail-closed blockers."""

    periods: tuple[ReplayPeriod, ...]
    normalized_data: pl.DataFrame
    blockers: tuple[str, ...]


def normalize_ohlcv(data: pl.DataFrame) -> pl.DataFrame:
    """Normalize common OHLCV column names and timestamps to UTC."""
    aliases = {
        "timestamp": ("timestamp", "date", "datetime", "time"),
        "open": ("open",),
        "high": ("high",),
        "low": ("low",),
        "close": ("close",),
        "volume": ("volume",),
    }
    lower_to_original = {column.strip().lower(): column for column in data.columns}
    selected: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        original = next(
            (
                lower_to_original[candidate]
                for candidate in candidates
                if candidate in lower_to_original
            ),
            None,
        )
        if original is None:
            raise ValueError(f"OHLCV data is missing required column {canonical!r}")
        selected[original] = canonical

    frame = data.select(list(selected)).rename(selected).to_pandas()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.isna().any().any():
        raise ValueError("OHLCV data contains null or non-numeric values")
    frame = frame.sort_values("timestamp")
    if frame["timestamp"].duplicated().any():
        raise ValueError("OHLCV data contains duplicate timestamps")
    return pl.from_pandas(frame.reset_index(drop=True))


def select_replay_periods(
    data: pl.DataFrame,
    *,
    window_bars: int = 40,
    macro_events: list[MacroSurpriseEvent] | None = None,
    windows_per_regime: int = 1,
) -> PeriodSelection:
    """Select deterministic stress windows before any strategy is executed.

    `windows_per_regime` (ADR-016 §6: top-3 = 18 unique curves) selects the
    top-N non-overlapping windows per regime. Windows from different regimes
    may overlap (different regime => different curve by definition); windows
    of the SAME regime never overlap (minimum gap == window_bars), so the N
    is of independent curves, not re-slices of the same window.
    """
    if window_bars < 10:
        raise ValueError("window_bars must be at least 10")
    if windows_per_regime < 1:
        raise ValueError("windows_per_regime must be at least 1")

    normalized = normalize_ohlcv(data)
    if normalized.height < window_bars * 2:
        raise ValueError(
            f"Need at least {window_bars * 2} bars for regime selection, got {normalized.height}"
        )

    frame = normalized.to_pandas()
    close = frame["close"].astype(float)
    returns = close.pct_change()
    rolling_return = close.pct_change(window_bars - 1)
    rolling_volatility = returns.rolling(window_bars).std(ddof=0) * sqrt(252)
    rolling_range = ((frame["high"] - frame["low"]) / close).rolling(window_bars).mean()
    volume_baseline = frame["volume"].rolling(window_bars * 2, min_periods=window_bars).median()
    volume_ratio = frame["volume"] / volume_baseline.replace(0, np.nan)
    liquidity_shock = rolling_range * volume_ratio

    scores = {
        ReplayRegime.BULL: rolling_return,
        ReplayRegime.BEAR: rolling_return,
        ReplayRegime.SIDEWAYS: rolling_return.abs(),
        ReplayRegime.HIGH_VOLATILITY: rolling_volatility,
        ReplayRegime.LIQUIDITY_SHOCK: liquidity_shock,
    }
    descending = {
        ReplayRegime.BULL: True,
        ReplayRegime.BEAR: False,
        ReplayRegime.SIDEWAYS: False,
        ReplayRegime.HIGH_VOLATILITY: True,
        ReplayRegime.LIQUIDITY_SHOCK: True,
    }
    metrics = {
        ReplayRegime.BULL: "rolling_return",
        ReplayRegime.BEAR: "rolling_return",
        ReplayRegime.SIDEWAYS: "absolute_rolling_return",
        ReplayRegime.HIGH_VOLATILITY: "annualized_realized_volatility",
        ReplayRegime.LIQUIDITY_SHOCK: "range_volume_shock_score",
    }

    periods: list[ReplayPeriod] = []
    used_end_indices: set[int] = set()
    for regime in (
        ReplayRegime.BULL,
        ReplayRegime.BEAR,
        ReplayRegime.SIDEWAYS,
        ReplayRegime.HIGH_VOLATILITY,
        ReplayRegime.LIQUIDITY_SHOCK,
    ):
        end_indices = _select_top_indices(
            scores[regime],
            used_end_indices,
            descending=descending[regime],
            count=windows_per_regime,
            min_gap=window_bars,
        )
        for end_index in end_indices:
            used_end_indices.add(end_index)
            start_index = end_index - window_bars + 1
            periods.append(
                ReplayPeriod(
                    name=f"{regime.value}-{_as_utc(frame.iloc[end_index]['timestamp']).date()}",
                    regime=regime,
                    start=_as_utc(frame.iloc[start_index]["timestamp"]),
                    end=_as_utc(frame.iloc[end_index]["timestamp"]),
                    selection_metric=metrics[regime],
                    selection_score=float(scores[regime].iloc[end_index]),
                )
            )

    blockers: list[str] = []
    macro_periods = _select_macro_periods(
        frame, window_bars, macro_events or [], used_end_indices, count=windows_per_regime
    )
    if not macro_periods:
        blockers.append(
            "Macro surprise regime missing: provide point-in-time actual, consensus, "
            "available_at, and source evidence."
        )
    else:
        periods.extend(macro_periods)

    periods.sort(key=lambda period: (period.regime.value, period.start))
    return PeriodSelection(tuple(periods), normalized, tuple(blockers))


def slice_period(data: pl.DataFrame, period: ReplayPeriod, *, warmup_bars: int = 0) -> pl.DataFrame:
    """Return an inclusive replay slice with optional pre-period warm-up bars."""
    if warmup_bars < 0:
        raise ValueError("warmup_bars must be non-negative")
    normalized = normalize_ohlcv(data)
    eligible = normalized.filter(pl.col("timestamp") <= period.end)
    period_start_index = eligible["timestamp"].search_sorted(period.start)
    start_index = max(0, int(period_start_index) - warmup_bars)
    return eligible.slice(start_index)


def _select_top_indices(
    series: pd.Series, used: set[int], *, descending: bool, count: int, min_gap: int
) -> list[int]:
    """Top-`count` indices of `series` with a minimum gap between them.

    `used` end-indices from OTHER regimes are only excluded (never shared),
    not gap-checked: windows of different regimes are different curves by
    definition. The `min_gap` (== window_bars) applies only within the same
    regime so the N is of non-overlapping, independent windows.
    """
    valid = series.replace([np.inf, -np.inf], np.nan).dropna()
    ordered = valid.sort_values(ascending=not descending)
    chosen: list[int] = []
    for index in ordered.index:
        numeric_index = int(index)
        if numeric_index in used or numeric_index in chosen:
            continue
        if any(abs(numeric_index - other) < min_gap for other in chosen):
            continue
        chosen.append(numeric_index)
        if len(chosen) == count:
            break
    return chosen


def _select_macro_periods(
    frame: pd.DataFrame,
    window_bars: int,
    macro_events: list[MacroSurpriseEvent],
    used_end_indices: set[int],
    *,
    count: int,
) -> list[ReplayPeriod]:
    """Select the top-`count` macro-surprise windows (ADR-016 §6).

    Events are ranked by absolute surprise; windows are placed around each
    event and must not overlap each other (gap >= window_bars) nor reuse an
    end index already claimed by a price-based regime period. When the
    centered placement collides, deterministic fallbacks are tried (window
    ending at the event, then window starting at the event) so a collision
    does not silently reduce the honest N.
    """
    if not macro_events:
        return []

    timestamps = pd.DatetimeIndex(frame["timestamp"])
    ranked_events = sorted(macro_events, key=lambda event: event.absolute_surprise, reverse=True)
    periods: list[ReplayPeriod] = []
    macro_end_indices: list[int] = []
    for event in ranked_events:
        event_time = pd.Timestamp(event.event_time)
        if event_time.tzinfo is None:
            event_time = event_time.tz_localize(UTC)
        else:
            event_time = event_time.tz_convert(UTC)
        event_index = int(timestamps.searchsorted(event_time, side="left"))
        if event_index >= len(frame):
            continue
        placed = False
        for start_hint in (
            max(0, event_index - window_bars // 2),  # centered on the event
            max(0, event_index - window_bars + 1),  # event at window end
            event_index,  # event at window start
        ):
            end_index = min(len(frame) - 1, start_hint + window_bars - 1)
            start_index = max(0, end_index - window_bars + 1)
            if end_index in used_end_indices or end_index in macro_end_indices:
                continue
            if any(abs(end_index - other) < window_bars for other in macro_end_indices):
                continue
            macro_end_indices.append(end_index)
            periods.append(
                ReplayPeriod(
                    name=(
                        f"{ReplayRegime.MACRO_SURPRISE.value}-"
                        f"{_as_utc(frame.iloc[event_index]['timestamp']).date()}"
                    ),
                    regime=ReplayRegime.MACRO_SURPRISE,
                    start=_as_utc(frame.iloc[start_index]["timestamp"]),
                    end=_as_utc(frame.iloc[end_index]["timestamp"]),
                    selection_metric="absolute_actual_minus_consensus",
                    selection_score=event.absolute_surprise,
                    source=event.source,
                    event_label=event.indicator,
                    available_at=event.available_at,
                )
            )
            placed = True
            break
        if placed and len(periods) == count:
            break
    return periods


def _as_utc(value: object) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    converted = timestamp.to_pydatetime()
    if not isinstance(converted, datetime):
        raise TypeError("Timestamp conversion did not return datetime")
    return converted
