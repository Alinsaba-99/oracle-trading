"""Tests for the MAS Orchestrator — graph, adapter, lifecycle, runner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from agents.orchestrator import (
    LangGraphWorkflowEngine,
    MASOrchestrator,
    MASRunner,
    StateManager,
    WorkflowEngine,
    build_mas_graph,
)
from agents.orchestrator.graph import GraphState, router

# =========================================================================
# StateManager
# =========================================================================


class TestStateManager:
    def test_initial_creates_valid_state(self) -> None:
        state = StateManager.initial()
        assert isinstance(state, dict)
        assert state["market_data"] is None
        assert state["market_state"] is None
        assert state["analyst_signals"] == []
        assert state["debate"] is None
        assert state["risk_assessment"] is None
        assert state["decision"] is None
        assert state["errors"] == []
        assert isinstance(state["run_id"], str)
        assert len(state["run_id"]) > 0
        assert state["total_tokens"] == 0
        assert state["timing"] == {}

    def test_initial_with_custom_instrument(self) -> None:
        state = StateManager.initial(instrument="QQQ")
        assert state["market_data"] is None

    def test_initial_each_call_unique_run_id(self) -> None:
        s1 = StateManager.initial()
        s2 = StateManager.initial()
        assert s1["run_id"] != s2["run_id"]


# =========================================================================
# Graph builder
# =========================================================================


class TestBuildMasGraph:
    def test_compiles_without_errors(self) -> None:
        app = build_mas_graph()
        assert app is not None
        assert hasattr(app, "invoke")
        assert hasattr(app, "ainvoke")

    def test_runs_end_to_end(self) -> None:
        app = build_mas_graph()
        result = app.invoke(StateManager.initial())
        assert isinstance(result, dict)
        for key in (
            "market_data",
            "market_state",
            "analyst_signals",
            "debate",
            "risk_assessment",
            "decision",
            "errors",
            "run_id",
            "total_tokens",
            "timing",
        ):
            assert key in result, f"Missing key: {key}"

    def test_result_contains_decision(self) -> None:
        app = build_mas_graph()
        result = app.invoke(StateManager.initial())
        assert result["decision"] is not None
        assert result["decision"]["direction"] == "hold"

    def test_risk_assessment_fail_closed_without_risk_manager(self) -> None:
        """Risk node is only reached when the debate produces consensus.

        P0 security fix (C3): a graph built without a risk manager must be
        fail-closed — the assessment is populated but NEVER approved.
        """
        app = build_mas_graph()
        state = StateManager.initial()
        state["debate"] = {"consensus": {"direction": "buy"}}
        result = app.invoke(state)
        assert result["risk_assessment"] is not None
        assert result["risk_assessment"]["approved"] is False
        assert result["risk_assessment"]["max_position_size"] == 0.0
        assert result["risk_assessment"]["reasons"]  # explicit fail-closed reason
        assert result["decision"] is not None

    def test_risk_assessment_uses_real_risk_manager(self) -> None:
        """With a configured RiskManager the assessment comes from the gate.

        The real risk node is async, so the graph is invoked via ainvoke.
        The assessment is a ``RiskAssessment`` model (not the stub dict).
        """
        from agents.decision import RiskManager
        from agents.protocol import RiskAssessment

        app = build_mas_graph(risk_manager=RiskManager())
        state = StateManager.initial()
        state["debate"] = {"consensus": {"direction": "buy", "confidence": 0.8}}
        result = asyncio.run(app.ainvoke(state))
        assessment = result["risk_assessment"]
        assert assessment is not None
        assert isinstance(assessment, RiskAssessment)
        assert isinstance(assessment.approved, bool)
        assert assessment.max_position_size == 0.25

    def test_empty_data_does_not_crash(self) -> None:
        app = build_mas_graph()
        state = StateManager.initial()
        state["market_data"] = None
        result = app.invoke(state)
        assert result["decision"] is not None

    def test_async_invoke(self) -> None:
        """Graph can be invoked asynchronously via ainvoke."""
        app = build_mas_graph()
        result = asyncio.run(app.ainvoke(StateManager.initial()))
        assert isinstance(result, dict)
        assert result["decision"] is not None

    # ==============================================================
    # Router unit tests
    # ==============================================================

    def test_router_defaults_to_portfolio(self) -> None:
        state: GraphState = {
            "instrument": "SPY",
            "market_data": None,
            "market_state": None,
            "analyst_signals": [],
            "debate": None,
            "risk_assessment": None,
            "decision": None,
            "errors": [],
            "run_id": "test",
            "total_tokens": 0,
            "timing": {},
        }
        assert router(state) == "portfolio"

    def test_router_routes_to_risk_on_consensus(self) -> None:
        state: GraphState = {
            "instrument": "SPY",
            "market_data": None,
            "market_state": None,
            "analyst_signals": [],
            "debate": {"consensus": {"direction": "buy"}},
            "risk_assessment": None,
            "decision": None,
            "errors": [],
            "run_id": "test",
            "total_tokens": 0,
            "timing": {},
        }
        assert router(state) == "risk"

    def test_router_ends_on_critical_error(self) -> None:
        state: GraphState = {
            "instrument": "SPY",
            "market_data": None,
            "market_state": None,
            "analyst_signals": [],
            "debate": None,
            "risk_assessment": None,
            "decision": None,
            "errors": ["critical: oracle unavailable"],
            "run_id": "test",
            "total_tokens": 0,
            "timing": {},
        }
        assert router(state) == "__end__"


# =========================================================================
# WorkflowEngine protocol + adapter
# =========================================================================


class TestWorkflowEngine:
    def test_langgraph_adapter_wraps_compiled_graph(self) -> None:
        app = build_mas_graph()
        engine = LangGraphWorkflowEngine(app)
        assert isinstance(engine, WorkflowEngine)

    def test_langgraph_adapter_runs(self) -> None:
        app = build_mas_graph()
        engine = LangGraphWorkflowEngine(app)
        result = asyncio.run(engine.run(StateManager.initial()))
        assert isinstance(result, dict)
        assert result["decision"] is not None


# =========================================================================
# MASOrchestrator
# =========================================================================


class TestMASOrchestrator:
    async def test_run_without_engine_returns_none(self) -> None:
        """Orchestrator with no engine returns None decision."""
        orch = MASOrchestrator(config=None, engine=None)
        decision = await orch.run(market_data=None)
        assert decision is None

    async def test_run_with_mock_engine(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {
            "decision": {
                "direction": "buy",
                "instrument": "SPY",
                "position_size": 100.0,
                "confidence": 0.85,
                "reasoning": "Strong signals.",
                "agents_contributing": ["macro"],
                "regime_at_decision": "bull",
                "risk_approved": True,
                "escalated": False,
            }
        }

        orch = MASOrchestrator(engine=mock_engine)
        decision = await orch.run(market_data="mock", instrument="SPY")
        assert decision is not None
        assert decision["direction"] == "buy"
        assert decision["position_size"] == 100.0

    async def test_run_submits_order_when_bridge_and_manager_present(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {
            "decision": {
                "direction": "buy",
                "instrument": "SPY",
                "position_size": 1.5,
                "confidence": 0.85,
                "reasoning": "Strong signals.",
                "agents_contributing": ["macro"],
                "regime_at_decision": "bull",
                "risk_approved": True,
                "escalated": False,
            }
        }
        mock_bridge = MagicMock()
        mock_request = MagicMock()
        mock_bridge.to_order_request.return_value = mock_request
        mock_manager = MagicMock()
        mock_manager.submit = AsyncMock(return_value={"status": "submitted"})

        orch = MASOrchestrator(engine=mock_engine, bridge=mock_bridge, order_manager=mock_manager)
        decision = await orch.run(market_data="mock", instrument="SPY")

        assert decision is not None
        mock_bridge.to_order_request.assert_called_once()
        mock_manager.submit.assert_awaited_once_with(mock_request)
        assert orch.last_order_request is mock_request
        assert orch.last_order_result == {"status": "submitted"}
        assert orch.last_result is not None
        assert orch.last_result["order_result"] == {"status": "submitted"}

    async def test_run_does_not_submit_hold_decision(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {
            "decision": {
                "direction": "hold",
                "instrument": "SPY",
                "position_size": 0.0,
                "confidence": 0.2,
                "reasoning": "No edge.",
                "agents_contributing": ["macro"],
                "regime_at_decision": "neutral",
                "risk_approved": True,
                "escalated": False,
            }
        }
        mock_bridge = MagicMock()
        mock_bridge.to_order_request.return_value = None
        mock_manager = MagicMock()
        mock_manager.submit = AsyncMock()

        orch = MASOrchestrator(engine=mock_engine, bridge=mock_bridge, order_manager=mock_manager)
        decision = await orch.run(market_data="mock", instrument="SPY")

        assert decision is not None
        mock_bridge.to_order_request.assert_called_once()
        mock_manager.submit.assert_not_awaited()
        assert orch.last_order_request is None
        assert orch.last_order_result is None
        assert orch.last_result is not None
        assert "order_result" not in orch.last_result

    async def test_last_result_property(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {"decision": "mock_decision"}

        orch = MASOrchestrator(engine=mock_engine)
        assert orch.last_result is None  # never run
        await orch.run(market_data="data")
        assert orch.last_result == {"decision": "mock_decision"}


# =========================================================================
# MASRunner
# =========================================================================


class TestMASRunner:
    async def test_run_once_delegates_to_orchestrator(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {"decision": {"direction": "sell"}}
        orch = MASOrchestrator(engine=mock_engine)
        runner = MASRunner(orchestrator=orch)

        decision = await runner.run_once(instrument="SPY", data="market_data")
        assert decision is not None
        assert decision["direction"] == "sell"

    async def test_run_once_without_data(self) -> None:
        mock_engine = AsyncMock(spec=WorkflowEngine)
        mock_engine.run.return_value = {"decision": None}
        orch = MASOrchestrator(engine=mock_engine)
        runner = MASRunner(orchestrator=orch)

        decision = await runner.run_once()
        assert decision is None
