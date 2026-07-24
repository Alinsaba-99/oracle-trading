"""Futures contract roll — continuous-to-tradable mapping and roll logic.

Provides:
- ``continuous_symbol(tradable)`` → continuous root (ESU26 → ES)
- ``tradable_contract(symbol, year, month)`` → ESZ26
- ``next_contract(current)`` → next listed contract
- ``RollCalendar`` with volume-based or calendar-based roll dates
- Expired contract detection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# ── Month code mapping (CME standard) ────────────────────────────────
# F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep,
# V=Oct, X=Nov, Z=Dec

MONTH_CODES: dict[str, int] = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}

MONTH_TO_CODE: dict[int, str] = {v: k for k, v in MONTH_CODES.items()}


def _month_code(month: int) -> str:
    """Return the CME month code for a given month number (1-12)."""
    return MONTH_TO_CODE[month]


def _parse_month_code(code: str) -> int:
    """Return month number (1-12) for a CME month code letter."""
    return MONTH_CODES[code.upper()]


def continuous_symbol(tradable_symbol: str) -> str:
    """Extract the continuous (root) symbol from a tradable contract code.

    Uses the known root symbol catalog to disambiguate month codes from
    root symbols (e.g. ``NQ`` contains ``Q`` which is also a month code).

    Examples::

        continuous_symbol("ESU26")  → "ES"
        continuous_symbol("NQZ25")  → "NQ"
        continuous_symbol("ES")     → "ES"   (already continuous)
    """
    from market.contracts import CATALOG

    # Try known root symbols first (longest match wins)
    for sym_len in (4, 3, 2, 1):
        if len(tradable_symbol) >= sym_len:
            candidate = tradable_symbol[:sym_len]
            if candidate in CATALOG:
                return candidate

    # Fallback: remove trailing month code + year
    if len(tradable_symbol) > 3 and tradable_symbol[-3] in MONTH_CODES:
        return tradable_symbol[:-3]

    return tradable_symbol


def tradable_contract(root_symbol: str, year: int, month: int) -> str:
    """Build a tradable contract symbol.

    Args:
        root_symbol: Continuous root symbol (e.g. ``ES``).
        year: Expiry year (e.g. 2026).
        month: Expiry month (1-12).

    Returns:
        Tradable symbol (e.g. ``ESU26`` for ES Sep 2026).
    """
    code = _month_code(month)
    year_short = str(year)[-2:]
    return f"{root_symbol}{code}{year_short}"


def next_contract(root_symbol: str, listing_months: tuple[int, ...]) -> str:
    """Return the next listed contract after the current month.

    Args:
        root_symbol: Continuous root symbol (e.g. ``ES``).
        listing_months: Tuple of listing months (e.g. ``(3, 6, 9, 12)``).

    Returns:
        Tradable symbol for the next contract month.
    """
    from datetime import datetime

    now = datetime.now()
    current_month = now.month
    current_year = now.year

    # Find the next listing month
    for m in sorted(listing_months):
        if m > current_month:
            return tradable_contract(root_symbol, current_year, m)

    # If no later month this year, use the first month of next year
    next_year = current_year + 1
    first_month = sorted(listing_months)[0]
    return tradable_contract(root_symbol, next_year, first_month)


@dataclass(frozen=True)
class RollSchedule:
    """Defines when to roll from one contract month to the next."""

    root_symbol: str
    """Continuous root symbol."""

    from_month: int
    """Current contract month."""

    to_month: int
    """Next contract month."""

    from_year: int
    """Current contract year."""

    to_year: int
    """Next contract year."""

    roll_date: date
    """Date on which the roll occurs."""

    roll_type: str = "volume"
    """Volume-based or calendar-based roll."""

    @property
    def from_symbol(self) -> str:
        return tradable_contract(self.root_symbol, self.from_year, self.from_month)

    @property
    def to_symbol(self) -> str:
        return tradable_contract(self.root_symbol, self.to_year, self.to_month)


def default_roll_date(listing_months: tuple[int, ...], current_month: int) -> date:
    """Compute a default roll date: 5 trading days before expiry month.

    For quarterly contracts (H/M/U/Z), the roll typically occurs in the
    week leading up to the contract expiry.  We use a simple heuristic:
    roll on the 25th of the month before expiry (or the last weekday
    before that).
    """
    from datetime import datetime

    now = datetime.now()
    current_year = now.year

    # Find the current listing month and the next one
    months = sorted(listing_months)
    next_month = None
    for m in months:
        if m >= current_month:
            next_month = m
            break
    if next_month is None:
        next_month = months[0]

    # Roll date: 8th day of the month before expiry
    if next_month == 1:
        roll_month = 12
        roll_year = current_year - 1
    else:
        roll_month = next_month - 1
        roll_year = current_year

    # Default to the 25th or nearest weekday before
    candidate = date(roll_year, roll_month, 25)
    if candidate.weekday() >= 5:  # Saturday=5, Sunday=6
        candidate -= timedelta(days=candidate.weekday() - 4)
    return candidate
