"""LangGraph StateGraph definition for the Multi-Agent System.

Flow:  oracle -> analysts (parallel) -> debate -> risk -> portfolio -> END
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph


class GraphState(TypedDict):
    """State type used by the LangGraph state graph."""

    market_data: Any
    market_state: Any
    analyst_signals: list[Any]
    debate: Any
    risk_assessment: Any
    decision: Any
    errors: list[str]
    run_id: str
    total_tokens: int
    timing: dict[str, float]


# ---------------------------------------------------------------------------
# Node functions  (simplified stubs — real async calls wired next iteration)
# ---------------------------------------------------------------------------


def oracle_node(_state: GraphState) -> dict[str, Any]:
    """Call MarketOracle to analyze market state.

    Real implementation will call ``await oracle.analyze(state["market_data"])``.
    """
    return {}


def analysts_node(_state: GraphState) -> dict[str, Any]:
    """Run parallel analyst agents.

    Real implementation will call ``asyncio.gather(...)`` over configured analysts.
    """
    return {}


def debate_node(_state: GraphState) -> dict[str, Any]:
    """Run structured debate over analyst signals."""
    return {}


def risk_node(_state: GraphState) -> dict[str, Any]:
    """Check risk constraints on the proposed decision."""
    return {
        "risk_assessment": {
            "approved": True,
            "max_position_size": 0.25,
            "kelly_fraction": 0.5,
            "var_95": 0.02,
            "reasons": [],
        }
    }


def portfolio_node(_state: GraphState) -> dict[str, Any]:
    """Make final portfolio decision after risk check."""
    return {
        "decision": {
            "direction": "hold",
            "instrument": "SPY",
            "position_size": 0.0,
            "confidence": 0.5,
            "reasoning": "No strong signals — holding.",
            "agents_contributing": [],
            "regime_at_decision": "unknown",
            "risk_approved": True,
            "escalated": False,
        }
    }


def router(state: GraphState) -> Literal["risk", "portfolio", "__end__"]:
    """Route based on debate outcome.

    Returns
    -------
        ``"risk"``       — default path (debate produced consensus -> check risk).
        ``"portfolio"``  — skip risk when debate lacked consensus.
        ``"__end__"``    — terminate early when there are critical errors.
    """
    if state.get("errors") and any("critical" in str(e).lower() for e in state["errors"]):
        return "__end__"

    debate = state.get("debate")
    if debate and isinstance(debate, dict) and debate.get("consensus"):
        return "risk"

    return "portfolio"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_mas_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the MAS LangGraph state graph.

    Flow::

        oracle -> analysts -> debate -> risk -> portfolio -> END
                    |                      |
                    +-- ... ---------------+   (conditional route)

    Returns
    -------
        A compiled ``StateGraph`` ready for ``.invoke()`` / ``.ainvoke()``.
    """
    graph: StateGraph[Any, Any, Any, Any] = StateGraph(GraphState)

    # Nodes
    graph.add_node("oracle", oracle_node)  # type: ignore[call-overload]
    graph.add_node("analysts", analysts_node)  # type: ignore[call-overload]
    graph.add_node("debate", debate_node)  # type: ignore[call-overload]
    graph.add_node("risk", risk_node)  # type: ignore[call-overload]
    graph.add_node("portfolio", portfolio_node)  # type: ignore[call-overload]

    # Edges
    graph.set_entry_point("oracle")
    graph.add_edge("oracle", "analysts")
    graph.add_edge("analysts", "debate")
    graph.add_conditional_edges(
        "debate", router, {"risk": "risk", "portfolio": "portfolio", END: END}
    )
    graph.add_edge("risk", "portfolio")
    graph.add_edge("portfolio", END)

    return graph.compile()
