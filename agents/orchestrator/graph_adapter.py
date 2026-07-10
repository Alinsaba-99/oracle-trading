"""WorkflowEngine protocol — isolates the MAS from LangGraph directly."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkflowEngine(Protocol):
    """Protocol that isolates the MAS from LangGraph directly."""

    async def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Run the workflow with the given initial state."""


class LangGraphWorkflowEngine:
    """Wraps a compiled LangGraph StateGraph behind the WorkflowEngine protocol."""

    def __init__(self, app: Any) -> None:
        """Wrap a compiled LangGraph state graph.

        Parameters
        ----------
        app :
            A compiled ``StateGraph`` instance with an ``ainvoke`` method.
        """
        self._app = app

    async def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Run the graph asynchronously with *initial_state*."""
        result: dict[str, Any] = await self._app.ainvoke(initial_state)
        return result
