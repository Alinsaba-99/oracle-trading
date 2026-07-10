"""MASOrchestrator — top-level lifecycle for the Multi-Agent System.

Manages:  init -> run -> report
"""

from __future__ import annotations

from typing import Any

from agents.orchestrator.state import StateManager


class MASOrchestrator:
    """Top-level orchestrator for the Multi-Agent System.

    Parameters
    ----------
    config :
        Optional ``MASConfig`` instance.
    engine :
        Optional ``WorkflowEngine`` instance.  When ``None``, ``run()``
        returns the initial state dict untouched.
    """

    def __init__(self, config: Any | None = None, engine: Any | None = None) -> None:
        self._config = config
        self._engine = engine
        self._last_result: dict[str, Any] | None = None

    async def run(self, market_data: Any, instrument: str = "SPY") -> Any | None:
        """Run a full MAS cycle.

        Parameters
        ----------
        market_data :
            Market data (e.g. ``pl.DataFrame``) passed into the initial state.
        instrument :
            Trading instrument identifier (default ``"SPY"``).

        Returns
        -------
            The ``"decision"`` value from the final graph state, or ``None``.
        """
        initial = StateManager.initial(instrument)
        initial["market_data"] = market_data

        if self._engine is not None:
            result = await self._engine.run(initial)
        else:
            result = initial

        self._last_result = result
        return result.get("decision")

    @property
    def last_result(self) -> dict[str, Any] | None:
        """The most recent full graph state, or ``None`` if never run."""
        return self._last_result
