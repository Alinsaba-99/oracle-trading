"""BL-023 P1d — Macro consensus feasibility probe (NASDaq economic calendar).

Downloads US macro events with BOTH actual and consensus values from the
public NASDaq API (zero cost, no auth) for the M31 replay window dates,
normalizes the raw strings ("219K" -> 219000, "-0.2%" -> -0.2), and appends
them to data/macro/m31-events.json in the MacroSurpriseEvent schema.

Purpose: prove that a point-in-time consensus source exists at zero cost so
the macro_surprise regime blocker (BL-023 F-4) can be lifted — or, if the
fetch yields nothing usable, document that the "5+1 regimes" re-spec is the
only honest path.

Usage:
    uv run --frozen python scripts/fetch_macro_events.py \
        --dates 2008-11-07 2008-12-05 2009-05-08 2019-10-04
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BASE_URL = "https://api.nasdaq.com/api/calendar/economicevents?date={date}"
OUT_PATH = Path("data/macro/m31-events.json")
RELEASE_TZ = ZoneInfo("America/New_York")
#: Default release time when the API row has no usable GMT (08:30 ET).
DEFAULT_RELEASE = time(8, 30)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "application/json",
}

#: High-impact US macro indicators that count as "macro surprise" for the
#: M31 regime. Filters out weekly stock/inventory data whose absolute
#: surprise (millions of barrels) would otherwise dominate the ranking.
HIGH_IMPACT = (
    "Nonfarm Payrolls",
    "Unemployment Rate",
    "Initial Jobless Claims",
    "Continuing Jobless Claims",
    "CPI",
    "PPI",
    "GDP",
    "ISM Manufacturing PMI",
    "ISM Non-Manufacturing PMI",
    "ISM Non-Manufacturing Business Activity",
    "FOMC",
    "Retail Sales",
    "Housing Starts",
    "Building Permits",
    "Consumer Confidence",
    "Michigan Consumer Sentiment",
    "Durable Goods Orders",
    "ADP Nonfarm Employment Change",
    "Average Hourly Earnings",
    "Average Weekly Hours",
    "Federal Funds Rate",
    "Trade Balance",
    "Current Account",
    "Nonfarm Productivity",
    "Unit Labor Costs",
)


def _parse_number(raw: str | None) -> float | None:
    """Parse NASDaq raw values: '219K' -> 219000, '-0.2%' -> -0.2, '' -> None."""
    if raw is None:
        return None
    text = raw.strip().replace("\u00a0", "").replace("&nbsp;", "")
    if not text or text in ("-", "—"):
        return None
    multiplier = 1.0
    if text.endswith("K") or text.endswith("k"):
        multiplier = 1e3
        text = text[:-1]
    elif text.endswith("M") or text.endswith("m"):
        multiplier = 1e6
        text = text[:-1]
    text = text.rstrip("%")
    text = text.replace(",", "")
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _event_time(date_str: str, gmt: str | None) -> datetime:
    """Event release instant in UTC. Prefer the API's GMT field, fall back
    to 08:30 America/New_York."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    if gmt and re.match(r"^\d{1,2}:\d{2}$", gmt):
        hour, minute = (int(part) for part in gmt.split(":"))
        local = datetime.combine(day, time(hour, minute), tzinfo=UTC)
        return local
    local = datetime.combine(day, DEFAULT_RELEASE, tzinfo=RELEASE_TZ)
    return local.astimezone(UTC)


def _fetch(date_str: str) -> tuple[list[dict[str, Any]], str]:
    url = BASE_URL.format(date=date_str)
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    raw_hash = hashlib.sha256(payload).hexdigest()
    data = json.loads(payload)
    rows = data.get("data", {}).get("rows", [])
    return rows, raw_hash


def _normalize(rows: list[dict[str, Any]], date_str: str, raw_hash: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        country = (row.get("country") or "").strip()
        if country != "United States":
            continue
        actual = _parse_number(row.get("actual"))
        consensus = _parse_number(row.get("consensus"))
        indicator = (row.get("eventName") or "").strip()
        if actual is None or consensus is None or not indicator:
            continue
        if not any(key in indicator for key in HIGH_IMPACT):
            continue
        event_time = _event_time(date_str, row.get("gmt"))
        events.append(
            {
                "event_time": event_time.isoformat(),
                "available_at": event_time.isoformat(),
                "indicator": indicator,
                "actual": actual,
                "consensus": consensus,
                "source": BASE_URL.format(date=date_str),
                "source_sha256": raw_hash,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "raw_actual": row.get("actual"),
                "raw_consensus": row.get("consensus"),
                "raw_previous": row.get("previous"),
            }
        )
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="+", required=True, help="YYYY-MM-DD dates to fetch")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    existing: dict[str, Any] = {
        "schema_version": "m31-macro-events-v1",
        "events": [],
        "normalization": {},
    }
    if args.out.exists():
        existing = json.loads(args.out.read_text())

    seen = {(e["event_time"], e["indicator"]) for e in existing["events"]}
    fetched = 0
    added = 0
    for date_str in args.dates:
        try:
            rows, raw_hash = _fetch(date_str)
        except Exception as exc:  # network/parse failures must not kill the probe
            print(f"  ! {date_str}: fetch failed ({exc})")
            continue
        events = _normalize(rows, date_str, raw_hash)
        fetched += 1
        print(f"  {date_str}: {len(rows)} rows, {len(events)} US events with actual+consensus")
        for event in events:
            key = (event["event_time"], event["indicator"])
            if key in seen:
                continue
            existing["events"].append(event)
            seen.add(key)
            added += 1
            print(
                f"    + {event['event_time']} {event['indicator']}: "
                f"actual={event['raw_actual']} consensus={event['raw_consensus']}"
            )

    existing["events"].sort(key=lambda e: e["event_time"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(existing, indent=2) + "\n")
    print(
        f"\nFetched {fetched} dates, added {added} events -> {args.out} "
        f"({len(existing['events'])} total)"
    )
    return 0 if added else 1


if __name__ == "__main__":
    sys.exit(main())
