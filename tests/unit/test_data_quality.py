"""Tests for data quality detection (duplicate, gap, outlier, leakage)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.data.quality import (
    check_future_leakage,
    find_duplicates,
    find_gaps,
    find_outliers,
)

UTC = timezone.utc


class TestFindDuplicates:
    """Duplicate detection."""

    def test_empty_list(self) -> None:
        assert find_duplicates([]) == []

    def test_no_duplicates(self) -> None:
        records = [
            {"id": "1", "price": 100},
            {"id": "2", "price": 101},
        ]
        assert find_duplicates(records, id_key="id") == []

    def test_finds_duplicate(self) -> None:
        records = [
            {"id": "1", "price": 100},
            {"id": "1", "price": 100},
        ]
        assert find_duplicates(records, id_key="id") == [1]

    def test_duplicate_without_id_key(self) -> None:
        records = [
            {"timestamp": "2026-01-01", "price": 100},
            {"timestamp": "2026-01-01", "price": 100},
            {"timestamp": "2026-01-02", "price": 101},
        ]
        dups = find_duplicates(records, timestamp_key="timestamp")
        assert dups == [1]

    def test_multiple_duplicates(self) -> None:
        records = [{"id": str(i // 2)} for i in range(6)]
        assert len(find_duplicates(records, id_key="id")) == 3


class TestFindGaps:
    """Gap detection in timestamp sequences."""

    def test_empty_list(self) -> None:
        assert find_gaps([]) == []

    def test_no_gaps(self) -> None:
        base = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        timestamps = [base + timedelta(hours=i) for i in range(5)]
        assert find_gaps(timestamps) == []

    def test_detects_gap(self) -> None:
        base = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        timestamps = [
            base,
            base + timedelta(hours=1),
            base + timedelta(hours=5),  # 4h gap, expected 1h + 5min tolerance
        ]
        gaps = find_gaps(timestamps)
        assert len(gaps) == 1
        assert gaps[0][2] == timestamps[1]
        assert gaps[0][3] == timestamps[2]

    def test_accepts_tolerance(self) -> None:
        base = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
        timestamps = [
            base,
            base + timedelta(hours=1, minutes=3),  # 3 min late, within 5min tolerance
        ]
        assert find_gaps(timestamps) == []

    def test_single_timestamp(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        assert find_gaps([base]) == []


class TestFindOutliers:
    """Outlier detection."""

    def test_short_sequence(self) -> None:
        assert find_outliers([1, 2, 3], window=10) == []

    def test_no_outliers(self) -> None:
        vals = [100 + i for i in range(50)]
        assert find_outliers(vals, threshold=3.0) == []

    def test_detects_outlier_zscore(self) -> None:
        vals = [100.0] * 30 + [5000.0] + [100.0] * 10
        outliers = find_outliers(vals, threshold=2.0)
        assert len(outliers) == 1
        assert outliers[0] == 30  # The spike at index 30

    def test_detects_outlier_iqr(self) -> None:
        vals = [10] * 20 + [1000] + [10] * 20
        outliers = find_outliers(vals, method="iqr")
        assert len(outliers) == 1

    def test_iqr_multiple_outliers(self) -> None:
        vals = [10] * 20 + [1000, 2000] + [10] * 20
        outliers = find_outliers(vals, method="iqr")
        assert len(outliers) == 2


class TestFutureLeakage:
    """Future data leakage detection."""

    def test_no_leak(self) -> None:
        base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        records = [
            {"event_time": base, "available_at": base + timedelta(seconds=1)},
        ]
        assert check_future_leakage(records) == []

    def test_detects_leak(self) -> None:
        base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        records = [
            {"event_time": base, "available_at": base - timedelta(hours=1)},
        ]
        leaks = check_future_leakage(records)
        assert len(leaks) == 1
