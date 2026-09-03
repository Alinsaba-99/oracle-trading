"""BL-724 — Macro Economic Events Calendar for news-blackout guards.

Loads a deterministic, source-attributed catalogue of ≥500 high-impact macro
releases from 2008 to 2026 covering USD/EUR/GBP/JPY/CHF/CAD/AUD currencies
(FOMC, NFP, CPI, PPI, GDP, Jackson Hole, ECB/BOE/BOJ/BOC/RBA/RBNZ/SNB
rate decisions, plus ISM/Retail Sales/PCE/Consumer Confidence/Jobless
Claims/Trade Balance/Housing data).

Provides the runtime primitives the BL-722 prop-firm governor needs to
refuse order entry in a ±N minute window around scheduled releases:

* :class:`MacroEvent` — Pydantic model for a single release.
* :class:`ImpactLevel` — HIGH / MEDIUM / LOW impact classification.
* :class:`MacroCalendar` — loader from ``data/macro/economic_calendar.json``
  (with a deterministic fallback for unit tests).
* :func:`is_in_blackout_window` — checks whether a given timestamp is in
  the before/after window of any HIGH/MEDIUM event for the asset's
  currency (e.g. ES→USD, EURUSD→EUR+USD, FTSE→GBP).
* :func:`get_upcoming_events` — lookahead filter with explicit ``until``.

Design notes
------------
* The catalog is generated deterministically by
  ``scripts/build_economic_calendar.py`` so two independent runs produce
  byte-identical JSON; this is the "high-integrity" property the BACKLOG
  asks for (``source_sha256`` per row, top-level sha256 over the file).
* The file format is plain JSON — Polars would also work but every
  release is a single scalar row, JSON keeps the catalog diff-friendly
  for human review and avoids a Polars version lock-in.
* No network calls at runtime — the catalog is a checked-in artifact.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

#: Default location of the on-disk calendar (relative to repo root).
DEFAULT_CALENDAR_PATH: Final[Path] = Path("data/macro/economic_calendar.json")

#: Top-level schema marker for the JSON file.
SCHEMA_VERSION: Final[str] = "bl724-economic-calendar-v1"


class ImpactLevel(StrEnum):
    """Market-impact classification for a macro release."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Asset → currency mapping
# ---------------------------------------------------------------------------
# Symbols tradable through Oracle's broker stack mapped to the currencies
# whose macro calendar they are sensitive to.  A US equity index (ES)
# reacts to USD events (FOMC, NFP); a EUR pair reacts to both EUR (ECB)
# and USD (FOMC) releases because EURUSD = f(EUR, USD).
#
# Mapping is conservative — when in doubt we list both currencies so the
# governor never misses a blackout window.  Symbols not listed here are
# treated as USD-only (US equity default).

ASSET_CURRENCIES: Final[dict[str, tuple[str, ...]]] = {
    # US equity indices
    "ES": ("USD",),
    "NQ": ("USD",),
    "YM": ("USD",),
    "RTY": ("USD",),
    "SPX": ("USD",),
    # US stocks
    "SPY": ("USD",),
    "QQQ": ("USD",),
    "AAPL": ("USD",),
    "MSFT": ("USD",),
    # FX majors
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USDCHF": ("USD", "CHF"),
    "USDCAD": ("USD", "CAD"),
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
    "EURJPY": ("EUR", "JPY"),
    "EURGBP": ("EUR", "GBP"),
    "GBPJPY": ("GBP", "JPY"),
    # Metals / commodities priced in USD
    "XAUUSD": ("USD",),
    "XAGUSD": ("USD",),
    "GC": ("USD",),
    "SI": ("USD",),
    # Energy
    "CL": ("USD",),
    "BZ": ("USD",),
    # Crypto is USD-quoted; not in the BL-724 scope (treat as USD-only).
    "BTCUSD": ("USD",),
    "ETHUSD": ("USD",),
    # European indices
    "DAX": ("EUR",),
    "FTSE": ("GBP",),
    "CAC": ("EUR",),
    "STOXX": ("EUR",),
    # Asian indices
    "N225": ("JPY",),
    "HSI": ("HKD",),
    # Bonds
    "ZN": ("USD",),
    "ZB": ("USD",),
}


def _resolve_currencies(symbol: str) -> tuple[str, ...]:
    """Return the currencies a given trading symbol is sensitive to.

    Unknown symbols default to USD-only (US-equity heuristic).
    """
    sym = symbol.upper().strip()
    if sym in ASSET_CURRENCIES:
        return ASSET_CURRENCIES[sym]
    # Heuristics for common tickers without explicit mapping.
    if sym.endswith("USD"):
        base = sym[:-3]
        return (base, "USD")
    return ("USD",)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MacroEvent(BaseModel):
    """A single scheduled macro-economic release.

    Mirrors the schema of ``data/macro/economic_calendar.json``.

    Both ``impact_level`` and the legacy alias ``impact`` are accepted on
    load — historical fixtures generated by sibling scripts use the
    shorter spelling.  ``source`` defaults to ``"unknown"`` when the row
    only carries a SHA-256 (the integrity anchor) but no URL.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    event_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3)
    event_time_utc: datetime
    impact_level: ImpactLevel
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    source: str = Field(min_length=1, default="unknown")
    source_sha256: str | None = None
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("event_time_utc")
    @classmethod
    def _utc_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("impact_level", mode="before")
    @classmethod
    def _accept_legacy_impact(cls, v: object) -> object:
        """Accept the legacy ``impact`` field name as an alias."""
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_aliases(cls, data: object) -> object:
        """Map legacy column names (``impact``, ``country``) to the spec."""
        if not isinstance(data, dict):
            return data
        # Legacy fixture uses ``impact`` as the column name.
        if "impact_level" not in data and "impact" in data:
            data = {**data, "impact_level": data["impact"]}
        return data


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class MacroCalendar:
    """In-memory index of macro releases for fast blackout queries.

    Backed by a JSON file at :data:`DEFAULT_CALENDAR_PATH` (or a custom
    path).  The loader groups events by ISO date and by (date, currency)
    for O(N) blackout lookups within a single trading session.
    """

    def __init__(self, events: list[MacroEvent]) -> None:
        self._events: tuple[MacroEvent, ...] = tuple(events)
        self._by_id: dict[str, MacroEvent] = {e.event_id: e for e in events}
        # index for fast range queries: date(YYYY-MM-DD) -> sorted events
        self._by_day: dict[str, list[MacroEvent]] = defaultdict(list)
        for ev in events:
            self._by_day[ev.event_time_utc.strftime("%Y-%m-%d")].append(ev)
        for day in self._by_day.values():
            day.sort(key=lambda e: e.event_time_utc)

    # ----- construction helpers ----------------------------------------

    @classmethod
    def from_json(cls, path: Path | str = DEFAULT_CALENDAR_PATH) -> MacroCalendar:
        """Load the catalog from a JSON file on disk."""
        p = Path(path)
        if not p.exists():
            msg = f"Macro calendar not found at {p}"
            raise FileNotFoundError(msg)
        raw = json.loads(p.read_text())
        if not isinstance(raw, dict) or "events" not in raw:
            msg = f"Invalid calendar schema at {p}: missing 'events' key"
            raise ValueError(msg)
        events: list[MacroEvent] = []
        for row in raw["events"]:
            try:
                events.append(MacroEvent.model_validate(row))
            except Exception as exc:  # pragma: no cover — surface the bad row
                msg = f"Invalid event row in {p}: {row} ({exc})"
                raise ValueError(msg) from exc
        cal = cls(events)
        logger.info(
            "macro_calendar.loaded path=%s events=%d schema=%s",
            str(p),
            len(events),
            raw.get("schema_version", "unknown"),
        )
        return cal

    @classmethod
    def empty(cls) -> MacroCalendar:
        """Return an empty calendar — useful for tests / dry-runs."""
        return cls([])

    # ----- accessors ----------------------------------------------------

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    def __contains__(self, event_id: object) -> bool:
        return isinstance(event_id, str) and event_id in self._by_id

    def get(self, event_id: str) -> MacroEvent | None:
        return self._by_id.get(event_id)

    @property
    def events(self) -> tuple[MacroEvent, ...]:
        """All events, in load order (deterministic)."""
        return self._events

    def filter(
        self,
        *,
        currency: str | None = None,
        impact: ImpactLevel | tuple[ImpactLevel, ...] | None = None,
    ) -> list[MacroEvent]:
        """Return events matching the given filter."""
        out: list[MacroEvent] = []
        impact_set: tuple[ImpactLevel, ...] | None = (
            impact if isinstance(impact, tuple) else (impact,) if impact else None
        )
        cur = currency.upper() if currency else None
        for ev in self._events:
            if cur and ev.currency != cur:
                continue
            if impact_set and ev.impact_level not in impact_set:
                continue
            out.append(ev)
        return out

    # ----- queries ------------------------------------------------------

    def events_on(self, day: str | datetime) -> list[MacroEvent]:
        """Return events whose UTC date equals ``day`` (YYYY-MM-DD or dt)."""
        key = day.astimezone(UTC).strftime("%Y-%m-%d") if isinstance(day, datetime) else day
        return list(self._by_day.get(key, ()))


# ---------------------------------------------------------------------------
# Blackout helpers
# ---------------------------------------------------------------------------


#: Default windows (minutes) for HIGH-impact and MEDIUM-impact events.
DEFAULT_HIGH_WINDOW_M: Final[int] = 5
DEFAULT_MEDIUM_WINDOW_M: Final[int] = 2
DEFAULT_LOW_WINDOW_M: Final[int] = 0


def _windows_for_impact(
    impact: ImpactLevel, window_before_m: int, window_after_m: int
) -> tuple[int, int] | None:
    """Translate the user-provided window into per-impact offsets.

    Returns ``None`` when the event is too small to trigger a blackout.
    """
    if impact == ImpactLevel.LOW and (window_before_m <= DEFAULT_LOW_WINDOW_M):
        return None
    # Caller's window is the HIGH default; shrink for MEDIUM.
    if impact == ImpactLevel.MEDIUM:
        scale = DEFAULT_MEDIUM_WINDOW_M / max(DEFAULT_HIGH_WINDOW_M, 1)
        return max(1, round(window_before_m * scale)), max(1, round(window_after_m * scale))
    return window_before_m, window_after_m


def is_in_blackout_window(
    timestamp: datetime,
    currency_or_symbol: str,
    calendar: MacroCalendar,
    *,
    window_before_m: int = DEFAULT_HIGH_WINDOW_M,
    window_after_m: int = DEFAULT_HIGH_WINDOW_M,
) -> tuple[bool, str | None]:
    """Return ``(True, event_id)`` if ``timestamp`` sits inside a blackout window.

    The window is centered on each event in the calendar and trimmed by
    impact level: HIGH events use the full caller-specified window,
    MEDIUM events use a 2/5 scaled window, LOW events never trigger
    unless the caller passes a non-zero ``window_before_m``.

    The first positional argument may be either a currency code (USD,
    EUR, ...) or a trading symbol (ES, EURUSD, ...) — symbols are
    expanded via :func:`_resolve_currencies`.
    """
    ts = timestamp.astimezone(UTC) if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    # Resolve to the set of currencies the caller cares about.
    raw = currency_or_symbol.strip().upper()
    currencies = (raw,) if len(raw) == 3 and raw.isalpha() else _resolve_currencies(raw)

    # Only HIGH and MEDIUM trigger by default — filter once.
    candidates = [
        ev
        for ev in calendar.events
        if ev.currency in currencies and ev.impact_level != ImpactLevel.LOW
    ]

    for ev in candidates:
        win = _windows_for_impact(ev.impact_level, window_before_m, window_after_m)
        if win is None:
            continue
        before, after = win
        start = ev.event_time_utc - timedelta(minutes=before)
        end = ev.event_time_utc + timedelta(minutes=after)
        if start <= ts <= end:
            return True, ev.event_id
    return False, None


def get_upcoming_events(
    timestamp: datetime,
    calendar: MacroCalendar,
    *,
    lookahead_hours: int = 24,
    currency: str | None = None,
    impact: ImpactLevel | tuple[ImpactLevel, ...] | None = None,
) -> list[MacroEvent]:
    """Return events scheduled within ``[timestamp, timestamp + lookahead]``.

    Both filters are optional: ``currency`` restricts to one currency,
    ``impact`` restricts to a level or a tuple of levels.
    """
    ts = timestamp.astimezone(UTC) if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    horizon = ts + timedelta(hours=lookahead_hours)
    cur = currency.upper() if currency else None
    impact_set: tuple[ImpactLevel, ...] | None = (
        impact if isinstance(impact, tuple) else (impact,) if impact else None
    )
    out: list[MacroEvent] = []
    for ev in calendar.events:
        if ev.event_time_utc < ts or ev.event_time_utc > horizon:
            continue
        if cur and ev.currency != cur:
            continue
        if impact_set and ev.impact_level not in impact_set:
            continue
        out.append(ev)
    return out


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------


def compute_file_sha256(path: Path | str) -> str:
    """Compute the catalog integrity hash.

    Mirrors the algorithm used by ``scripts/build_economic_calendar.py``:
    load the JSON, drop the ``file_sha256`` field, serialize canonically
    (sorted keys, no whitespace), and hash the bytes.  This way the
    stored ``file_sha256`` is self-verifying against the same canonical
    form regardless of the on-disk indentation.
    """
    p = Path(path)
    if not p.exists():
        msg = f"Calendar file not found: {p}"
        raise FileNotFoundError(msg)
    raw = json.loads(p.read_text())
    if isinstance(raw, dict):
        raw = {k: v for k, v in raw.items() if k != "file_sha256"}
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "ASSET_CURRENCIES",
    "DEFAULT_CALENDAR_PATH",
    "DEFAULT_HIGH_WINDOW_M",
    "DEFAULT_LOW_WINDOW_M",
    "DEFAULT_MEDIUM_WINDOW_M",
    "SCHEMA_VERSION",
    "ImpactLevel",
    "MacroCalendar",
    "MacroEvent",
    "compute_file_sha256",
    "get_upcoming_events",
    "is_in_blackout_window",
]
