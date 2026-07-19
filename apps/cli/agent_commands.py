"""MAS CLI command handlers — agent run, debate, and status commands."""

from __future__ import annotations

import argparse
from typing import Any


def _setup_mas(_args: argparse.Namespace | None = None) -> dict[str, Any]:
    """Import MAS components, build config and LLM, return assembled pieces.

    This factored setup is shared by ``handle_agent_run`` and
    ``handle_agent_debate`` so they don't duplicate the import / wiring.
    """
    from agents.analysts import create_analyst
    from agents.config import MASConfig
    from agents.debate import DebateTeam
    from agents.decision import PortfolioManager, RiskManager, SignalScorer
    from agents.llm import FallbackLLMClient, LitellmLLMClient
    from agents.oracle.oracle import MarketOracle
    from agents.orchestrator import LangGraphWorkflowEngine, MASOrchestrator, build_mas_graph

    config = MASConfig()

    # Setup LLM with primary/fallback chain
    primary = LitellmLLMClient(model=config.primary_model)
    fallback = LitellmLLMClient(model=config.fallback_model)
    llm = FallbackLLMClient([primary, fallback])

    # Build MAS components
    oracle = MarketOracle(llm_client=llm)
    analysts = [create_analyst(t, llm) for t in config.enabled_agents]
    debate = DebateTeam(llm)
    risk = RiskManager()
    portfolio = PortfolioManager(SignalScorer(), risk)

    # Build LangGraph engine with real components and orchestrator
    engine = LangGraphWorkflowEngine(
        build_mas_graph(
            oracle=oracle,
            analysts=analysts,
            debate_team=debate,
            risk_manager=risk,
            portfolio_manager=portfolio,
        )
    )
    orchestrator = MASOrchestrator(config=config, engine=engine)

    return {
        "config": config,
        "llm": llm,
        "oracle": oracle,
        "analysts": analysts,
        "debate": debate,
        "portfolio": portfolio,
        "engine": engine,
        "orchestrator": orchestrator,
    }


def _format_output(result: Any, instrument: str, fmt: str, verbose: bool = False) -> str:
    """Format a MAS result for display (json / table / standard)."""
    import json

    if fmt == "json":
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(), indent=2, default=str)
        return json.dumps(result, indent=2, default=str)

    if fmt == "table":
        return _format_table(result, instrument)

    # Standard text output
    lines: list[str] = [f"=== MAS Result [{instrument}] ==="]
    if isinstance(result, dict):
        for k, v in result.items():
            lines.append(f"  {k}: {v}")
    else:
        lines.append(f"  {result!s}")
    if verbose:
        lines.append("  (verbose mode enabled)")
    return "\n".join(lines)


def _format_table(result: Any, instrument: str) -> str:
    """Simple text table for signal / decision display."""
    try:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return _format_output(result, instrument, "standard")

    buf = StringIO()
    console = Console(width=100, file=buf, force_terminal=False)
    table = Table(title=f"MAS Analysis \u2014 {instrument}")

    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    if isinstance(result, dict):
        for k, v in result.items():
            table.add_row(str(k), str(v))
    else:
        table.add_row("decision", str(result))

    console.print(table)
    return buf.getvalue()


async def handle_agent_run(args: argparse.Namespace) -> int:
    """Run a full MAS analysis pipeline: oracle -> analysts -> debate -> decision.

    Returns 0 on success, 1 on failure.
    """
    instrument: str = args.instrument
    fmt: str = "json" if args.json else "table" if args.table else "standard"

    try:
        mas = _setup_mas(args)
    except Exception as exc:
        import sys as _sys

        print(f"Failed to initialise MAS: {exc}", file=_sys.stderr)
        return 1

    config = mas["config"]
    analysts = mas["analysts"]

    print(f"MAS ready: {len(analysts)} analysts, debate={config.debate_rounds} rounds")
    print("  oracle+analysts+debate+risk+portfolio pipeline")
    print(f"  Instrument: {instrument}")
    print(f"  Output mode: {fmt}")

    # Fetch market data
    _data = _fetch_market_data(instrument)

    # Run the pipeline
    orchestrator = mas["orchestrator"]
    decision = await orchestrator.run(market_data=_data, instrument=instrument)

    if decision is not None:
        print(_format_output(decision, instrument, fmt, verbose=args.verbose))
    else:
        print("No decision returned from MAS pipeline.")

    return 0


async def handle_agent_debate(args: argparse.Namespace) -> int:
    """Run debate-only analysis (skip full pipeline).

    Useful for inspecting how analysts debate without executing trades.
    """
    instrument: str = args.instrument

    try:
        mas = _setup_mas(args)
    except Exception as exc:
        import sys as _sys

        print(f"Failed to initialise MAS: {exc}", file=_sys.stderr)
        return 1

    debate = mas["debate"]
    analysts = mas["analysts"]

    print(f"Debate-only mode [{instrument}]")
    print(f"  {len(analysts)} analysts, {mas['config'].debate_rounds} debate rounds")

    _data = _fetch_market_data(instrument)

    # Collect analyst signals first
    from agents.protocol import AnalystInput

    dummy_state: dict[str, str] = {"regime": "unknown"}
    signals_raw: list[Any] = []
    for analyst in analysts:
        inp = AnalystInput(instrument=instrument, market_state=dummy_state, agent_specific_data={})
        signal = await analyst.analyze(inp)
        signals_raw.append(signal)
        print(f"  [{analyst.name}] {signal.vote.direction} ({signal.vote.confidence:.2f})")

    # Run debate
    result = await debate.debate(signals_raw)
    from agents.protocol import DebateResult

    if isinstance(result, DebateResult):
        print(f"\nDebate consensus: {result.consensus}")
        if result.disagreements:
            for d in result.disagreements:
                print(f"  disagreement: {d}")
        print(f"  quality score: {result.debate_quality:.3f}")
    else:
        print(f"\nDebate result: {result!s}")

    return 0


def handle_agent_status(args: argparse.Namespace) -> int:
    """Show configured MAS agents and their runtime status."""
    from agents.analysts.factory import list_analysts

    _ = args  # unused (kept for consistent handler signature)
    registered = list_analysts()

    print(f"Registered analyst types ({len(registered)}):")
    for name in registered:
        print(f"  - {name}")

    try:
        from agents.config import MASConfig

        config = MASConfig()
        enabled = config.enabled_agents
        print(f"\nEnabled analysts ({len(enabled)}):")
        for name in enabled:
            status = "registered" if name in registered else "NOT REGISTERED"
            print(f"  - {name} [{status}]")
        print(f"\nDebate rounds: {config.debate_rounds}")
        print(f"Primary LLM:   {config.primary_model}")
        print(f"Fallback LLM:  {config.fallback_model}")
    except Exception as exc:
        import sys as _sys

        print(f"  (config unavailable: {exc})", file=_sys.stderr)

    return 0


def _fetch_market_data(instrument: str) -> dict[str, object] | None:
    """Fetch market data for the given instrument.

    Returns ``None`` when data is unavailable (the pipeline handles it).
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(instrument)
        hist = ticker.history(period="6mo")
        if hist.empty:
            return None
        # Return a lightweight dict representation
        return {
            "instrument": instrument,
            "close": hist["Close"].tolist(),
            "volume": hist["Volume"].tolist(),
            "high": hist["High"].tolist(),
            "low": hist["Low"].tolist(),
            "dates": [str(d.date()) for d in hist.index],
        }
    except ImportError:
        return None
    except Exception:
        return None
