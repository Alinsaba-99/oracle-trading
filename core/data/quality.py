"""Data quality detection — duplicate, gap, outlier, and leakage probes.

These functions detect common data quality issues in market data
feeds before they reach the backtest or qualification engine.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class DataQualityWarning(Exception):
    """Warning about a data quality issue."""


def find_duplicates(
    records: list[dict[str, Any]], timestamp_key: str = "timestamp", id_key: str | None = None
) -> list[int]:
    """Find duplicate records in a list of dictionaries.

    Args:
        records: List of record dicts.
        timestamp_key: Key for the timestamp field.
        id_key: Optional key for a unique identifier (if None, uses
                timestamp + all other fields for comparison).

    Returns:
        List of indices of duplicate records (second+ occurrence).
    """
    seen: set[Any] = set()
    duplicates: list[int] = []

    for i, rec in enumerate(records):
        if id_key and id_key in rec:
            key = rec[id_key]
        else:
            # Use timestamp + sorted fields as composite key
            ts = rec.get(timestamp_key, "")
            fields = tuple(sorted((k, v) for k, v in rec.items() if k != timestamp_key))
            key = (ts, fields)

        if key in seen:
            duplicates.append(i)
        else:
            seen.add(key)

    return duplicates


def find_gaps(
    timestamps: list[datetime],
    *,
    expected_interval: timedelta = timedelta(minutes=60),
    tolerance: timedelta = timedelta(minutes=5),
) -> list[tuple[int, int, datetime, datetime]]:
    """Find gaps in a sequence of timestamps.

    Args:
        timestamps: Sorted list of UTC datetimes.
        expected_interval: Expected interval between consecutive timestamps.
        tolerance: Allowed deviation from expected interval.

    Returns:
        List of (prev_idx, next_idx, prev_ts, next_ts) for each gap found.
    """
    if len(timestamps) < 2:
        return []

    gaps: list[tuple[int, int, datetime, datetime]] = []
    max_allowed = expected_interval + tolerance

    for i in range(len(timestamps) - 1):
        diff = timestamps[i + 1] - timestamps[i]
        if diff > max_allowed:
            gaps.append((i, i + 1, timestamps[i], timestamps[i + 1]))

    return gaps


def find_outliers(
    values: list[float], *, method: str = "zscore", threshold: float = 3.0, window: int = 20
) -> list[int]:
    """Find outlier values using z-score or IQR method.

    Args:
        values: List of numeric values.
        method: ``zscore`` (deviation from rolling mean) or ``iqr``.
        threshold: Z-score threshold (default 3.0).
        window: Rolling window size for z-score (default 20).

    Returns:
        List of indices identified as outliers.
    """
    if len(values) < window:
        return []

    outliers: list[int] = []

    if method == "zscore":
        for i in range(window, len(values)):
            window_vals = values[i - window : i]
            mean = sum(window_vals) / len(window_vals)
            variance = sum((x - mean) ** 2 for x in window_vals) / len(window_vals)
            std = variance**0.5
            if std > 0 and abs(values[i] - mean) / std > threshold:
                outliers.append(i)
            elif std == 0 and abs(values[i] - mean) > 0:
                # All window values identical, any deviation is an outlier
                outliers.append(i)

    elif method == "iqr":
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        for i, v in enumerate(values):
            if v < lower or v > upper:
                outliers.append(i)

    return outliers


def check_future_leakage(
    records: list[dict[str, Any]],
    *,
    event_time_key: str = "event_time",
    available_at_key: str = "available_at",
) -> list[int]:
    """Check for future leakage: records where ``available_at`` < ``event_time``.

    This indicates that data was "available" before the event occurred,
    which is a time-travel leak.

    Returns:
        List of indices of leaked records.
    """
    leaks: list[int] = []
    for i, rec in enumerate(records):
        event = rec.get(event_time_key)
        available = rec.get(available_at_key)
        if event and available and available < event:
            leaks.append(i)
    return leaks
