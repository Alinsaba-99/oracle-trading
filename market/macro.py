"""Global macro event data — GDELT, NewsAPI, central bank calendars.

Provides:
- GDELT: 300+ event categories, free, real-time global events
- Central bank rate decision calendar
- Economic indicator release schedule
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("oracle.data.macro")


# ── GDELT Project ───────────────────────────────────────────────────
# GDELT monitors print, broadcast, web news in 100+ languages.
# API: https://api.gdeltproject.org/api/v2/doc/doc
# Free, no key required, rate limit ~1 req/sec.

GDELT_BASE = "https://api.gdeltproject.org/api/v2"


class MacroEventFetcher:
    """Fetch global macro events from multiple free sources."""

    def __init__(self) -> None:
        self._http = httpx.Client(timeout=30)
        self._last_request: float = 0.0

    # ── GDELT ────────────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        """Ensure at least 1.5 seconds between requests (GDELT rate limit)."""
        import time

        elapsed = time.time() - self._last_request
        if elapsed < 1.5:
            time.sleep(1.5 - elapsed)
        self._last_request = time.time()

    def gdelt_events(
        self,
        query: str = "inflation OR GDP OR unemployment OR central+bank",
        start_date: str | None = None,
        end_date: str | None = None,
        max_records: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch global events from GDELT.

        GDELT categorizes events with ACTION_GEO and ACTION_GLOBAL codes.

        Args:
            query: Search query (boolean operators supported).
            start_date: YYYY-MM-DD (default: 30 days ago).
            end_date: YYYY-MM-DD (default: today).
            max_records: Max articles to return (max 250).

        Returns:
            List of event dicts with: title, url, date, tone, source.
        """
        params: dict[str, Any] = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(max_records, 250),
        }
        if start_date:
            params["startdate"] = start_date
        if end_date:
            params["enddate"] = end_date

        try:
            self._rate_limit()
            resp = self._http.get(f"{GDELT_BASE}/doc/doc", params=params)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", data.get("results", []))
            logger.info("GDELT events fetched", query=query, count=len(articles))

            result = []
            for art in articles:
                result.append(
                    {
                        "title": art.get("title", ""),
                        "url": art.get("url", ""),
                        "date": art.get("seendate", art.get("date", "")),
                        "tone": art.get("tone", ""),
                        "source": art.get("domain", ""),
                        "categories": art.get("categories", []),
                    }
                )
            return result
        except Exception as e:
            logger.warning("GDELT fetch failed", error=str(e))
            return []

    def gdelt_recent_macro(self, days: int = 7) -> list[dict[str, Any]]:
        """Fetch recent macro-economic events (inflation, GDP, central bank)."""
        from datetime import timedelta

        start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.gdelt_events(
            query="(inflation OR GDP OR unemployment OR 'central bank' OR 'interest rate' OR CPI) AND (economy OR financial OR market)",
            start_date=start,
            max_records=100,
        )

    def gdelt_earnings(self, ticker: str, days: int = 30) -> list[dict[str, Any]]:
        """Fetch news about a specific ticker/company."""
        from datetime import timedelta

        start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.gdelt_events(query=ticker, start_date=start, max_records=50)

    # ── Central bank calendar ──────────────────────────────────────

    @staticmethod
    def central_bank_calendar() -> list[dict[str, str]]:
        """Return the next scheduled central bank rate decisions.

        Data is pre-computed from known schedules (updated quarterly).
        """
        return [
            {"bank": "FED", "date": "2026-07-29", "description": "FOMC rate decision"},
            {"bank": "FED", "date": "2026-09-16", "description": "FOMC rate decision"},
            {"bank": "FED", "date": "2026-11-04", "description": "FOMC rate decision"},
            {"bank": "ECB", "date": "2026-07-23", "description": "ECB rate decision"},
            {"bank": "ECB", "date": "2026-09-11", "description": "ECB rate decision"},
            {"bank": "BOE", "date": "2026-08-06", "description": "BOE rate decision"},
            {"bank": "BOJ", "date": "2026-07-30", "description": "BOJ rate decision"},
            {"bank": "RBA", "date": "2026-08-04", "description": "RBA rate decision"},
        ]

    @staticmethod
    def economic_calendar() -> list[dict[str, str]]:
        """Major economic indicator release dates."""
        return [
            {"indicator": "NFP (Non-Farm Payrolls)", "date": "2026-08-07", "source": "BLS"},
            {"indicator": "CPI (Consumer Price Index)", "date": "2026-08-13", "source": "BLS"},
            {"indicator": "GDP (Advance)", "date": "2026-07-30", "source": "BEA"},
            {"indicator": "PPI (Producer Price Index)", "date": "2026-08-12", "source": "BLS"},
            {"indicator": "Retail Sales", "date": "2026-08-14", "source": "Census"},
        ]
