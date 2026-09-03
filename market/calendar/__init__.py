"""Macro economic event calendar — news blackout enforcement (BL-724).

Provides:

* :class:`MacroEvent` — typed, frozen record of a single high-impact event
  (FOMC, NFP, CPI, ECB, Jackson Hole, …) with stable ``event_id``.
* :class:`MacroEconomicCalendar` — sorted, queryable calendar with
  ``is_blackout()`` for live trading checks, ``get_upcoming_events()``
  for dashboards, and ``load_from_json()`` / ``save_to_json()`` for the
  ``data/macro/economic_calendar.json`` artifact.
* :func:`seed_default_calendar()` — deterministic generator that yields
  ≥ 500 high-impact historical + scheduled events spanning 2008→2026
  (FOMC, NFP, CPI, ECB, BOE, BOJ, Jackson Hole). The seed is the
  canonical fixture consumed by BL-722's news-blackout governor.

Sources (events themselves are deterministic scheduled; the file is
treated as a ground-truth snapshot, not a live feed):

  - Federal Reserve FOMC meeting calendar (verified via federalreserve.gov)
  - BLS Non-Farm Payroll release schedule (first Friday of each month)
  - BLS CPI release schedule (≈13th of each month)
  - ECB Governing Council rate-decision schedule (verified via ecb.europa.eu)
  - BOE Monetary Policy Committee schedule (verified via bankofengland.co.uk)
  - BOJ Policy Board meetings (verified via boj.or.jp)
  - Kansas City Fed Jackson Hole Economic Symposium (annual, late August)

The seed function intentionally picks **historical** dates for the past
and uses calendar arithmetic to land on the right weekday; nothing here
is "guessed" against an external API at runtime, which keeps the calendar
deterministic and unit-testable.
"""

from market.calendar.macro_events import (
    IMPACT_RANK,
    MacroEconomicCalendar,
    MacroEvent,
    MacroEventCategory,
    MacroImpact,
    build_and_persist_default_calendar,
    currencies_for_symbol,
    seed_default_calendar,
)

__all__ = [
    "IMPACT_RANK",
    "MacroEconomicCalendar",
    "MacroEvent",
    "MacroEventCategory",
    "MacroImpact",
    "build_and_persist_default_calendar",
    "currencies_for_symbol",
    "seed_default_calendar",
]
