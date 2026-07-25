"""Tests for core.reconciliation_worker — periodic reconcile loop (G6-105)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.reconciliation import Mismatch, MismatchSeverity, MismatchType, ReconciliationReport


def _clean_report() -> ReconciliationReport:
    return ReconciliationReport()


def _dirty_report() -> ReconciliationReport:
    return ReconciliationReport(
        mismatches=[
            Mismatch(
                mismatch_type=MismatchType.POSITION,
                severity=MismatchSeverity.RECOVERABLE,
                instrument_id="ES",
                description="test",
            )
        ]
    )


class TestReconciliationWorker:
    """ReconciliationWorker must run periodically and handle errors."""

    async def test_start_stop(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(return_value=_clean_report())
        worker = ReconciliationWorker(engine, interval_seconds=0.05)

        await worker.start()
        assert worker.is_running
        await asyncio.sleep(0.15)  # let it tick a couple of times
        await worker.stop()

        assert not worker.is_running
        assert worker.run_count >= 1
        assert worker.last_report is not None

    async def test_run_once_outside_loop(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(return_value=_clean_report())
        worker = ReconciliationWorker(engine, interval_seconds=60.0)

        report = await worker.run_once()
        assert report.is_clean
        assert worker.run_count == 1
        assert worker.last_run_at is not None

    async def test_on_mismatch_callback_fires(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(return_value=_dirty_report())

        calls: list[ReconciliationReport] = []

        async def on_mismatch(report: ReconciliationReport) -> None:
            calls.append(report)

        worker = ReconciliationWorker(engine, interval_seconds=0.05, on_mismatch=on_mismatch)
        await worker.start()
        await asyncio.sleep(0.12)
        await worker.stop()

        assert len(calls) >= 1
        assert not calls[0].is_clean

    async def test_engine_error_does_not_kill_worker_immediately(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(side_effect=RuntimeError("boom"))
        worker = ReconciliationWorker(engine, interval_seconds=0.05, max_consecutive_errors=10)

        await worker.start()
        await asyncio.sleep(0.18)
        await worker.stop()

        assert worker.error_count >= 1

    async def test_stops_after_max_consecutive_errors(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(side_effect=RuntimeError("boom"))
        worker = ReconciliationWorker(engine, interval_seconds=0.05, max_consecutive_errors=2)

        await worker.start()
        # worker should self-terminate after 2 errors
        for _ in range(40):
            if not worker.is_running:
                break
            await asyncio.sleep(0.02)

        assert not worker.is_running
        assert worker.error_count >= 2

    async def test_invalid_interval_rejected(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        with pytest.raises(ValueError, match="interval_seconds"):
            ReconciliationWorker(engine, interval_seconds=0)

    async def test_start_idempotent(self) -> None:
        from core.reconciliation_worker import ReconciliationWorker

        engine = MagicMock()
        engine.reconcile = AsyncMock(return_value=_clean_report())
        worker = ReconciliationWorker(engine, interval_seconds=0.05)

        await worker.start()
        task1 = worker._task
        await worker.start()  # second start is a no-op
        assert worker._task is task1
        await worker.stop()


# type-check helper for Any
_: Any = None
