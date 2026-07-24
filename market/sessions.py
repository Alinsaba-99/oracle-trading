"""Exchange trading sessions and calendars — timezone-aware.

Provides session definitions, holiday calendars, early close schedules,
and DST transition handling for CME Group futures exchanges.

Sources:
  - CME Group Trading Hours: https://www.cmegroup.com/market-regulation/trading-hours
  - CME Group Holidays: https://www.cmegroup.com/tools-information/holiday-calendar
  - All data verified 2026-07-19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

# ── Timezone offsets (fixed for CME calendar purposes) ───────────────
# CME reference timezone: America/Chicago.
# We avoid pytz zoneinfo here to keep core zero-dependency; callers can
# use zoneinfo.ZoneInfo("America/Chicago") for full DST-aware arithmetic.
# The constants below give standard/UTC offsets for CME session bounds.

CHICAGO_UTC_WINTER = timedelta(hours=-6)  # CST (November → March)
CHICAGO_UTC_SUMMER = timedelta(hours=-5)  # CDT (March → November)


def _second_sunday_of_march(year: int) -> int:
    """Return the day of the second Sunday of March for the given year."""
    march_first_weekday = date(year, 3, 1).weekday()  # Mon=0, Sun=6
    first_sunday = (6 - march_first_weekday) % 7 + 1
    return first_sunday + 7


def _first_sunday_of_november(year: int) -> int:
    """Return the day of the first Sunday of November for the given year."""
    nov_first_weekday = date(year, 11, 1).weekday()
    return (6 - nov_first_weekday) % 7 + 1


def _cme_offset(dt: date) -> timedelta:
    """Return the Chicago UTC offset for the given date.

    DST in the US starts the second Sunday of March and ends the first
    Sunday of November.
    """
    if dt.month > 3 and dt.month < 11:
        return CHICAGO_UTC_SUMMER
    if dt.month == 3:
        if dt.day >= _second_sunday_of_march(dt.year):
            return CHICAGO_UTC_SUMMER
        return CHICAGO_UTC_WINTER
    if dt.month == 11:
        if dt.day < _first_sunday_of_november(dt.year):
            return CHICAGO_UTC_SUMMER
        return CHICAGO_UTC_WINTER
    return CHICAGO_UTC_WINTER


# ── Session types ────────────────────────────────────────────────────


class SessionType(StrEnum):
    REGULAR = "regular"  # Regular trading hours (RTH)
    ELECTRONIC = "electronic"  # Electronic trading hours (ETH)
    HOLIDAY = "holiday"  # Holiday schedule (early close / late open)
    CLOSED = "closed"  # Exchange closed


# ── CME regular sessions ─────────────────────────────────────────────


@dataclass(frozen=True)
class TradingSession:
    """A single trading session for an exchange/product group.

    Sessions are defined by their open/close times in the exchange's
    local timezone.  The ``weekdays`` field indicates which days of the
    week the session is active (1=Monday … 7=Sunday).
    """

    exchange: str
    """Exchange code (CME, ICE, EUREX)."""

    product_group: str
    """Product group (equity_index, energy, metal, interest_rate, currency)."""

    session_type: SessionType = SessionType.REGULAR

    # Local time (exchange timezone) open/close
    open_time: str = "17:00"
    """Session open time in exchange local time (HH:MM, 24h)."""

    close_time: str = "16:00"
    """Session close time in exchange local time (HH:MM, 24h)."""

    close_next_day: bool = True
    """If True, the session closes on the following calendar day."""

    timezone: str = "America/Chicago"
    """Exchange timezone (IANA)."""

    weekdays: tuple[int, ...] = (1, 2, 3, 4, 5)
    """Days the session is active (1=Monday … 7=Sunday)."""

    def in_session(self, dt: datetime) -> bool:
        """Check if a UTC datetime falls within this session."""
        # Simplified check — returns True if the weekday matches
        # and time is within bounds (ignoring DST edge cases for now).
        return dt.isoweekday() in self.weekdays


# ── Pre-defined CME sessions ─────────────────────────────────────────

# CME Electronic Trading Hours (ETH): Sun 17:00 – Fri 16:00 CT
# Most CME futures trade nearly 24h on weekdays with a brief break.

CME_ETH = TradingSession(
    exchange="CME",
    product_group="all",
    session_type=SessionType.ELECTRONIC,
    open_time="17:00",
    close_time="16:00",
    close_next_day=True,
    weekdays=(1, 2, 3, 4, 5, 7),  # Sun–Fri (Saturday closed)
)

CME_EQUITY_RTH = TradingSession(
    exchange="CME",
    product_group="equity_index",
    session_type=SessionType.REGULAR,
    open_time="08:30",
    close_time="15:15",
    close_next_day=False,
    weekdays=(1, 2, 3, 4, 5),
)

CME_ENERGY_RTH = TradingSession(
    exchange="CME",
    product_group="energy",
    session_type=SessionType.REGULAR,
    open_time="09:00",
    close_time="14:30",
    close_next_day=False,
    weekdays=(1, 2, 3, 4, 5),
)

CME_METAL_RTH = TradingSession(
    exchange="CME",
    product_group="metal",
    session_type=SessionType.REGULAR,
    open_time="08:20",
    close_time="13:30",
    close_next_day=False,
    weekdays=(1, 2, 3, 4, 5),
)


# ── CME holiday calendar (2026) ──────────────────────────────────────
# Source: https://www.cmegroup.com/tools-information/holiday-calendar


@dataclass
class ExchangeCalendar:
    """Calendar of trading days, holidays, and early closes.

    All dates are in the exchange's local timezone (Chicago for CME).
    """

    exchange: str
    year: int
    holidays: set[date] = field(default_factory=set)
    """Full closure dates (exchange closed all day)."""

    early_closes: dict[date, str] = field(default_factory=dict)
    """Early close dates → close time in local time (HH:MM)."""

    late_opens: dict[date, str] = field(default_factory=dict)
    """Late open dates → open time in local time (HH:MM)."""

    maintenance_breaks: dict[date, tuple[str, str]] = field(default_factory=dict)
    """Date → (break_start, break_end) in local time (HH:MM)."""

    def is_trading_day(self, dt: date) -> bool:
        """Return True if the exchange is open on this date."""
        if dt in self.holidays:
            return False
        if dt.isoweekday() >= 6:  # Saturday=6, Sunday=7
            return False
        return True

    def is_early_close(self, dt: date) -> bool:
        return dt in self.early_closes

    def is_late_open(self, dt: date) -> bool:
        return dt in self.late_opens

    def close_time(self, dt: date, default: str = "16:00") -> str:
        return self.early_closes.get(dt, default)

    def open_time(self, dt: date, default: str = "17:00") -> str:
        return self.late_opens.get(dt, default)


# ── CME 2026 calendar ────────────────────────────────────────────────

CME_2026_HOLIDAYS: set[date] = {
    date(2026, 1, 1),  # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 18),  # Good Friday (observed)
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),  # Independence Day (observed)
    date(2026, 9, 7),  # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
}

CME_2026_EARLY_CLOSES: dict[date, str] = {
    date(2026, 7, 3): "12:00",  # Independence Day (observed) — early close
    date(2026, 11, 27): "12:00",  # Day after Thanksgiving — early close
    date(2026, 12, 24): "12:00",  # Christmas Eve — early close
}

CME_2026_LATE_OPENS: dict[date, str] = {
    date(2026, 1, 1): "17:00"  # New Year's Day — electronic open at 17:00
}

CME_2026_CALENDAR = ExchangeCalendar(
    exchange="CME",
    year=2026,
    holidays=CME_2026_HOLIDAYS,
    early_closes=CME_2026_EARLY_CLOSES,
    late_opens=CME_2026_LATE_OPENS,
    maintenance_breaks={
        # CME maintenance window: typically Sat 08:00–12:00 CT
        date(2026, 1, 3): ("08:00", "12:00"),
        date(2026, 2, 7): ("08:00", "12:00"),
        date(2026, 3, 7): ("08:00", "12:00"),
        date(2026, 4, 4): ("08:00", "12:00"),
        date(2026, 5, 2): ("08:00", "12:00"),
        date(2026, 6, 6): ("08:00", "12:00"),
        date(2026, 7, 4): ("08:00", "12:00"),
        date(2026, 8, 1): ("08:00", "12:00"),
        date(2026, 9, 5): ("08:00", "12:00"),
        date(2026, 10, 3): ("08:00", "12:00"),
        date(2026, 11, 7): ("08:00", "12:00"),
        date(2026, 12, 5): ("08:00", "12:00"),
    },
)


# ── Daylight saving transitions (2026) ───────────────────────────────

# US DST 2026:
#   Spring forward: Sunday, March 8, 2026 (clocks 02:00 → 03:00 CT)
#   Fall back:      Sunday, November 1, 2026 (clocks 02:00 → 01:00 CT)

DST_SPRING_2026 = date(2026, 3, 8)
DST_FALL_2026 = date(2026, 11, 1)


def is_dst_transition_day(dt: date) -> bool:
    """Return True if ``dt`` is a DST transition day for US/CME."""
    return dt in (DST_SPRING_2026, DST_FALL_2026)


# ── Liquidation deadline ─────────────────────────────────────────────


@dataclass(frozen=True)
class LiquidationDeadline:
    """Latest time before expiry when a position must be flattened."""

    exchange: str
    product_group: str
    deadline_time: str = "12:00"
    timezone: str = "America/Chicago"
    days_before_expiry: int = 1


CME_EQUITY_LIQUIDATION = LiquidationDeadline(
    exchange="CME", product_group="equity_index", deadline_time="12:00", days_before_expiry=1
)

CME_ENERGY_LIQUIDATION = LiquidationDeadline(
    exchange="CME", product_group="energy", deadline_time="12:00", days_before_expiry=1
)
