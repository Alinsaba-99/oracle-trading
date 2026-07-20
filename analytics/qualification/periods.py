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
) -> PeriodSelection:
    """Select deterministic stress windows before any strategy is executed."""
    if window_bars < 10:
        raise ValueError("window_bars must be at least 10")

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
        end_index = _select_index(scores[regime], used_end_indices, descending[regime])
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
    macro_period = _select_macro_period(frame, window_bars, macro_events or [], used_end_indices)
    if macro_period is None:
        blockers.append(
            "Macro surprise regime missing: provide point-in-time actual, consensus, "
            "available_at, and source evidence."
        )
    else:
        periods.append(macro_period)

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


def _select_index(series: pd.Series, used: set[int], descending: bool) -> int:
    valid = series.replace([np.inf, -np.inf], np.nan).dropna()
    ordered = valid.sort_values(ascending=not descending)
    for index in ordered.index:
        numeric_index = int(index)
        if numeric_index not in used:
            return numeric_index
    raise ValueError("Unable to select distinct replay periods from the available data")


def _select_macro_period(
    frame: pd.DataFrame,
    window_bars: int,
    macro_events: list[MacroSurpriseEvent],
    used_end_indices: set[int],
) -> ReplayPeriod | None:
    if not macro_events:
        return None

    timestamps = pd.DatetimeIndex(frame["timestamp"])
    ranked_events = sorted(macro_events, key=lambda event: event.absolute_surprise, reverse=True)
    for event in ranked_events:
        event_time = pd.Timestamp(event.event_time)
        if event_time.tzinfo is None:
            event_time = event_time.tz_localize(UTC)
        else:
            event_time = event_time.tz_convert(UTC)
        event_index = int(timestamps.searchsorted(event_time, side="left"))
        if event_index >= len(frame):
            continue
        start_index = max(0, event_index - window_bars // 2)
        end_index = min(len(frame) - 1, start_index + window_bars - 1)
        start_index = max(0, end_index - window_bars + 1)
        if end_index in used_end_indices:
            continue
        return ReplayPeriod(
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
    return None


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
