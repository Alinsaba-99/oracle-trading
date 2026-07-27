"""Reconciliation worker — periodic broker ↔ OMS ↔ ledger checks.

G6-105: runs the ``ReconciliationEngine`` on a configurable interval.
Fatal mismatches block new order entry until operator unblocks.

The worker is async-first and integrates with any broker / OMS / ledger
triple.  It emits structured logs and is safe to cancel.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from core.reconciliation import ReconciliationEngine, ReconciliationReport

logger = logging.getLogger("oracle.execution.reconciliation_worker")


OnMismatch = Callable[[ReconciliationReport], Awaitable[None]]


class ReconciliationWorker:
    """Periodic reconciliation loop.

    Usage::

        worker = ReconciliationWorker(engine, interval_seconds=60)
        await worker.start()        # spawn background task
        ...
        await worker.stop()         # graceful cancel
        last = worker.last_report   # most recent ReconciliationReport
    """

    def __init__(
        self,
        engine: ReconciliationEngine,
        interval_seconds: float = 60.0,
        on_mismatch: OnMismatch | None = None,
        max_consecutive_errors: int = 5,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._engine = engine
        self._interval = interval_seconds
        self._on_mismatch = on_mismatch
        self._max_errors = max_consecutive_errors
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.last_report: ReconciliationReport | None = None
        self.last_run_at: datetime | None = None
        self.run_count: int = 0
        self.error_count: int = 0

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the background reconciliation loop."""
        if self.is_running:
            logger.warning("ReconciliationWorker already running")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="reconciliation-worker")
        logger.info(f"ReconciliationWorker started (interval={self._interval}s)")

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the background loop, waiting for in-flight reconcile."""
        if not self.is_running:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=timeout)  # type: ignore[arg-type]
        except TimeoutError:
            if self._task:
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task
        self._task = None
        logger.info("ReconciliationWorker stopped")

    async def run_once(self) -> ReconciliationReport:
        """Run a single reconciliation immediately (outside the loop)."""
        report = await self._engine.reconcile()
        self._ingest(report)
        return report

    # ── internals ─────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                report = await self._engine.reconcile()
                self._ingest(report)
                consecutive_errors = 0

                if not report.is_clean:
                    logger.warning(
                        f"Reconcile mismatch: {report.fatal_count} fatal, "
                        f"{report.recoverable_count} recoverable"
                    )
                    if self._on_mismatch is not None:
                        try:
                            await self._on_mismatch(report)
                        except Exception:
                            logger.exception("on_mismatch callback failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                consecutive_errors += 1
                self.error_count += 1
                logger.exception(f"Reconciliation pass failed ({consecutive_errors} consecutive)")
                if consecutive_errors >= self._max_errors:
                    logger.error(
                        f"ReconciliationWorker stopping after {consecutive_errors} "
                        "consecutive errors"
                    )
                    return

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)

    def _ingest(self, report: ReconciliationReport) -> None:
        self.last_report = report
        self.last_run_at = datetime.now(UTC)
        self.run_count += 1


__all__ = ["ReconciliationWorker"]
