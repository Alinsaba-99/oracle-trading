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

import numpy as np
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

__all__ = ["GraphState", "build_mas_graph", "router"]


class GraphState(TypedDict):
    """State type used by the LangGraph state graph."""

    instrument: str
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


def _build_agent_specific_data(market_data: Any, market_state: Any) -> dict[str, Any]:
    """Build analyst-ready feature dict from available market data.

    Extracts or computes:
      - technical: recent closes, RSI (14), MACD, SMA(20/50)
      - macro:     placeholder (TODO: GDP, CPI, unemployment integration)
      - sentiment: placeholder (TODO: news / social sentiment integration)

    Returns a non-empty dict even when *market_data* is ``None``,
    falling back to the qualitative *market_state* fields.
    """
    import numpy as np

    technical: dict[str, Any] = {}
    macro: dict[str, Any] = {}
    sentiment: dict[str, Any] = {}

    # ── extract price series ───────────────────────────────────────
    closes: np.ndarray | None = None
    if market_data is not None:
        try:
            if hasattr(market_data, "to_numpy"):
                closes = market_data["close"].to_numpy().flatten()
            elif hasattr(market_data, "__getitem__"):
                closes = np.asarray(market_data["close"], dtype=float)
        except (KeyError, TypeError, ValueError):
            pass

    # ── compute technical indicators ───────────────────────────────
    if closes is not None and len(closes) >= 50:
        technical["recent_closes"] = closes[-20:].tolist()
        technical["close"] = float(closes[-1])
        technical["sma_20"] = float(np.mean(closes[-20:]))
        technical["sma_50"] = float(np.mean(closes[-50:]))
        technical["daily_return"] = (
            float((closes[-1] - closes[-2]) / closes[-2]) if len(closes) >= 2 else 0.0
        )

        # RSI(14) — Wilder's smoothing
        rsi = _compute_rsi(closes, period=14)
        technical["rsi_14"] = float(rsi) if rsi is not None else None

        # MACD(12, 26, 9)
        macd, signal, hist = _compute_macd(closes)
        if macd is not None and signal is not None and hist is not None:
            technical["macd"] = {
                "macd": float(macd),
                "signal": float(signal),
                "histogram": float(hist),
            }
        else:
            technical["macd"] = None

        # volatility
        if len(closes) >= 20:
            log_rets = np.diff(np.log(closes[-20:]))
            technical["volatility_20d"] = float(np.std(log_rets, ddof=1))
    elif closes is not None and len(closes) >= 2:
        # Bare minimum with sparse data
        technical["recent_closes"] = closes.tolist()
        technical["close"] = float(closes[-1])
        if len(closes) >= 2:
            technical["daily_return"] = float((closes[-1] - closes[-2]) / closes[-2])

    # ── macro placeholder ──────────────────────────────────────────
    macro["_placeholder"] = True
    macro["_todo"] = "GDP, CPI, unemployment, yield curve via Fred/FRED API"
    if market_state is not None and hasattr(market_state, "regime"):
        macro["regime"] = market_state.regime

    # ── sentiment placeholder ──────────────────────────────────────
    sentiment["_placeholder"] = True
    sentiment["_todo"] = "NewsAPI, Twitter/X, Fear & Greed index integration"

    return {"technical": technical, "macro": macro, "sentiment": sentiment}


def _compute_rsi(closes: Any, period: int = 14) -> float | None:
    """Compute RSI using Wilder's smoothing method.

    Returns ``None`` when the series is too short.
    """
    import numpy as np

    arr = np.asarray(closes, dtype=float)
    if len(arr) < period + 1:
        return None
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain: float = float(gains[1:period].mean())
    avg_loss: float = float(losses[1:period].mean())
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs: float = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd(closes: Any) -> tuple[float | None, float | None, float | None]:
    """Compute MACD(12,26,9) line, signal line, and histogram.

    Returns three ``None`` values when the series is too short.
    """
    import numpy as np

    arr = np.asarray(closes, dtype=float)
    if len(arr) < 35:  # 26 + 9
        return None, None, None

    def ema(data: np.ndarray, span: int) -> np.ndarray:
        alpha = 2.0 / (span + 1)
        out = np.empty_like(data)
        out[0] = data[0]
        for i in range(1, len(data)):
            out[i] = data[i] * alpha + out[i - 1] * (1 - alpha)
        return out

    ema_12 = ema(arr, 12)
    ema_26 = ema(arr, 26)
    macd_line = ema_12 - ema_26
    signal_line = ema(macd_line, 9)
    histogram = macd_line[-1] - signal_line[-1]
    return float(macd_line[-1]), float(signal_line[-1]), float(histogram)


def _make_analysts_node(analysts: list[Any] | None) -> Any:
    if not analysts:

        def analysts_node_sync(state: GraphState) -> dict[str, Any]:
            existing = state.get("analyst_signals")
            return {} if existing else {"analyst_signals": []}

        return analysts_node_sync

    async def analysts_node(state: GraphState) -> dict[str, Any]:
        market_state = state.get("market_state")
        market_data = state.get("market_data")
        instrument = state.get("instrument", "SPY")
        from agents.protocol import AnalystInput

        # ── compute agent-specific data from available sources ──────────
        agent_specific_data: dict[str, Any] = _build_agent_specific_data(market_data, market_state)

        inputs = AnalystInput(
            instrument=instrument,
            market_state=market_state,
            agent_specific_data=agent_specific_data,
        )

        async def _safe_analyze(analyst: Any) -> Any:
            try:
                return await analyst.analyze(inputs)
            except Exception as exc:
                return {"error": f"{getattr(analyst, 'name', 'analyst')}: {exc}"}

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
            return {"debate": None, "errors": [*state.get("errors", []), f"debate: {exc}"]}

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
        instrument = state.get("instrument", "SPY")
        decision = PortfolioDecision(
            direction=direction,  # type: ignore[arg-type]
            instrument=instrument,
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
            return {"errors": [*state.get("errors", []), f"risk: {exc}"], "risk_assessment": None}

    return risk_node


def _make_portfolio_node(portfolio_manager: Any | None) -> Any:
    if portfolio_manager is None:

        def portfolio_node_sync(state: GraphState) -> dict[str, Any]:
            instrument = state.get("instrument", "SPY")
            return {
                "decision": {
                    "direction": "hold",
                    "instrument": instrument,
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
        instrument = state.get("instrument", "SPY")
        try:
            decision = portfolio_manager.decide(signals, market_state, instrument=instrument)
            return {"decision": decision}
        except Exception as exc:
            return {
                "decision": {
                    "direction": "hold",
                    "instrument": instrument,
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
    if debate is not None:
        consensus = None
        if isinstance(debate, dict):
            consensus = debate.get("consensus")
        elif hasattr(debate, "consensus"):
            consensus = debate.consensus
        if consensus is not None:
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
