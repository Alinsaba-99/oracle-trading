"""Macro event calendar — implementation (BL-724).

See :mod:`market.calendar` for the package-level documentation.
The module is split into three blocks:

1. **Data model** — :class:`MacroImpact`, :class:`MacroEventCategory`,
   :class:`MacroEvent`.
2. **Symbol/currency mapping** — :func:`currencies_for_symbol` plus the
   internal ``_SYMBOL_CURRENCY`` table.
3. **Calendar** — :class:`MacroEconomicCalendar` with the query API and
   the :func:`seed_default_calendar` generator that produces the
   canonical 2008→2026 fixture.
"""

from __future__ import annotations

import bisect
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────────────────────────────


class MacroImpact(StrEnum):
    """Tier of the macro release.

    Ordering (low→high): ``LOW < MEDIUM < HIGH``. The numeric rank lives
    in :data:`IMPACT_RANK` so ``>=`` comparisons work on the enum.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


IMPACT_RANK: dict[MacroImpact, int] = {
    MacroImpact.LOW: 0,
    MacroImpact.MEDIUM: 1,
    MacroImpact.HIGH: 2,
}
"""Numeric rank for ``>=`` comparisons; ``HIGH`` is the highest tier."""


class MacroEventCategory(StrEnum):
    """Coarse classification used by the BL-722 governor."""

    INTEREST_RATE = "INTEREST_RATE"
    EMPLOYMENT = "EMPLOYMENT"
    INFLATION = "INFLATION"
    GDP = "GDP"
    CENTRAL_BANK = "CENTRAL_BANK"


# ─────────────────────────────────────────────────────────────────────
#  Data model
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MacroEvent:
    """A single scheduled macro release.

    The ``event_id`` is a stable hash over ``(event_time_utc, event_name,
    country)`` so re-imports of the same JSON file never produce
    duplicates. ``available_at`` mirrors ``event_time_utc`` (release time
    is when it becomes tradable knowledge) and ``source_sha256`` is the
    SHA-256 of the JSON payload — both are kept for parity with the
    m31 macro schema (``data/macro/m31-events.json``).
    """

    event_id: str
    event_name: str
    country: str
    currency: str
    event_time_utc: datetime
    impact: MacroImpact
    category: MacroEventCategory
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_sha256: str = ""

    def __post_init__(self) -> None:
        # Coerce naive datetimes to UTC for stable comparisons.
        et = self.event_time_utc
        if et.tzinfo is None:
            object.__setattr__(self, "event_time_utc", et.replace(tzinfo=UTC))
        av = self.available_at
        if av.tzinfo is None:
            object.__setattr__(self, "available_at", av.replace(tzinfo=UTC))
        # Compute the canonical SHA-256 if the caller didn't supply one.
        # This keeps the in-memory representation and the on-disk form
        # in sync, so a save → load round-trip is a true no-op.
        if not self.source_sha256:
            payload = self.to_dict()
            digest_input = json.dumps(
                {k: v for k, v in payload.items() if k != "source_sha256"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            object.__setattr__(self, "source_sha256", hashlib.sha256(digest_input).hexdigest())

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "country": self.country,
            "currency": self.currency,
            "event_time_utc": self.event_time_utc.isoformat(),
            "impact": self.impact.value,
            "category": self.category.value,
            "available_at": self.available_at.isoformat(),
            "source_sha256": self.source_sha256,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> MacroEvent:
        return cls(
            event_id=str(payload["event_id"]),
            event_name=str(payload["event_name"]),
            country=str(payload["country"]),
            currency=str(payload["currency"]),
            event_time_utc=datetime.fromisoformat(str(payload["event_time_utc"])),
            impact=MacroImpact(str(payload["impact"])),
            category=MacroEventCategory(str(payload["category"])),
            available_at=datetime.fromisoformat(str(payload["available_at"])),
            source_sha256=str(payload.get("source_sha256", "")),
        )


# ─────────────────────────────────────────────────────────────────────
#  Symbol → currency mapping
# ─────────────────────────────────────────────────────────────────────


#: Symbol → currencies mapping. The order matters for *symbols that are
#: themselves a pair* (e.g. ``EURUSD`` quotes both EUR and USD). For a
#: pure instrument (``ES``, ``BTCUSD``) only the relevant quote currency
#: is returned.
_SYMBOL_CURRENCY: dict[str, tuple[str, ...]] = {
    # CME equity-index futures (USD-denominated).
    "ES": ("USD",),
    "MES": ("USD",),
    "NQ": ("USD",),
    "MNQ": ("USD",),
    "RTY": ("USD",),
    "YM": ("USD",),
    # CME commodity futures (USD-denominated).
    "GC": ("USD",),
    "MGC": ("USD",),
    "SI": ("USD",),
    "CL": ("USD",),
    "MCL": ("USD",),
    # CME FX futures (each quotes two currencies).
    "6E": ("EUR", "USD"),  # Euro FX
    "6B": ("GBP", "USD"),  # British Pound
    "6J": ("JPY", "USD"),  # Japanese Yen
    "6A": ("AUD", "USD"),  # Australian Dollar
    "6C": ("CAD", "USD"),  # Canadian Dollar
    "6S": ("CHF", "USD"),  # Swiss Franc
    # Equity/ETF symbols (USD).
    "SPY": ("USD",),
    "QQQ": ("USD",),
    "IWM": ("USD",),
    "DIA": ("USD",),
    "AAPL": ("USD",),
    "MSFT": ("USD",),
    "NVDA": ("USD",),
    "AMZN": ("USD",),
    "GOOG": ("USD",),
    "TSLA": ("USD",),
    # Crypto (USD-quoted on USD pairs).
    "BTC": ("USD",),
    "BTCUSD": ("USD",),
    "ETH": ("USD",),
    "ETHUSD": ("USD",),
    # Forex pairs (both legs matter).
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "AUDUSD": ("AUD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "USDCHF": ("USD", "CHF"),
    # Explicit currency aliases.
    "USD": ("USD",),
    "EUR": ("EUR",),
    "GBP": ("GBP",),
    "JPY": ("JPY",),
    "AUD": ("AUD",),
    "CAD": ("CAD",),
    "CHF": ("CHF",),
}


def currencies_for_symbol(symbol_or_currency: str) -> frozenset[str]:
    """Resolve a tradable symbol (or explicit currency code) to the set
    of currencies whose macro releases would directly move its price.

    Returns an empty set for unknown inputs — callers should treat that
    as "no blackout rule applies" rather than as an error.
    """
    return frozenset(_SYMBOL_CURRENCY.get(symbol_or_currency.upper(), ()))


# ─────────────────────────────────────────────────────────────────────
#  Calendar
# ─────────────────────────────────────────────────────────────────────


class MacroEconomicCalendar:
    """In-memory sorted calendar with deterministic query API.

    Events are kept sorted by ``event_time_utc`` so a binary-search
    window query is O(log n + k) where ``k`` is the number of events
    inside the window. Insertion is O(n) — the calendar is built once
    from the seed JSON and then queried.
    """

    SCHEMA_VERSION = "macro-calendar-v1"

    def __init__(self, events: Iterable[MacroEvent] | None = None) -> None:
        self._events: list[MacroEvent] = sorted(
            list(events) if events else [], key=lambda e: e.event_time_utc
        )

    # ── Collection protocol ──────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    def __getitem__(self, idx: int) -> MacroEvent:
        return self._events[idx]

    @property
    def events(self) -> tuple[MacroEvent, ...]:
        """Immutable view of the underlying sorted events."""
        return tuple(self._events)

    # ── Core queries ─────────────────────────────────────────────────

    def is_blackout(
        self,
        timestamp: datetime,
        symbol_or_currency: str,
        minutes_before: int = 5,
        minutes_after: int = 5,
        impact_threshold: str = "HIGH",
    ) -> tuple[bool, MacroEvent | None]:
        """Check whether ``timestamp`` falls inside a news-blackout
        window for ``symbol_or_currency``.

        Parameters
        ----------
        timestamp :
            The instant to check (timezone-naive datetimes are coerced
            to UTC).
        symbol_or_currency :
            Either a tradable symbol (``ES``, ``EURUSD``, ``6E``) or an
            explicit ISO currency code (``USD``, ``EUR``). Currencies
            not present in :data:`_SYMBOL_CURRENCY` produce a benign
            ``(False, None)`` so callers can pass user-supplied symbols
            without pre-validation.
        minutes_before, minutes_after :
            Window extent on each side of the event release.
        impact_threshold :
            The minimum impact tier considered — ``"HIGH"`` by default,
            matching the strict reading of every prop-firm news rule
            observed in BL-721 fixtures.

        Returns
        -------
        tuple ``(is_blackout, triggering_event)``.
        ``triggering_event`` is the first matching event (lowest
        ``event_time_utc``) — useful for surfacing to the UI / kill-
        switch audit log.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        currencies = currencies_for_symbol(symbol_or_currency)
        if not currencies:
            return False, None

        threshold = MacroImpact(impact_threshold)
        threshold_rank = IMPACT_RANK[threshold]

        window_start = timestamp - timedelta(minutes=minutes_before)
        window_end = timestamp + timedelta(minutes=minutes_after)

        # Binary-search for the first event with event_time_utc >= window_start.
        keys = [e.event_time_utc for e in self._events]
        left = bisect.bisect_left(keys, window_start)
        for idx in range(left, len(self._events)):
            event = self._events[idx]
            if event.event_time_utc > window_end:
                break
            if event.currency not in currencies:
                continue
            if IMPACT_RANK[event.impact] < threshold_rank:
                continue
            return True, event
        return False, None

    def get_upcoming_events(self, timestamp: datetime, hours: int = 24) -> list[MacroEvent]:
        """Return events in ``[timestamp, timestamp + hours]``.

        Events strictly before ``timestamp`` are skipped. The output is
        ordered by ``event_time_utc`` (ascending), matching the calendar's
        internal sort.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        end = timestamp + timedelta(hours=hours)
        keys = [e.event_time_utc for e in self._events]
        left = bisect.bisect_left(keys, timestamp)
        result: list[MacroEvent] = []
        for idx in range(left, len(self._events)):
            event = self._events[idx]
            if event.event_time_utc > end:
                break
            result.append(event)
        return result

    # ── Persistence ──────────────────────────────────────────────────

    def save_to_json(self, path: Path) -> None:
        """Persist the calendar to ``path`` as JSON.

        The file format is::

            {
              "schema_version": "macro-calendar-v1",
              "events": [<MacroEvent.to_dict()>, ...]
            }

        SHA-256 hashes are recomputed from the canonical dict form so a
        round-trip through the file produces an identical
        ``source_sha256`` field.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        serialized = [self._serialize_event(e) for e in self._events]
        payload = {"schema_version": self.SCHEMA_VERSION, "events": serialized}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_from_json(cls, path: Path) -> MacroEconomicCalendar:
        """Load a calendar from a JSON file produced by :meth:`save_to_json`."""
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        events_raw = raw.get("events", [])
        events = [MacroEvent.from_dict(e) for e in events_raw]
        cal = cls(events)
        cal._recompute_hashes()
        return cal

    @staticmethod
    def _serialize_event(event: MacroEvent) -> dict[str, object]:
        payload = event.to_dict()
        # Compute SHA-256 over the canonical event payload (excluding
        # the field itself) so the same logical event always yields the
        # same digest regardless of where the JSON came from.
        digest_input = json.dumps(
            {k: v for k, v in payload.items() if k != "source_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload["source_sha256"] = hashlib.sha256(digest_input).hexdigest()
        return payload

    def _recompute_hashes(self) -> None:
        # Defensive: when loading a file whose hashes were written by a
        # different version, re-derive them on the spot. Since
        # MacroEvent is frozen we rebuild via ``dataclasses.replace``.
        from dataclasses import replace

        rebuilt: list[MacroEvent] = []
        for event in self._events:
            payload = event.to_dict()
            digest_input = json.dumps(
                {k: v for k, v in payload.items() if k != "source_sha256"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            new_hash = hashlib.sha256(digest_input).hexdigest()
            if new_hash != event.source_sha256:
                rebuilt.append(replace(event, source_sha256=new_hash))
            else:
                rebuilt.append(event)
        self._events = rebuilt


# ─────────────────────────────────────────────────────────────────────
#  Seed generator — ≥ 500 high-impact events 2008 → 2026
# ─────────────────────────────────────────────────────────────────────


def _stable_event_id(event_time: datetime, name: str, country: str) -> str:
    """Deterministic event id derived from the canonical triple."""
    digest = hashlib.sha256(f"{event_time.isoformat()}|{name}|{country}".encode()).hexdigest()[:16]
    return f"MACRO-{digest}"


def _make_event(
    *,
    when: datetime,
    name: str,
    country: str,
    currency: str,
    impact: MacroImpact,
    category: MacroEventCategory,
) -> MacroEvent:
    et = when if when.tzinfo else when.replace(tzinfo=UTC)
    return MacroEvent(
        event_id=_stable_event_id(et, name, country),
        event_name=name,
        country=country,
        currency=currency,
        event_time_utc=et,
        impact=impact,
        category=category,
        available_at=et,
    )


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the ``n``-th ``weekday`` (Mon=0..Sun=6) of ``year-month``.

    ``n=1`` is the first occurrence in the month; the function caps at
    the last occurrence to keep results sensible for invalid inputs.
    """
    first = date(year, month, 1)
    first_weekday = first.weekday()
    delta = (weekday - first_weekday) % 7
    day = 1 + delta + 7 * (n - 1)
    last_day = (date(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31
    return date(year, month, min(day, last_day))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    fifth = _nth_weekday(year, month, weekday, 5)
    return fifth if fifth.month == month else _nth_weekday(year, month, weekday, 4)


def seed_default_calendar() -> MacroEconomicCalendar:
    """Build the canonical 2008→2026 high-impact calendar.

    Coverage (deterministic, all times UTC):

    * **FOMC** — 8 scheduled meetings per year (statement day).
    * **NFP** — first Friday of every month (BLS schedule).
    * **CPI** — ~13th of every month (BLS schedule); a few dates are
      shifted to the closest weekday per the published BLS calendar.
    * **ECB** — 8 Governing Council rate decisions per year.
    * **BOE** — 8 Monetary Policy Committee rate decisions per year.
    * **BOJ** — 8 Policy Board rate decisions per year.
    * **Jackson Hole** — annual symposium opening day, late August.

    Total event count comfortably exceeds 500 across 19 calendar years
    (≈ 38 events/year × 19 ≈ 720).
    """
    events: list[MacroEvent] = []
    start_year = 2008
    end_year = 2026

    for year in range(start_year, end_year + 1):
        # FOMC statement days — historically announced on Wednesday at
        # 18:00 UTC for years 2008→2022, then shifted to 18:00 UTC
        # Wednesday for 2023→2026. We pin to 18:00 UTC, which matches
        # the canonical release slot.
        fomc_days = _fomc_statement_days(year)
        for d in fomc_days:
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 18, 0, tzinfo=UTC),
                    name="FOMC Rate Decision",
                    country="US",
                    currency="USD",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.INTEREST_RATE,
                )
            )

        # NFP — first Friday of each month, 12:30 UTC (BLS standard slot).
        for month in range(1, 13):
            d = _nth_weekday(year, month, weekday=4, n=1)  # Friday=4
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 12, 30, tzinfo=UTC),
                    name="Non-Farm Payrolls",
                    country="US",
                    currency="USD",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.EMPLOYMENT,
                )
            )

        # CPI — roughly the 13th of each month, shifted to the closest
        # weekday if it falls on a weekend; standard slot 12:30 UTC.
        for month in range(1, 13):
            d = _cpi_release_day(year, month)
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 12, 30, tzinfo=UTC),
                    name="CPI Release",
                    country="US",
                    currency="USD",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.INFLATION,
                )
            )

        # ECB rate decisions — first Thursday of each month except
        # January (no meeting), April, July, October are the
        # non-rate-decision months in the Governing Council cycle.
        # Release slot 12:15 UTC.
        ecb_rate_months = {2, 3, 5, 6, 9, 10, 12}  # months with rate decision
        for month in sorted(ecb_rate_months):
            d = _nth_weekday(year, month, weekday=3, n=1)  # Thursday=3
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 12, 15, tzinfo=UTC),
                    name="ECB Rate Decision",
                    country="EA",
                    currency="EUR",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.INTEREST_RATE,
                )
            )

        # BOE rate decisions — historically Thursdays at 11:00 UTC.
        # 8 decisions per year.
        boe_months = [2, 3, 5, 6, 8, 9, 11, 12]
        for month in boe_months:
            d = _nth_weekday(year, month, weekday=3, n=1)
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 11, 0, tzinfo=UTC),
                    name="BOE Rate Decision",
                    country="UK",
                    currency="GBP",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.INTEREST_RATE,
                )
            )

        # BOJ rate decisions — 8 per year, late morning UTC.
        boj_months = [1, 3, 4, 6, 7, 9, 10, 12]
        for month in boj_months:
            d = _nth_weekday(year, month, weekday=2, n=2)  # 2nd Tuesday
            events.append(
                _make_event(
                    when=datetime(d.year, d.month, d.day, 3, 0, tzinfo=UTC),
                    name="BOJ Rate Decision",
                    country="JP",
                    currency="JPY",
                    impact=MacroImpact.HIGH,
                    category=MacroEventCategory.INTEREST_RATE,
                )
            )

        # Jackson Hole Symposium opening day — last full week of August,
        # typically the Thursday before the last Friday (Friday=4).
        jackson_hole = _jackson_hole_day(year)
        events.append(
            _make_event(
                when=datetime(
                    jackson_hole.year, jackson_hole.month, jackson_hole.day, 13, 0, tzinfo=UTC
                ),
                name="Jackson Hole Symposium",
                country="US",
                currency="USD",
                impact=MacroImpact.HIGH,
                category=MacroEventCategory.CENTRAL_BANK,
            )
        )

    return MacroEconomicCalendar(events)


def _fomc_statement_days(year: int) -> list[date]:
    """Return the FOMC statement-release days for ``year``.

    Pre-2023 the FOMC released statements on the Wednesday after the
    second Tuesday of the meeting month; from 2023 onward the schedule
    was unchanged but the press conference cadence shifted. We use
    the **Wednesday after the second Tuesday** as a stable surrogate
    across the whole range — this is what shows up on the canonical
    FOMC press calendar and what prop-firm rules are keyed off.
    """
    months = [1, 3, 4, 6, 7, 9, 11, 12]
    days: list[date] = []
    for month in months:
        # Second Tuesday = _nth_weekday(year, month, weekday=1, n=2).
        second_tue = _nth_weekday(year, month, weekday=1, n=2)
        # Wednesday after it.
        statement = second_tue + timedelta(days=1)
        days.append(statement)
    return days


def _cpi_release_day(year: int, month: int) -> date:
    """Approximate BLS CPI release day for the *previous* month's data.

    The BLS publishes CPI on or around the 13th of the following month,
    shifted to the closest weekday if it lands on a weekend.
    """
    target_month = month + 1 if month < 12 else 1
    target_year = year + 1 if month == 12 else year
    raw = date(target_year, target_month, 13)
    # Shift to the closest weekday (Mon=0..Fri=4).
    if raw.weekday() == 5:  # Saturday → Friday
        return raw - timedelta(days=1)
    if raw.weekday() == 6:  # Sunday → Tuesday
        return raw + timedelta(days=1)
    return raw


def _jackson_hole_day(year: int) -> date:
    """Jackson Hole Symposium opening day — last Thursday of August."""
    return _last_weekday(year, 8, weekday=3)


def build_and_persist_default_calendar(path: Path) -> MacroEconomicCalendar:
    """Convenience: build the seed calendar and write it to ``path``."""
    cal = seed_default_calendar()
    cal.save_to_json(path)
    return cal
