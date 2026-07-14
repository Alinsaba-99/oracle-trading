"""LangGraph StateGraph definition for the Multi-Agent System.

Flow:  oracle -> analysts (parallel) -> debate -> risk -> portfolio -> END

Each node delegates to the real agent implementation when an instance is
provided via ``build_mas_graph(...)``.  When no instance is provided (e.g.
in tests or when LLM access is not configured), the node falls back to a
deterministic stub so the graph still compiles and runs end-to-end.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

__all__ = ["GraphState", "build_mas_graph", "router"]


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
# Node implementations — real wiring with graceful fallback
# ---------------------------------------------------------------------------


def _make_oracle_node(oracle: Any | None) -> Any:
    if oracle is None:
        def oracle_node_sync(_state: GraphState) -> dict[str, Any]:
            return {}
        return oracle_node_sync

    async def oracle_node(state: GraphState) -> dict[str, Any]:
        try:
            market_state = await oracle.analyze(state.get("market_data"))
            return {"market_state": market_state}
        except Exception as exc:
            return {"errors": [*state.get("errors", []), f"oracle: {exc}"]}

    return oracle_node


def _make_analysts_node(analysts: list[Any] | None) -> Any:
    if not analysts:
        def analysts_node_sync(state: GraphState) -> dict[str, Any]:
            existing = state.get("analyst_signals")
            return {} if existing else {"analyst_signals": []}
        return analysts_node_sync

    async def analysts_node(state: GraphState) -> dict[str, Any]:
        market_state = state.get("market_state")
        instrument = "SPY"
        from agents.protocol import AnalystInput

        inputs = AnalystInput(
            instrument=instrument,
            market_state=market_state,
            agent_specific_data={},
        )

        async def _safe_analyze(analyst: Any) -> Any:
            try:
                return await analyst.analyze(inputs)
            except Exception as exc:
                return {
                    "error": f"{getattr(analyst, 'name', 'analyst')}: {exc}",
                }

        results = await asyncio.gather(*[_safe_analyze(a) for a in analysts])
        signals = [r for r in results if "error" not in (r if isinstance(r, dict) else {})]
        errors = [r["error"] for r in results if isinstance(r, dict) and "error" in r]
        update: dict[str, Any] = {"analyst_signals": signals}
        if errors:
            update["errors"] = [*state.get("errors", []), *errors]
        return update

    return analysts_node


def _make_debate_node(debate_team: Any | None) -> Any:
    if debate_team is None:
        def debate_node_sync(state: GraphState) -> dict[str, Any]:
            existing = state.get("debate")
            return {} if existing is not None else {"debate": None}
        return debate_node_sync

    async def debate_node(state: GraphState) -> dict[str, Any]:
        signals = state.get("analyst_signals", [])
        if not signals:
            return {"debate": None}
        try:
            result = await debate_team.debate(signals)
            return {"debate": result}
        except Exception as exc:
            return {
                "debate": None,
                "errors": [*state.get("errors", []), f"debate: {exc}"],
            }

    return debate_node


def _make_risk_node(risk_manager: Any | None) -> Any:
    if risk_manager is None:
        def risk_node_sync(_state: GraphState) -> dict[str, Any]:
            return {
                "risk_assessment": {
                    "approved": True,
                    "max_position_size": 0.25,
                    "kelly_fraction": 0.0,
                    "var_95": 0.0,
                    "reasons": [],
                }
            }
        return risk_node_sync

    async def risk_node(state: GraphState) -> dict[str, Any]:
        debate = state.get("debate")
        consensus = getattr(debate, "consensus", None) if debate else None
        if consensus is None and isinstance(debate, dict):
            consensus = debate.get("consensus")
        if consensus is None:
            return {"risk_assessment": None}

        from agents.protocol import PortfolioDecision

        raw_direction = getattr(consensus, "direction", None) or (
            consensus.get("direction") if isinstance(consensus, dict) else "hold"
        )
        raw_confidence = getattr(consensus, "confidence", None) or (
            consensus.get("confidence") if isinstance(consensus, dict) else 0.5
        )
        direction: str = str(raw_direction) if raw_direction else "hold"
        confidence: float = float(raw_confidence) if raw_confidence else 0.5
        decision = PortfolioDecision(
            direction=direction,  # type: ignore[arg-type]
            instrument="SPY",
            position_size=confidence * 0.2,
            confidence=confidence,
            reasoning="debate consensus",
            agents_contributing=[],
            regime_at_decision="unknown",
            risk_approved=False,
        )
        try:
            assessment = risk_manager.approve(decision)
            return {"risk_assessment": assessment}
        except Exception as exc:
            return {
                "errors": [*state.get("errors", []), f"risk: {exc}"],
                "risk_assessment": None,
            }

    return risk_node


def _make_portfolio_node(portfolio_manager: Any | None) -> Any:
    if portfolio_manager is None:
        def portfolio_node_sync(_state: GraphState) -> dict[str, Any]:
            return {
                "decision": {
                    "direction": "hold",
                    "instrument": "SPY",
                    "position_size": 0.0,
                    "confidence": 0.5,
                    "reasoning": "No portfolio manager configured — holding.",
                    "agents_contributing": [],
                    "regime_at_decision": "unknown",
                    "risk_approved": True,
                    "escalated": False,
                }
            }
        return portfolio_node_sync

    async def portfolio_node(state: GraphState) -> dict[str, Any]:
        signals = state.get("analyst_signals", [])
        market_state = state.get("market_state")
        try:
            decision = portfolio_manager.decide(signals, market_state)
            return {"decision": decision}
        except Exception as exc:
            return {
                "decision": {
                    "direction": "hold",
                    "instrument": "SPY",
                    "position_size": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"Portfolio manager error: {exc}",
                    "agents_contributing": [],
                    "regime_at_decision": "unknown",
                    "risk_approved": False,
                    "escalated": True,
                },
                "errors": [*state.get("errors", []), f"portfolio: {exc}"],
            }

    return portfolio_node


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


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


def build_mas_graph(
    *,
    oracle: Any | None = None,
    analysts: list[Any] | None = None,
    debate_team: Any | None = None,
    risk_manager: Any | None = None,
    portfolio_manager: Any | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the MAS LangGraph state graph.

    Parameters
    ----------
    oracle:
        ``MarketOracle`` instance (or any async object with ``analyze(data)``).
        When ``None``, the oracle node is a no-op.
    analysts:
        List of ``BaseAnalyst`` instances.  When ``None`` or empty, the
        analysts node returns an empty signal list.
    debate_team:
        ``DebateTeam`` instance.  When ``None``, the debate node returns
        ``None``.
    risk_manager:
        ``RiskManager`` instance.  When ``None``, the risk node returns a
        permissive default assessment.
    portfolio_manager:
        ``PortfolioManager`` instance.  When ``None``, the portfolio node
        returns a deterministic HOLD decision.

    Returns
    -------
        A compiled ``StateGraph`` ready for ``.invoke()`` / ``.ainvoke()``.
    """
    graph: StateGraph[Any, Any, Any, Any] = StateGraph(GraphState)

    graph.add_node("oracle", _make_oracle_node(oracle))
    graph.add_node("analysts", _make_analysts_node(analysts))
    graph.add_node("debate", _make_debate_node(debate_team))
    graph.add_node("risk", _make_risk_node(risk_manager))
    graph.add_node("portfolio", _make_portfolio_node(portfolio_manager))

    graph.set_entry_point("oracle")
    graph.add_edge("oracle", "analysts")
    graph.add_edge("analysts", "debate")
    graph.add_conditional_edges(
        "debate", router, {"risk": "risk", "portfolio": "portfolio", END: END}
    )
    graph.add_edge("risk", "portfolio")
    graph.add_edge("portfolio", END)

    return graph.compile()
