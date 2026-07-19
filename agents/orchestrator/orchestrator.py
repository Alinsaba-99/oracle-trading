"""MASOrchestrator — top-level lifecycle for the Multi-Agent System.

Manages:  init -> run -> report
"""

from __future__ import annotations

from typing import Any

from agents.orchestrator.state import StateManager
from agents.protocol import PortfolioDecision


class MASOrchestrator:
    """Top-level orchestrator for the Multi-Agent System.

    Parameters
    ----------
    config :
        Optional ``MASConfig`` instance.
    engine :
        Optional ``WorkflowEngine`` instance.  When ``None``, ``run()``
        returns the initial state dict untouched.
    bridge :
        Optional ``PortfolioBridge`` instance. When provided together with
        ``order_manager``, BUY/SELL decisions are translated into
        ``OrderRequest`` objects and submitted.
    order_manager :
        Optional ``OrderManager`` instance used for live/paper execution.
    """

    def __init__(
        self,
        config: Any | None = None,
        engine: Any | None = None,
        bridge: Any | None = None,
        order_manager: Any | None = None,
    ) -> None:
        self._config = config
        self._engine = engine
        self._bridge = bridge
        self._order_manager = order_manager
        self._last_result: dict[str, Any] | None = None
        self._last_order_request: Any | None = None
        self._last_order_result: Any | None = None

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

        decision = result.get("decision")
        self._last_order_request = None
        self._last_order_result = None

        if decision is not None and self._bridge is not None and self._order_manager is not None:
            order_request = self._bridge.to_order_request(self._coerce_decision(decision))
            if order_request is not None:
                self._last_order_request = order_request
                self._last_order_result = await self._order_manager.submit(order_request)
                if isinstance(result, dict):
                    result = {**result, "order_result": self._last_order_result}

        self._last_result = result
        return decision

    @staticmethod
    def _coerce_decision(decision: Any) -> PortfolioDecision:
        """Convert a raw decision dict into ``PortfolioDecision`` when needed."""
        if isinstance(decision, PortfolioDecision):
            return decision
        if isinstance(decision, dict):
            return PortfolioDecision(**decision)
        return decision  # type: ignore[no-any-return]

    @property
    def last_result(self) -> dict[str, Any] | None:
        """The most recent full graph state, or ``None`` if never run."""
        return self._last_result

    @property
    def last_order_request(self) -> Any | None:
        """The most recent bridged order request, or ``None`` if none emitted."""
        return self._last_order_request

    @property
    def last_order_result(self) -> Any | None:
        """The most recent execution result, or ``None`` if none submitted."""
        return self._last_order_result
