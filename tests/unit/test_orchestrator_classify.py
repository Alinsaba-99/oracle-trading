"""BL-304 — Orchestrator state machine unit tests."""

from __future__ import annotations

from datetime import date

from market.ingestion.orchestrator import classify_report
from market.ingestion.pipeline import FetchReport, _is_weekend_only_range


def _report(
    *, note: str = "", rows_in: int = 0, rows_out: int = 0, rows_rejected: int = 0
) -> FetchReport:
    return FetchReport(
        source="test",
        symbol="ES",
        timeframe="1h",
        note=note,
        rows_in=rows_in,
        rows_out=rows_out,
        rows_rejected=rows_rejected,
    )


def test_classify_ok_when_bars_written() -> None:
    r = _report(note="", rows_in=100, rows_out=100)
    assert classify_report(r) == "ok"


def test_classify_failed_on_source_exception_note() -> None:
    r = _report(note="FAILED: ConnectionError: timeout", rows_in=0, rows_out=0)
    assert classify_report(r) == "failed"


def test_classify_failed_when_source_returns_nothing() -> None:
    # rows_in == 0: the source answered nothing at all -> real problem
    r = _report(note="NO_DATA", rows_in=0, rows_out=0)
    assert classify_report(r) == "failed"


def test_classify_failed_when_all_rows_rejected() -> None:
    # rows_in > 0 but everything rejected by quality checks -> not "fresh"
    r = _report(note="NO_DATA", rows_in=100, rows_out=0, rows_rejected=100)
    assert classify_report(r) == "failed"


def test_classify_fresh_when_already_up_to_date() -> None:
    # Weekend re-run: source answered, bars were all duplicates -> done
    r = _report(note="NO_DATA", rows_in=1440, rows_out=0, rows_rejected=0)
    assert classify_report(r) == "fresh"


def test_classify_fresh_on_weekend_only_window() -> None:
    # BL-307: FX/metals sources print no quotes on Sat/Sun. An empty
    # answer over a weekend-only window is expected, not an error —
    # otherwise the perpetual refresh poisons `failed` every weekend.
    r = _report(note="NO_DATA_WEEKEND", rows_in=0, rows_out=0)
    assert classify_report(r) == "fresh"


def test_weekend_only_range_detection() -> None:
    # 2026-08-01 is a Saturday, 2026-08-02 a Sunday.
    assert _is_weekend_only_range(date(2026, 8, 1), date(2026, 8, 1))
    assert _is_weekend_only_range(date(2026, 8, 1), date(2026, 8, 2))
    # Any weekday inside the window makes it NOT weekend-only.
    assert not _is_weekend_only_range(date(2026, 7, 31), date(2026, 8, 2))
    assert not _is_weekend_only_range(date(2026, 8, 1), date(2026, 8, 3))
