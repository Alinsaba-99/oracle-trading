"""FRED API connector for macro-economic indicator data.

Fetches time series from the Federal Reserve Economic Data (FRED) API
at ``https://api.stlouisfed.org/fred``.

Requires ``FRED_API_KEY`` environment variable. Rate limited to 120
requests per minute per FRED terms of service.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from datetime import date, datetime
from typing import Any

import httpx
import polars as pl

from analytics.common.errors import MacroError

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
DEFAULT_TIMEOUT = 30.0

# Rate limit: 120 requests per minute (FRED ToS)
MAX_REQUESTS_PER_WINDOW = 120
RATE_LIMIT_WINDOW = 60.0

# Well-known FRED series identifiers
KNOWN_SERIES: set[str] = {"GDP", "CPI", "UNRATE", "FEDFUNDS", "GDPC1"}


def _to_fred_date(d: str | date | datetime | None) -> str | None:
    """Normalize a date value to ``YYYY-MM-DD`` string."""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d")


class FREDClient:
    """Async FRED API client with automatic rate-limit management.

    Usage::

        async with FREDClient(api_key="…") as fred:
            df = await fred.fetch_series("GDP", start="2020-01-01")
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self._api_key:
            msg = "FRED_API_KEY not set — provide ``api_key`` or set the environment variable."
            raise MacroError(msg)

        self._client: httpx.AsyncClient | None = None
        # Rolling window of request timestamps for rate limiting
        self._request_times: deque[float] = deque()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> FREDClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Open the HTTP client session."""
        self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        logger.info("FREDClient connected")

    async def disconnect(self) -> None:
        """Close the HTTP client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("FREDClient disconnected")

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _acquire(self) -> None:
        """Block until a rate-limit slot is available."""
        now = time.monotonic()
        # Evict timestamps outside the current window
        cutoff = now - RATE_LIMIT_WINDOW
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

        if len(self._request_times) >= MAX_REQUESTS_PER_WINDOW:
            sleep_for = self._request_times[0] + RATE_LIMIT_WINDOW - now
            if sleep_for > 0:
                logger.warning("FRED rate limit reached — sleeping %.2fs", sleep_for)
                await asyncio.sleep(sleep_for)

        self._request_times.append(time.monotonic())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_series(
        self,
        series_id: str,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> pl.DataFrame:
        """Fetch observations for a FRED time series.

        Returns a ``pl.DataFrame`` with columns ``date`` (``pl.Date``) and
        ``value`` (``pl.Float64``). Missing observations (``"."``) are
        excluded.

        Raises:
            MacroError: On API errors, timeouts, or unexpected response shape.
        """
        if self._client is None:
            msg = "FREDClient not connected — call ``.connect()`` first."
            raise MacroError(msg)

        params: dict[str, str] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
        }

        start_str = _to_fred_date(start)
        end_str = _to_fred_date(end)
        if start_str:
            params["observation_start"] = start_str
        if end_str:
            params["observation_end"] = end_str

        await self._acquire()

        try:
            response = await self._client.get(f"{FRED_BASE_URL}/series/observations", params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            msg = f"FRED API HTTP {exc.response.status_code}: {body}"
            raise MacroError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"FRED API timeout after {DEFAULT_TIMEOUT}s"
            raise MacroError(msg) from exc
        except httpx.RequestError as exc:
            msg = f"FRED API request failed: {exc}"
            raise MacroError(msg) from exc

        observations: list[dict[str, str]] | None = data.get("observations")
        if observations is None:
            msg = "FRED response missing ``observations`` key"
            raise MacroError(msg)

        rows: list[dict[str, Any]] = []
        for obs in observations:
            raw_val = obs.get("value")
            if raw_val in (".", None, ""):
                continue
            rows.append({"date": obs["date"], "value": float(raw_val)})  # type: ignore[arg-type]

        if not rows:
            return pl.DataFrame(
                {"date": pl.Series([], dtype=pl.Date), "value": pl.Series([], dtype=pl.Float64)}
            )

        df = pl.DataFrame(rows).with_columns(pl.col("date").str.to_date("%Y-%m-%d")).sort("date")
        return df

    async def fetch_multiple(
        self,
        series_ids: list[str],
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
    ) -> dict[str, pl.DataFrame]:
        """Fetch several FRED series concurrently.

        Returns a dict mapping ``series_id`` → ``pl.DataFrame``.
        """
        import asyncio

        async def _fetch_one(sid: str) -> tuple[str, pl.DataFrame]:
            df = await self.fetch_series(sid, start=start, end=end)
            return sid, df

        coros = [_fetch_one(sid) for sid in series_ids]
        results = await asyncio.gather(*coros, return_exceptions=True)

        out: dict[str, pl.DataFrame] = {}
        for sid, res in zip(series_ids, results, strict=False):
            if isinstance(res, BaseException):
                logger.error("Failed to fetch %s: %s", sid, res)
                continue
            _sid, df = res
            out[sid] = df
        return out
