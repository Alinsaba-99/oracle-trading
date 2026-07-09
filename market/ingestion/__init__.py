"""Market data ingestion pipeline.

The :class:`IngestionPipeline` manages multiple :class:`BaseSource`
instances, connects to NATS via :class:`EventBusClient`, and routes
normalized market data to ``market.tick`` and ``market.bar`` subjects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from analytics.common.errors import IngestionError
from core.config.settings import OracleSettings
from core.events.client import EventBusClient
from core.events.market import MarketBarEvent, MarketTickEvent
from market.normalizer import Normalizer
from market.sources.base import BaseSource

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrate multiple market data sources.

    Usage::

        pipeline = IngestionPipeline(settings)
        pipeline.add_source(source1)
        pipeline.add_source(source2)
        await pipeline.start()
        # ... runs until pipeline.stop()
        await pipeline.stop()
    """

    def __init__(self, settings: OracleSettings, sources: list[BaseSource] | None = None) -> None:
        self._settings = settings
        self._sources: list[BaseSource] = list(sources) if sources else []
        self._event_bus: EventBusClient = EventBusClient(settings.nats)
        self._normalizer = Normalizer()
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def add_source(self, source: BaseSource) -> None:
        """Register a market data source."""
        self._sources.append(source)

    def remove_source(self, source: BaseSource) -> None:
        """Remove a previously registered source."""
        self._sources.remove(source)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect sources, connect NATS, and start event forwarding."""
        self._running = True

        # Connect NATS event bus
        try:
            await self._event_bus.connect()
            logger.info("IngestionPipeline: NATS connected")
        except Exception as exc:
            raise IngestionError(f"Failed to connect NATS: {exc}") from exc

        # Connect all sources
        for source in self._sources:
            try:
                await source.connect()
                logger.info("IngestionPipeline: source '%s' connected", source.name)
            except Exception as exc:
                logger.warning(
                    "IngestionPipeline: source '%s' failed to connect: %s", source.name, exc
                )

        # Start per-source event forwarder tasks
        for source in self._sources:
            task = asyncio.create_task(self._forward_events(source))
            self._tasks.append(task)

        logger.info("IngestionPipeline started (%d sources)", len(self._sources))

    async def stop(self) -> None:
        """Disconnect sources and NATS, cancel forwarder tasks."""
        self._running = False

        # Cancel event forwarders
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Disconnect sources
        for source in self._sources:
            try:
                await source.disconnect()
            except Exception:
                logger.exception("IngestionPipeline: error disconnecting source '%s'", source.name)

        # Disconnect NATS
        try:
            await self._event_bus.close()
        except Exception:
            logger.exception("IngestionPipeline: error closing NATS")

        logger.info("IngestionPipeline stopped")

    # ------------------------------------------------------------------
    # Event forwarding
    # ------------------------------------------------------------------

    async def _forward_events(self, source: BaseSource) -> None:
        """Read raw events from a source's queue, normalize, and publish.

        Ticks are published as ``MarketTickEvent`` on ``market.tick``.
        Every 60 ticks the pipeline aggregates a single bar and publishes
        it as ``MarketBarEvent`` on ``market.bar``.
        """
        tick_buffer: list[dict[str, Any]] = []

        while self._running:
            try:
                raw = await source.events.get()
            except asyncio.CancelledError:
                break

            try:
                tick = self._normalizer.normalize_tick(raw)
            except ValueError as exc:
                logger.warning("Dropping invalid tick from %s: %s", source.name, exc)
                continue

            # Publish tick event
            try:
                await self._publish_tick(tick)
            except Exception:
                logger.exception("Failed to publish tick from %s", source.name)

            # Buffer for bar aggregation (every 60 ticks)
            tick_buffer.append(tick)
            if len(tick_buffer) >= 60:
                await self._flush_bar(source.name, tick_buffer)
                tick_buffer.clear()

        # Flush any remaining ticks
        if tick_buffer:
            await self._flush_bar(source.name, tick_buffer)

    async def _publish_tick(self, tick: dict[str, Any]) -> None:
        """Publish a normalized tick as a MarketTickEvent."""
        event = MarketTickEvent(
            instrument_id=tick["instrument_id"],
            asset_class="crypto",
            exchange=tick.get("source", "unknown"),
            bid=tick.get("bid", 0),
            ask=tick.get("ask", 0),
            last=tick.get("price"),
            volume=tick.get("volume", 0),
        )
        await self._event_bus.publish(
            "market.tick",
            event.model_dump(mode="json"),
            source=f"oracle.market.{tick.get('source', 'unknown')}",
        )

    async def _flush_bar(self, source_name: str, ticks: list[dict[str, Any]]) -> None:
        """Aggregate buffered ticks into a bar and publish."""
        try:
            bar = self._normalizer.aggregate_bars(ticks, "1m")
            self._normalizer.validate_bar(bar)
        except ValueError as exc:
            logger.warning("Bar aggregation failed for %s: %s", source_name, exc)
            return

        event = MarketBarEvent(
            instrument_id=bar["instrument_id"],
            asset_class="crypto",
            exchange=source_name,
            timeframe=bar["timeframe"],
            open=bar["open"],
            high=bar["high"],
            low=bar["low"],
            close=bar["close"],
            volume=bar["volume"],
            trades=bar["trades"],
        )
        try:
            await self._event_bus.publish(
                "market.bar", event.model_dump(mode="json"), source=f"oracle.market.{source_name}"
            )
        except Exception:
            logger.exception("Failed to publish bar from %s", source_name)
