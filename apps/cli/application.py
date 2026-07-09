"""OracleApplication — lifecycle manager with signal handlers."""

from __future__ import annotations

import asyncio
import signal

from core.logging import get_logger

logger = get_logger("oracle.app")


class OracleApplication:
    """Context manager with signal handlers and clean shutdown.

    Usage:
        async with OracleApplication() as app:
            await app.run()
    """

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    async def __aenter__(self) -> OracleApplication:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):

            def _signal_handler(s: signal.Signals = sig) -> None:
                task = asyncio.create_task(self.shutdown(s))
                self._tasks.append(task)

            loop.add_signal_handler(sig, _signal_handler)
        logger.info("oracle.application.started")
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._cleanup()

    def add_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.append(task)

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    async def shutdown(self, sig: signal.Signals) -> None:
        logger.info("oracle.application.shutdown", signal=sig.name)
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._cleanup()

    async def _cleanup(self) -> None:
        self._shutdown_event.set()
        logger.info("oracle.application.stopped")
