"""MacroState — aggregate macro-economic context for regime detection.

Combines FRED economic indicators with FXMacroData central bank rates and
inflation into a structured macro snapshot, then publishes it via NATS for
downstream consumers (regime detection, portfolio risk, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import polars as pl

from analytics.common.errors import MacroError
from analytics.macro.fred import FREDClient
from analytics.macro.fxmacro import FXMacroDataClient

logger = logging.getLogger(__name__)

# Default FRED series pulled for macro context
DEFAULT_FRED_SERIES: list[str] = ["GDP", "CPI", "UNRATE", "FEDFUNDS", "GDPC1"]

# NATS subject for macro state updates
MACRO_STATE_SUBJECT = "analytics.macro.state"


@dataclass
class MacroSnapshot:
    """Immutable snapshot of macro-economic conditions at a point in time."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    fred_series: dict[str, pl.DataFrame] = field(default_factory=dict)
    central_bank_rates: dict[str, float] = field(default_factory=dict)
    inflation: dict[str, pl.DataFrame] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """Serialize snapshot to a plain dict for NATS publishing."""
        summary: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "fred": {},
            "central_bank_rates": dict(self.central_bank_rates),
            "inflation": {},
        }

        for sid, df in self.fred_series.items():
            if df.is_empty():
                summary["fred"][sid] = None
            else:
                latest = df.tail(1)
                summary["fred"][sid] = {
                    "latest_value": float(latest["value"][0]),
                    "latest_date": str(latest["date"][0]),
                    "count": len(df),
                }

        for country, df in self.inflation.items():
            if df.is_empty():
                summary["inflation"][country] = None
            else:
                latest = df.tail(1)
                summary["inflation"][country] = {
                    "latest_rate": float(latest["rate"][0]),
                    "latest_date": str(latest["date"][0]),
                    "count": len(df),
                }

        return summary


class MacroStatePublisher:
    """Aggregate macro data sources and publish state.

    Combines FRED economic indicators with FXMacroData rates and inflation,
    producing a ``MacroSnapshot`` that can be published via NATS.

    The publisher is **NATS-agnostic** — it produces the snapshot dict via
    ``collect()``; the caller supplies the NATS ``EventBusClient`` and calls
    ``publish()`` to emit it.
    """

    def __init__(
        self,
        fred_client: FREDClient,
        fx_client: FXMacroDataClient,
        fred_series: list[str] | None = None,
        inflation_countries: list[str] | None = None,
    ) -> None:
        self._fred = fred_client
        self._fx = fx_client
        self._fred_series = fred_series or list(DEFAULT_FRED_SERIES)
        self._inflation_countries = inflation_countries or ["US", "GB", "JP", "DE"]

    async def collect(self) -> MacroSnapshot:
        """Fetch all data sources and assemble a ``MacroSnapshot``.

        Individual source failures are logged and produce empty placeholders
        rather than failing the whole snapshot.
        """
        snapshot = MacroSnapshot()

        # --- FRED series ---
        try:
            snapshot.fred_series = await self._fred.fetch_multiple(
                self._fred_series, start=None, end=None
            )
        except MacroError as exc:
            logger.error("Failed to fetch FRED series: %s", exc)

        # --- Central bank rates ---
        try:
            snapshot.central_bank_rates = await self._fx.fetch_central_bank_rates()
        except MacroError as exc:
            logger.error("Failed to fetch central bank rates: %s", exc)

        # --- Inflation ---
        for country in self._inflation_countries:
            try:
                snapshot.inflation[country] = await self._fx.fetch_inflation_data(country)
            except MacroError as exc:
                logger.error("Failed to fetch inflation for %s: %s", country, exc)

        return snapshot

    async def collect_summary(self) -> dict[str, Any]:
        """Convenience: collect data and return the serializable summary dict."""
        snapshot = await self.collect()
        return snapshot.summary()

    async def publish(
        self,
        nats_client: Any,  # EventBusClient-compatible duck type
        subject: str = MACRO_STATE_SUBJECT,
    ) -> dict[str, Any]:
        """Collect macro state and publish it via NATS.

        Args:
            nats_client: An object with a ``publish(subject, data)`` async
                method  (e.g. ``core.events.client.EventBusClient``).
            subject: NATS subject to publish on.

        Returns:
            The summary dict that was published.
        """
        summary = await self.collect_summary()
        await nats_client.publish(subject, data=summary, source="analytics.macro")
        logger.info("Published macro state to %s", subject)
        return summary
