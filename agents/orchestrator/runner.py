"""MASRunner — CLI bridge for the Multi-Agent System."""

from __future__ import annotations

from typing import Any

from agents.orchestrator.orchestrator import MASOrchestrator


class MASRunner:
    """CLI bridge for the MAS.  Supports single-shot and loop modes.

    Parameters
    ----------
    orchestrator :
        Pre-configured ``MASOrchestrator`` instance.
    """

    def __init__(self, orchestrator: MASOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def run_once(self, instrument: str = "SPY", data: Any | None = None) -> Any | None:
        """Run a single MAS cycle.

        Parameters
        ----------
        instrument :
            Trading instrument identifier (default ``"SPY"``).
        data :
            Market data passed to the orchestrator (e.g. ``pl.DataFrame``).

        Returns
        -------
            The portfolio decision or ``None``.
        """
        return await self._orchestrator.run(data, instrument)
