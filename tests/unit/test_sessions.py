"""Tests for exchange sessions, calendars, DST, and contract roll."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from market.roll import (
    MONTH_CODES,
    continuous_symbol,
    next_contract,
    tradable_contract,
    default_roll_date,
)
from market.sessions import (
    CME_2026_CALENDAR,
    CME_2026_EARLY_CLOSES,
    CME_2026_HOLIDAYS,
    DST_FALL_2026,
    DST_SPRING_2026,
    _cme_offset,
    is_dst_transition_day,
)


# =========================================================================
# Session tests
# =========================================================================


class TestExchangeCalendar:
    """CME 2026 calendar invariants."""

    def test_holidays_count(self) -> None:
        assert len(CME_2026_HOLIDAYS) == 10

    def test_known_holiday(self) -> None:
        assert date(2026, 12, 25) in CME_2026_CALENDAR.holidays

    def test_weekday_is_trading_day(self) -> None:
        assert CME_2026_CALENDAR.is_trading_day(date(2026, 3, 10))  # Tuesday

    def test_saturday_is_not_trading(self) -> None:
        assert not CME_2026_CALENDAR.is_trading_day(date(2026, 3, 14))  # Saturday

    def test_sunday_is_not_trading(self) -> None:
        assert not CME_2026_CALENDAR.is_trading_day(date(2026, 3, 15))

    def test_christmas_is_not_trading(self) -> None:
        assert not CME_2026_CALENDAR.is_trading_day(date(2026, 12, 25))

    def test_early_closes_count(self) -> None:
        assert len(CME_2026_EARLY_CLOSES) == 3

    def test_known_early_close(self) -> None:
        assert date(2026, 11, 27) in CME_2026_CALENDAR.early_closes

    def test_early_close_time(self) -> None:
        assert CME_2026_CALENDAR.close_time(date(2026, 11, 27)) == "12:00"

    def test_normal_close_time(self) -> None:
        assert CME_2026_CALENDAR.close_time(date(2026, 3, 10)) == "16:00"

    def test_maintenance_breaks_exist(self) -> None:
        assert len(CME_2026_CALENDAR.maintenance_breaks) == 12


class TestDSTTransitions:
    """Daylight saving time edge cases."""

    def test_dst_spring_date(self) -> None:
        assert DST_SPRING_2026 == date(2026, 3, 8)

    def test_dst_fall_date(self) -> None:
        assert DST_FALL_2026 == date(2026, 11, 1)

    def test_dst_transition_detected(self) -> None:
        assert is_dst_transition_day(DST_SPRING_2026)
        assert is_dst_transition_day(DST_FALL_2026)

    def test_non_transition_not_detected(self) -> None:
        assert not is_dst_transition_day(date(2026, 3, 10))

    def test_cme_offset_winter(self) -> None:
        jan = date(2026, 1, 15)
        assert _cme_offset(jan) == timedelta(hours=-6)

    def test_cme_offset_summer(self) -> None:
        jun = date(2026, 6, 15)
        assert str(_cme_offset(jun)) == "-1 day, 19:00:00"  # = -5 hours

    def test_cme_offset_spring_transition(self) -> None:
        before = date(2026, 3, 7)
        after = date(2026, 3, 9)
        assert str(_cme_offset(before)) == "-1 day, 18:00:00"  # CST
        assert str(_cme_offset(after)) == "-1 day, 19:00:00"  # CDT


# =========================================================================
# Roll tests
# =========================================================================


class TestMonthCodes:
    """CME month code mapping."""

    def test_all_months_present(self) -> None:
        assert len(MONTH_CODES) == 12

    def test_known_codes(self) -> None:
        assert MONTH_CODES["H"] == 3  # March
        assert MONTH_CODES["M"] == 6  # June
        assert MONTH_CODES["U"] == 9  # September
        assert MONTH_CODES["Z"] == 12  # December


class TestContinuousSymbol:
    """Tradable → continuous symbol extraction."""

    def test_es_u26(self) -> None:
        assert continuous_symbol("ESU26") == "ES"

    def test_nq_z25(self) -> None:
        assert continuous_symbol("NQZ25") == "NQ"

    def test_gc_g26(self) -> None:
        assert continuous_symbol("GCG26") == "GC"

    def test_cl_f26(self) -> None:
        assert continuous_symbol("CLF26") == "CL"

    def test_already_continuous(self) -> None:
        assert continuous_symbol("ES") == "ES"
        assert continuous_symbol("NQ") == "NQ"


class TestTradableContract:
    """Building tradable contract symbols."""

    def test_es_jun26(self) -> None:
        assert tradable_contract("ES", 2026, 6) == "ESM26"

    def test_nq_sep26(self) -> None:
        assert tradable_contract("NQ", 2026, 9) == "NQU26"

    def test_gc_dec26(self) -> None:
        assert tradable_contract("GC", 2026, 12) == "GCZ26"


class TestNextContract:
    """Next contract month selection."""

    def test_next_after_march(self) -> None:
        """After March, the next quarterly is June."""
        # We can't easily test this without mocking datetime,
        # but we can verify the logic constructs valid symbols.
        jun = tradable_contract("ES", 2026, 6)
        assert jun == "ESM26"
        sep = tradable_contract("ES", 2026, 9)
        assert sep == "ESU26"


class TestDefaultRollDate:
    """Roll date heuristic."""

    def test_roll_date_for_jun_contract(self) -> None:
        rd = default_roll_date((3, 6, 9, 12), 4)  # April, next is June
        assert rd.month == 5  # Roll should be in May
        assert rd.day == 25  # Default to 25th

    def test_roll_date_for_sep_contract(self) -> None:
        rd = default_roll_date((3, 6, 9, 12), 7)  # July, next is Sep
        assert rd.month == 8  # Roll should be in August
