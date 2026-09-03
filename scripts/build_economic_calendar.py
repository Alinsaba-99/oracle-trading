"""BL-724 — Generate the deterministic macro economic events calendar.

Produces ``data/macro/economic_calendar.json`` containing >=500
high-impact macro releases from 2008 to 2026 across the USD/EUR/GBP/
JPY/CHF/CAD/AUD/NZD/HKD currencies.

The catalog covers:

* FOMC rate decisions (~8 per year, USD)
* NFP / Non-Farm Payrolls (~12 per year, USD)
* CPI / Consumer Price Index (~12 per year, USD)
* PPI / Producer Price Index (~12 per year, USD)
* GDP advance / preliminary / final (~12 per year, USD)
* Jackson Hole symposium (1 per year, USD)
* ISM Manufacturing PMI (~12 per year, USD)
* ISM Services PMI (~12 per year, USD)
* Retail Sales (~12 per year, USD)
* PCE / Core PCE (~12 per year, USD)
* Unemployment Rate (~12 per year, USD)
* Initial Jobless Claims (~52 per year, USD)
* Consumer Confidence (~12 per year, USD)
* ECB rate decisions (~8 per year, EUR)
* BOE rate decisions (~8 per year, GBP)
* BOJ rate decisions (~8 per year, JPY)
* BOC rate decisions (~8 per year, CAD)
* RBA rate decisions (~8 per year, AUD)
* RBNZ rate decisions (~8 per year, NZD)
* SNB rate decisions (~4 per year, CHF)

Total ~= 280/year x 19 years = ~5300 rows; we cap to keep the file
manageable (~1000-1500 rows) and keep determinism by hashing the
schedule to compute per-event stable IDs.

The generator is **deterministic** — two runs produce byte-identical
output.  Each event carries a ``source_sha256`` and the file header
embeds a ``file_sha256`` for the calendar JSON itself.

Usage::

    uv run python scripts/build_economic_calendar.py

The catalog file is checked in — regenerate only when adding new
events or correcting known dates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

OUT_PATH: Final[Path] = Path("data/macro/economic_calendar.json")
SCHEMA_VERSION: Final[str] = "bl724-economic-calendar-v1"

#: Source label embedded into every event — the schedule is publicly known
#: (Federal Reserve press release index, ECB/BOE calendars) and the row
#: SHA-256 below anchors each event to its deterministic date string.
SOURCE_LABEL: Final[str] = "bl724-schedule"

#: Start / end of the catalog (inclusive UTC dates).
START_DATE: Final[datetime] = datetime(2008, 1, 1, tzinfo=UTC)
END_DATE: Final[datetime] = datetime(2026, 12, 31, tzinfo=UTC)


@dataclass(frozen=True)
class EventTemplate:
    """Repeatable schedule description."""

    name: str
    currency: str
    impact: str
    hour_utc: int
    minute_utc: int
    # Repeat interval (days) — None means explicit dates provided externally.
    repeat_days: int | None = None
    # Day-of-month list (1..31) — for "first Friday", "15th of month" etc.
    day_of_month: int | None = None
    # Day-of-week list (0=Mon..6=Sun) — for "first Friday"
    day_of_week: int | None = None
    # Skip every N occurrences (1=keep all)
    every_n_months: int | None = None


#: Schedules for events that occur on a fixed day-of-month.
_FIXED_DAY_TEMPLATES: tuple[tuple[str, EventTemplate], ...] = (
    # First Friday of month: NFP (USD)
    (
        "NFP",
        EventTemplate(
            name="Non-Farm Payrolls",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=1,
            day_of_week=4,  # Friday
        ),
    ),
    # ~13th of each month: CPI release
    (
        "CPI",
        EventTemplate(
            name="CPI m/m",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=13,
        ),
    ),
    # ~15th of each month: PPI
    (
        "PPI",
        EventTemplate(
            name="PPI m/m",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=15,
        ),
    ),
    # Last week of month (Thu): GDP advance
    (
        "GDP_ADV",
        EventTemplate(
            name="GDP Advance q/q",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=28,
            day_of_week=3,  # Thursday
        ),
    ),
    # First business day of month: ISM Manufacturing PMI
    (
        "ISM_MFG",
        EventTemplate(
            name="ISM Manufacturing PMI",
            currency="USD",
            impact="HIGH",
            hour_utc=14,
            minute_utc=0,
            day_of_month=1,
            day_of_week=4,  # first Friday
        ),
    ),
    # Third business day of month: ISM Services PMI
    (
        "ISM_SVC",
        EventTemplate(
            name="ISM Services PMI",
            currency="USD",
            impact="HIGH",
            hour_utc=14,
            minute_utc=0,
            day_of_month=3,
            day_of_week=4,
        ),
    ),
    # Mid-month: Retail Sales
    (
        "RETAIL",
        EventTemplate(
            name="Retail Sales m/m",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=16,
        ),
    ),
    # Last week of month: Consumer Confidence
    (
        "CONF",
        EventTemplate(
            name="CB Consumer Confidence",
            currency="USD",
            impact="MEDIUM",
            hour_utc=14,
            minute_utc=0,
            day_of_month=25,
        ),
    ),
    # Last Friday of month: PCE inflation
    (
        "PCE",
        EventTemplate(
            name="Core PCE m/m",
            currency="USD",
            impact="HIGH",
            hour_utc=12,
            minute_utc=30,
            day_of_month=28,
            day_of_week=4,  # last Friday-ish; day_of_month handles 4-Friday
        ),
    ),
)


#: Explicit-date events (rate decisions + Jackson Hole + recurring monthly jobs).
#: Each row is (event_name, currency, impact, ISO date, hour_utc, minute_utc).
#: These dates are sourced from publicly published central-bank schedules.
EXPLICIT_DATES: tuple[tuple[str, str, str, str, int, int], ...] = (
    # ---------------------------------------------------------------- FOMC
    # 2008: 8 unscheduled emergency cuts + Jan/Mar/May/Jun/Aug/Sep/Oct/Dec scheduled
    ("FOMC Rate Decision", "USD", "HIGH", "2008-01-22", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-01-30", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-03-11", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-03-18", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-04-30", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-06-25", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-08-05", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-09-16", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-09-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-10-08", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-10-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-11-25", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2008-12-16", 18, 15),
    # 2009 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2009-01-28", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-03-18", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-04-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-06-24", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-08-12", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-09-23", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-11-04", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2009-12-16", 19, 15),
    # 2010 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2010-01-27", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-03-16", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-04-28", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-06-23", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-08-10", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-09-21", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-11-03", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2010-12-14", 19, 15),
    # 2011 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2011-01-26", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-03-15", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-04-27", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-06-22", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-08-09", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-09-21", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-11-02", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2011-12-13", 19, 15),
    # 2012 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2012-01-25", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-03-13", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-04-25", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-06-20", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-08-01", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-09-13", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-10-24", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2012-12-12", 19, 15),
    # 2013 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2013-01-30", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-03-20", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-05-01", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-06-19", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-07-31", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-09-18", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-10-30", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2013-12-18", 19, 15),
    # 2014 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2014-01-29", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-03-19", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-04-30", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-06-18", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-07-30", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-09-17", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-10-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2014-12-17", 19, 15),
    # 2015 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2015-01-28", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-03-18", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-04-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-06-17", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-07-29", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-09-17", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-10-28", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2015-12-16", 19, 15),
    # 2016 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2016-01-27", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-03-16", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-04-27", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-06-15", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-07-27", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-09-21", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-11-02", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2016-12-14", 19, 15),
    # 2017 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2017-02-01", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-03-15", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-05-03", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-06-14", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-07-26", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-09-20", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-11-01", 18, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2017-12-13", 19, 15),
    # 2018 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2018-01-31", 19, 15),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-03-21", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-05-02", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-06-13", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-08-01", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-09-26", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-11-08", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2018-12-19", 19, 0),
    # 2019 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2019-01-30", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-03-20", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-05-01", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-06-19", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-07-31", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-09-18", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-10-30", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2019-12-11", 19, 0),
    # 2020 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2020-01-29", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-03-03", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-03-15", 17, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-04-29", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-06-10", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-07-29", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-09-16", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-11-05", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2020-12-16", 19, 0),
    # 2021 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2021-01-27", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-03-17", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-04-28", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-06-16", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-07-28", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-09-22", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-11-03", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2021-12-15", 19, 0),
    # 2022 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2022-01-26", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-03-16", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-05-04", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-06-15", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-07-27", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-09-21", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-11-02", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2022-12-14", 19, 0),
    # 2023 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2023-02-01", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-03-22", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-05-03", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-06-14", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-07-26", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-09-20", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-11-01", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2023-12-13", 19, 0),
    # 2024 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2024-01-31", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-03-20", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-05-01", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-06-12", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-07-31", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-09-18", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-11-07", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2024-12-18", 19, 0),
    # 2025 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2025-01-29", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-03-19", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-05-07", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-06-18", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-07-30", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-09-17", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-10-29", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2025-12-17", 19, 0),
    # 2026 (8)
    ("FOMC Rate Decision", "USD", "HIGH", "2026-01-28", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-03-18", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-04-29", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-06-17", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-07-29", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-09-16", 18, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-11-04", 19, 0),
    ("FOMC Rate Decision", "USD", "HIGH", "2026-12-16", 19, 0),
    # ---------------------------------------------------------------- ECB
    # 2015-onwards (rate cuts through 2016 then QE exit, normal cycle 2017+)
    ("ECB Rate Decision", "EUR", "HIGH", "2015-01-22", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-03-05", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-04-15", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-06-03", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-07-16", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-09-03", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-10-22", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2015-12-03", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-01-21", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-03-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-04-21", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-06-02", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-07-21", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-09-08", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-10-20", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2016-12-08", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-01-19", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-03-09", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-04-27", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-06-08", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-07-20", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-09-07", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-10-26", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2017-12-14", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-01-25", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-03-08", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-04-26", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-06-14", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-07-26", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-09-13", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-10-25", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2018-12-13", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-01-24", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-03-07", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-04-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-06-06", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-07-25", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-09-12", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-10-24", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2019-12-12", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-01-23", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-03-12", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-04-30", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-06-04", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-07-16", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-09-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-10-29", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2020-12-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-01-21", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-03-11", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-04-22", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-06-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-07-22", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-09-09", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-10-28", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2021-12-16", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-01-20", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-03-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-04-14", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-06-09", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-07-21", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-09-08", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-10-27", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2022-12-15", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-02-02", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-03-16", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-05-04", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-06-15", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-07-27", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-09-14", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-10-26", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2023-12-14", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-01-25", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-03-07", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-04-11", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-06-06", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-07-25", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-09-12", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-10-17", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2024-12-12", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-01-30", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-03-06", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-04-17", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-06-05", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-07-24", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-09-11", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-10-30", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2025-12-18", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-01-29", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-03-19", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-04-30", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-06-04", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-07-23", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-09-10", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-10-29", 13, 45),
    ("ECB Rate Decision", "EUR", "HIGH", "2026-12-17", 13, 45),
    # ---------------------------------------------------------------- BOE
    ("BOE Rate Decision", "GBP", "HIGH", "2008-01-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-02-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-03-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-04-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-05-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-06-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-07-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-08-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-09-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-10-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-11-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2008-12-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-01-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-02-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-03-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-04-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-05-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-06-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-07-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-08-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-09-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-10-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-11-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2009-12-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-01-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-02-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-03-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-04-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-05-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-06-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-07-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-08-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-09-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-10-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-11-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2010-12-09", 12, 0),
    # 2011-2026 BOE (8/year)
    ("BOE Rate Decision", "GBP", "HIGH", "2011-01-13", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-02-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-03-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-04-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-05-12", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-06-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-07-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-08-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-09-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-10-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-11-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2011-12-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-01-12", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-02-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-03-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-04-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-05-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-06-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-07-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-08-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-09-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-10-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-11-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2012-12-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-01-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-02-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-03-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-04-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-05-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-06-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-07-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-08-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-09-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-10-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-11-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2013-12-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-01-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-02-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-03-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-04-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-05-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-06-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-07-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-08-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-09-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-10-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-11-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2014-12-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-01-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-02-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-03-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-04-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-05-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-06-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-07-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-08-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-09-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-10-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-11-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2015-12-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-01-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-02-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-03-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-04-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-05-12", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-06-16", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-07-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-08-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-09-15", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-10-13", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-11-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2016-12-15", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-02-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-03-16", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-04-13", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-06-15", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-08-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-09-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-11-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2017-12-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-02-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-03-22", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-05-10", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-06-21", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-08-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-09-13", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-11-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2018-12-20", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-02-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-03-21", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-05-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-06-20", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-08-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-09-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-11-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2019-12-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-01-30", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-03-11", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-03-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-04-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-05-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-06-18", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-08-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-09-17", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-11-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2020-12-17", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-01-21", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-03-18", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-05-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-06-24", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-08-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-09-23", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-11-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2021-12-16", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-02-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-03-17", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-05-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-06-16", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-08-04", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-09-22", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-11-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2022-12-15", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-02-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-03-23", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-05-11", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-06-22", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-08-03", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-09-21", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-11-02", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2023-12-14", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-02-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-03-21", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-05-09", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-06-20", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-08-01", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-09-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-11-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2024-12-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-02-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-03-20", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-05-08", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-06-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-08-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-09-18", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-11-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2025-12-18", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-02-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-03-19", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-05-07", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-06-18", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-08-06", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-09-17", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-11-05", 12, 0),
    ("BOE Rate Decision", "GBP", "HIGH", "2026-12-17", 12, 0),
    # ---------------------------------------------------------------- BOJ
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-01-29", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-03-15", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-06-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-07-29", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-09-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-11-01", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2016-12-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-01-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-03-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-06-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-07-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-09-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-10-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2017-12-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-01-23", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-03-09", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-04-27", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-06-15", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-07-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-09-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-10-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2018-12-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-01-23", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-03-15", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-04-25", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-06-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-07-30", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-09-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-10-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2019-12-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-01-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-03-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-04-27", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-06-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-07-15", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-09-17", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-10-29", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2020-12-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-01-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-03-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-06-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-07-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-09-22", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-10-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2021-12-17", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-01-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-03-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-06-17", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-07-21", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-09-22", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-10-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2022-12-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-01-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-03-10", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-06-16", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-07-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-09-22", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-10-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2023-12-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-01-23", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-03-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-04-26", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-06-14", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-07-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-09-20", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-10-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2024-12-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-01-24", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-03-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-05-01", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-06-17", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-07-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-09-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-10-30", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2025-12-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-01-23", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-03-19", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-04-28", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-06-17", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-07-31", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-09-18", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-10-29", 3, 0),
    ("BOJ Rate Decision", "JPY", "HIGH", "2026-12-18", 3, 0),
    # ---------------------------------------------------------------- BOC
    ("BOC Rate Decision", "CAD", "HIGH", "2018-01-17", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-03-07", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-04-18", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-05-30", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-07-11", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-09-05", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-10-24", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2018-12-05", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-01-09", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-03-06", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-04-24", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-05-29", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-07-10", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-09-04", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-10-23", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2019-12-04", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-01-22", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-03-04", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-03-27", 17, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-04-15", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-06-03", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-07-15", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-09-09", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-10-28", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2020-12-09", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-01-20", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-03-10", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-04-21", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-06-09", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-07-14", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-09-08", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-10-27", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2021-12-08", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-01-26", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-03-02", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-04-13", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-06-01", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-07-13", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-09-07", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-10-26", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2022-12-07", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-01-25", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-03-08", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-04-12", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-06-07", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-07-12", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-09-06", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-10-25", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2023-12-06", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-01-24", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-03-06", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-04-10", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-06-05", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-07-24", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-09-04", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-10-23", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2024-12-11", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-01-29", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-03-12", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-04-16", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-06-04", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-07-30", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-09-03", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-10-22", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2025-12-10", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-01-28", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-03-11", 15, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-04-15", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-06-03", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-07-29", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-09-02", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-10-21", 14, 0),
    ("BOC Rate Decision", "CAD", "HIGH", "2026-12-09", 15, 0),
    # ---------------------------------------------------------------- RBA
    ("RBA Rate Decision", "AUD", "HIGH", "2018-02-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-03-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-04-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-05-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-06-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-07-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-08-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-09-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-10-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-11-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2018-12-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-02-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-03-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-04-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-05-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-06-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-07-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-08-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-09-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-10-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-11-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2019-12-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-02-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-03-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-03-19", 1, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-04-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-05-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-06-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-07-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-08-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-09-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-10-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-11-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2020-12-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-02-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-03-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-04-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-05-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-06-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-07-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-08-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-09-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-10-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-11-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2021-12-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-02-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-03-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-04-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-05-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-06-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-07-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-08-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-09-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-10-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-11-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2022-12-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-02-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-03-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-04-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-05-02", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-06-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-07-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-08-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-09-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-10-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-11-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2023-12-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-02-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-03-19", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-05-07", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-06-18", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-08-06", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-09-24", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-11-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2024-12-10", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-02-18", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-04-01", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-05-20", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-07-08", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-08-26", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-09-30", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-11-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2025-12-09", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-02-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-03-17", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-05-05", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-06-16", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-08-04", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-09-29", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-11-03", 5, 30),
    ("RBA Rate Decision", "AUD", "HIGH", "2026-12-08", 5, 30),
    # ---------------------------------------------------------------- RBNZ
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-02-08", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-03-22", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-05-10", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-06-28", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-08-09", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-09-27", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2018-11-08", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-02-13", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-03-27", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-05-08", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-06-26", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-08-07", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-09-25", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2019-11-13", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-02-12", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-03-16", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-05-13", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-06-24", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-08-12", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-09-23", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2020-11-11", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-02-24", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-04-14", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-05-26", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-07-14", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-08-18", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-10-06", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2021-11-24", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-02-23", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-04-13", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-05-25", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-07-13", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-08-17", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-10-05", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2022-11-23", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-02-22", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-04-05", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-05-24", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-07-12", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-08-16", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-10-04", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2023-11-29", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-02-28", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-04-10", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-05-22", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-08-14", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-10-09", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2024-11-27", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-02-19", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-04-09", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-05-28", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-08-20", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-10-08", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2025-11-26", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-02-18", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-04-08", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-05-27", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-08-19", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-10-07", 1, 0),
    ("RBNZ Rate Decision", "NZD", "HIGH", "2026-11-25", 1, 0),
    # ---------------------------------------------------------------- SNB
    ("SNB Rate Decision", "CHF", "HIGH", "2018-03-15", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2018-06-14", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2018-09-20", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2018-12-13", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2019-03-21", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2019-06-13", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2019-09-19", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2019-12-12", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2020-03-19", 9, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2020-06-18", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2020-09-24", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2020-12-17", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2021-03-25", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2021-06-17", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2021-09-23", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2021-12-16", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2022-03-24", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2022-06-16", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2022-09-22", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2022-12-15", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2023-03-23", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2023-06-22", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2023-09-21", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2023-12-14", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2024-03-21", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2024-06-20", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2024-09-26", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2024-12-12", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2025-03-20", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2025-06-19", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2025-09-25", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2025-12-11", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2026-03-19", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2026-06-18", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2026-09-24", 8, 30),
    ("SNB Rate Decision", "CHF", "HIGH", "2026-12-10", 8, 30),
    # ---------------------------------------------------------------- Jackson Hole
    ("Jackson Hole Symposium", "USD", "MEDIUM", "2008-08-21", 13, 0),
    ("Jackson Hole Symposium", "USD", "MEDIUM", "2009-08-21", 13, 0),
    ("Jackson Hole Symposium", "USD", "MEDIUM", "2010-08-27", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2011-08-26", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2012-08-31", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2013-08-22", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2014-08-21", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2015-08-27", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2016-08-25", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2017-08-24", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2018-08-23", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2019-08-22", 13, 0),
    ("Jackson Hole Symposium", "USD", "MEDIUM", "2020-08-27", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2021-08-26", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2022-08-25", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2023-08-24", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2024-08-22", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2025-08-21", 13, 0),
    ("Jackson Hole Symposium", "USD", "HIGH", "2026-08-27", 13, 0),
)


#: Initial Jobless Claims — every Thursday 12:30 UTC (USD).
JOBLESS_CLAIMS_TEMPLATE = EventTemplate(
    name="Initial Jobless Claims",
    currency="USD",
    impact="MEDIUM",
    hour_utc=12,
    minute_utc=30,
    day_of_week=3,  # Thursday
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_row(row: dict[str, object]) -> str:
    """Stable SHA-256 of the row's canonical content (JSON, sort_keys)."""
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generate_explicit() -> list[dict[str, object]]:
    """Materialize the explicit-date events."""
    rows: list[dict[str, object]] = []
    for name, currency, impact, date_str, hour, minute in EXPLICIT_DATES:
        ts = datetime.fromisoformat(f"{date_str}T{hour:02d}:{minute:02d}:00+00:00")
        if not (START_DATE <= ts <= END_DATE):
            continue
        event_id = f"{currency}-{ts.strftime('%Y%m%dT%H%M')}-{name.split()[0].lower()}"
        row: dict[str, object] = {
            "event_id": event_id,
            "event_name": name,
            "currency": currency,
            "event_time_utc": ts.isoformat(),
            "impact_level": impact,
            "actual": None,
            "forecast": None,
            "previous": None,
            "source": f"{SOURCE_LABEL}:{name}",
        }
        row["source_sha256"] = _hash_row(row)
        rows.append(row)
    return rows


def _first_weekday_in_month(year: int, month: int, target_weekday: int) -> datetime | None:
    """Return the first ``target_weekday`` (0=Mon..6=Sun) of the month."""
    this_first = datetime(year, month, 1, tzinfo=UTC)
    delta = (target_weekday - this_first.weekday()) % 7
    return this_first + timedelta(days=delta)


def _generate_fixed_day_template(key: str, template: EventTemplate) -> list[dict[str, object]]:
    """Generate events for a fixed-day-of-month template."""
    if template.day_of_month is None:
        msg = f"Template {key} missing day_of_month"
        raise ValueError(msg)
    rows: list[dict[str, object]] = []
    for year in range(START_DATE.year, END_DATE.year + 1):
        for month in range(1, 13):
            if template.day_of_week is not None:
                # Anchor on day_of_month, then advance to the requested weekday.
                anchor = datetime(year, month, template.day_of_month, tzinfo=UTC)
                delta = (template.day_of_week - anchor.weekday()) % 7
                # If day_of_month is 1 we want first; if it's later we may move past
                # the requested day_of_month — clamp to the same week if so.
                candidate = anchor + timedelta(days=delta)
                # Heuristic: if anchor.day_of_month <= 7 -> first occurrence;
                # if anchor.day_of_month is mid-month (e.g. 25/28) keep that week.
                if template.day_of_month <= 7 and delta > 6:
                    continue  # invalid first-weekday placement
            else:
                # Clamp day-of-month for short months (e.g., Feb 30 -> Feb 28).
                dom = template.day_of_month
                if month == 2 and dom > 28:
                    dom = 28
                if dom > 30 and month in (4, 6, 9, 11):
                    dom = 30
                candidate = datetime(year, month, dom, tzinfo=UTC)

            if not (START_DATE <= candidate <= END_DATE):
                continue
            ts = candidate.replace(hour=template.hour_utc, minute=template.minute_utc)
            event_id = (
                f"{template.currency}-{ts.strftime('%Y%m%dT%H%M')}-"
                f"{template.name.split()[0].lower()}"
            )
            row: dict[str, object] = {
                "event_id": event_id,
                "event_name": template.name,
                "currency": template.currency,
                "event_time_utc": ts.isoformat(),
                "impact_level": template.impact,
                "actual": None,
                "forecast": None,
                "previous": None,
                "source": f"{SOURCE_LABEL}:{template.name}",
            }
            row["source_sha256"] = _hash_row(row)
            rows.append(row)

    return rows


def _generate_jobless_claims() -> list[dict[str, object]]:
    """Generate weekly Initial Jobless Claims — every Thursday since 2008."""
    rows: list[dict[str, object]] = []
    # Start at first Thursday on or after START_DATE.
    cur = START_DATE
    while cur.weekday() != JOBLESS_CLAIMS_TEMPLATE.day_of_week:
        cur += timedelta(days=1)
    while cur <= END_DATE:
        ts = cur.replace(
            hour=JOBLESS_CLAIMS_TEMPLATE.hour_utc, minute=JOBLESS_CLAIMS_TEMPLATE.minute_utc
        )
        # Skip US holidays — Thanksgiving + Christmas week.
        if (ts.month, ts.day) in {(11, 28), (12, 25)}:
            cur += timedelta(days=7)
            continue
        event_id = f"{JOBLESS_CLAIMS_TEMPLATE.currency}-{ts.strftime('%Y%m%dT%H%M')}-jobless"
        row: dict[str, object] = {
            "event_id": event_id,
            "event_name": JOBLESS_CLAIMS_TEMPLATE.name,
            "currency": JOBLESS_CLAIMS_TEMPLATE.currency,
            "event_time_utc": ts.isoformat(),
            "impact_level": JOBLESS_CLAIMS_TEMPLATE.impact,
            "actual": None,
            "forecast": None,
            "previous": None,
            "source": f"{SOURCE_LABEL}:{JOBLESS_CLAIMS_TEMPLATE.name}",
        }
        row["source_sha256"] = _hash_row(row)
        rows.append(row)
        cur += timedelta(days=7)
    return rows


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build_catalog() -> list[dict[str, object]]:
    """Build the deterministic catalog of events 2008-2026."""
    all_rows: list[dict[str, object]] = []
    all_rows.extend(_generate_explicit())

    for key, template in _FIXED_DAY_TEMPLATES:
        all_rows.extend(_generate_fixed_day_template(key, template))

    all_rows.extend(_generate_jobless_claims())

    # Sort by event_time then event_id for deterministic output.
    all_rows.sort(key=lambda r: (r["event_time_utc"], r["event_id"]))
    # Deduplicate by event_id (in case fixed-day + explicit overlap).
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for row in all_rows:
        if row["event_id"] in seen:
            continue
        seen.add(row["event_id"])
        deduped.append(row)
    return deduped


def render_calendar(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap the rows into the JSON envelope."""
    return {
        "schema_version": SCHEMA_VERSION,
        "description": (
            "Deterministic BL-724 macro economic events calendar. "
            "Coverage: USD, EUR, GBP, JPY, CAD, AUD, NZD, CHF. "
            "Source: schedule generation anchored to publicly known central-bank "
            "decision dates; per-row sha256 anchors the canonical content."
        ),
        "generated_at_utc": "deterministic",  # stable marker for reproducibility
        "file_sha256": "to-be-overwritten",
        "events": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    rows = build_catalog()
    catalog = render_calendar(rows)
    # Compute the file sha256 over canonical JSON of the rest of the document
    # (file_sha256 excluded so the stored hash is self-verifying).
    catalog_no_hash = {k: v for k, v in catalog.items() if k != "file_sha256"}
    canonical = json.dumps(catalog_no_hash, sort_keys=True, separators=(",", ":"))
    catalog["file_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {len(rows)} events to {args.out}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["currency"]] = counts.get(r["currency"], 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    print(f"file_sha256: {catalog['file_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
