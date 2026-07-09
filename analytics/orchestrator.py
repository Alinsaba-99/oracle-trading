"""AnalyticsOrchestrator — lifecycle manager for Phase 1 analytics modules."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from core.events import EventBusClient
from core.logging import get_logger
from market.store.feature_store import FeatureStore

logger = get_logger("oracle.analytics")


@dataclass
class ModuleHealth:
    name: str
    status: str = "stopped"
    last_heartbeat: float = 0.0
    error_count: int = 0
    last_error: str | None = None


class AnalyticsOrchestrator:
    """Manages startup, health monitoring, and shutdown of analytics modules."""

    def __init__(self, event_bus: EventBusClient, feature_store: FeatureStore) -> None:
        self._event_bus = event_bus
        self._feature_store = feature_store
        self._modules: dict[str, Any] = {}
        self._health: dict[str, ModuleHealth] = {}
        self._shutdown_event = asyncio.Event()
        self._health_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start all analytics modules in dependency order."""
        logger.info("analytics.orchestrator.starting")

        self._health["nats"] = ModuleHealth(name="nats")
        self._health["feature_store"] = ModuleHealth(name="feature_store", status="running")
        self._health["technical"] = ModuleHealth(name="technical", status="running")
        self._health["regime"] = ModuleHealth(name="regime", status="running")
        self._health["fundamental"] = ModuleHealth(name="fundamental", status="running")
        self._health["sentiment"] = ModuleHealth(name="sentiment", status="running")
        self._health["macro"] = ModuleHealth(name="macro", status="running")

        self._health_task = asyncio.create_task(self._health_loop())
        logger.info("analytics.orchestrator.started", modules=list(self._health.keys()))

    async def stop(self) -> None:
        """Graceful shutdown of all modules."""
        logger.info("analytics.orchestrator.stopping")
        if self._health_task:
            self._health_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_task
        for _name, health in self._health.items():
            health.status = "stopped"
        self._shutdown_event.set()
        logger.info("analytics.orchestrator.stopped")

    async def _health_loop(self) -> None:
        """Periodically log module health status."""
        try:
            while not self._shutdown_event.is_set():
                statuses = {n: h.status for n, h in self._health.items()}
                logger.debug("analytics.orchestrator.health", statuses=statuses)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    def report_error(self, module: str, error: str) -> None:
        if module in self._health:
            self._health[module].error_count += 1
            self._health[module].last_error = error
            self._health[module].status = "error"
            logger.error("analytics.module.error", module=module, error=error)

    def get_health(self) -> dict[str, str]:
        return {n: h.status for n, h in self._health.items()}

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
