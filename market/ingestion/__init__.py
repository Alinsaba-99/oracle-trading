"""Market data ingestion pipeline.

The :class:`IngestionPipeline` manages multiple :class:`BaseSource`
instances, connects to NATS via :class:`EventBusClient`, and routes
normalized market data to ``market.tick`` and ``market.bar`` subjects.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from analytics.common.errors import IngestionError
from core.config.settings import OracleSettings
from core.events.client import EventBusClient
from core.events.market import MarketBarEvent, MarketTickEvent
from market.normalizer import Normalizer
from market.sources.base import BaseSource

logger = logging.getLogger(__name__)


# Default bar aggregation interval in seconds.
_BAR_INTERVAL_S = 60


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

        - **Tick events** (``event_type == "tick"`` or absent) are normalized,
          published to ``market.tick``, and buffered per-symbol for bar
          aggregation.
        - **Bar events** (``event_type == "bar"``) are published directly to
          ``market.bar`` *without* passing through the tick buffer, preserving
          the original OHLCV values from the source (e.g. a Binance final
          kline).

        Bars are flushed at a fixed time interval (default 60 s), and each
        symbol has its own buffer so multi-symbol sources cannot produce
        cross-contaminated bars.
        """
        tick_buffers: dict[str, list[dict[str, Any]]] = {}

        async def _periodic_flush() -> None:
            """Periodically flush all per-symbol buffers on a timer."""
            while self._running:
                await asyncio.sleep(_BAR_INTERVAL_S)
                for _instr_id, buf in list(tick_buffers.items()):
                    if buf:
                        await self._flush_bar(source.name, buf)
                        buf.clear()

        flush_task = asyncio.create_task(_periodic_flush())

        try:
            while self._running:
                try:
                    raw = await source.events.get()
                except asyncio.CancelledError:
                    break

                event_type = raw.get("event_type", "tick")

                if event_type == "bar":
                    # Source already provides a complete OHLCV bar
                    # (e.g. Binance final kline).  Publish directly as a
                    # bar event, preserving the actual high/low/open
                    # values, skipping tick re-aggregation.
                    try:
                        self._normalizer.validate_bar(raw)
                        await self._publish_bar(source.name, raw)
                    except ValueError as exc:
                        logger.warning("Dropping invalid bar from %s: %s", source.name, exc)
                    continue

                # Normal tick processing
                try:
                    tick = self._normalizer.normalize_tick(raw)
                except ValueError as exc:
                    logger.warning("Dropping invalid tick from %s: %s", source.name, exc)
                    continue

                instr_id = tick["instrument_id"]
                if instr_id not in tick_buffers:
                    tick_buffers[instr_id] = []

                # Publish tick event
                try:
                    await self._publish_tick(tick)
                except Exception:
                    logger.exception("Failed to publish tick from %s", source.name)

                # Buffer per-symbol for bar aggregation
                tick_buffers[instr_id].append(tick)
        finally:
            flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await flush_task

            # Flush any remaining ticks
            for _instr_id, buf in tick_buffers.items():
                if buf:
                    await self._flush_bar(source.name, buf)

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

    async def _publish_bar(self, source_name: str, bar: dict[str, Any]) -> None:
        """Publish a pre-computed OHLCV bar as a MarketBarEvent.

        Used when the data source already provides a complete bar
        (e.g. Binance final kline with ``event_type: "bar"``).
        """
        event = MarketBarEvent(
            instrument_id=bar["instrument_id"],
            asset_class="crypto",
            exchange=source_name,
            timeframe="1m",
            open=bar["open"],
            high=bar["high"],
            low=bar["low"],
            close=bar["close"],
            volume=bar["volume"],
            trades=bar.get("trades", 0),
        )
        try:
            await self._event_bus.publish(
                "market.bar", event.model_dump(mode="json"), source=f"oracle.market.{source_name}"
            )
        except Exception:
            logger.exception("Failed to publish bar from %s", source_name)

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
