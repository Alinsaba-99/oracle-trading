#!/usr/bin/env python3
"""MAS experiment runner — CLI for running the Multi-Agent System pipeline.

Usage:
    python -m experiments.scripts.run_mas --instrument SPY --iterations 5 --output results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


async def _run_mas_experiment(
    instrument: str,
    iterations: int = 1,
    output: str | None = None,
) -> int:
    """Execute *iterations* MAS cycles and optionally persist results."""
    import yfinance as yf

    from agents.analysts import create_analyst
    from agents.config import MASConfig
    from agents.debate import DebateTeam
    from agents.decision import PortfolioManager, RiskManager, SignalScorer
    from agents.llm import FallbackLLMClient, LitellmLLMClient
    from agents.oracle.oracle import MarketOracle
    from agents.orchestrator import (
        MASOrchestrator,
        build_mas_graph,
    )

    config = MASConfig()

    # Setup LLM
    primary = LitellmLLMClient(model=config.primary_model)
    fallback = LitellmLLMClient(model=config.fallback_model)
    llm = FallbackLLMClient([primary, fallback])

    # Build MAS components
    _oracle = MarketOracle(llm_client=llm)
    analysts = [create_analyst(t, llm) for t in config.enabled_agents]
    _debate = DebateTeam(llm)
    risk = RiskManager()
    _portfolio = PortfolioManager(SignalScorer(), risk)

    # Build engine
    from agents.orchestrator.graph_adapter import LangGraphWorkflowEngine

    engine = LangGraphWorkflowEngine(build_mas_graph())
    orchestrator = MASOrchestrator(config=config, engine=engine)

    print(f"MAS experiment: {instrument}, {iterations} iteration(s)")
    print(f"  analysts: {[a.name for a in analysts]}")
    print(f"  debate rounds: {config.debate_rounds}")
    print()

    # Fetch market data once (or per iteration if time-series slicing)
    ticker = yf.Ticker(instrument)
    raw_data = ticker.history(period="12mo")
    if raw_data.empty:
        print(f"No data for {instrument}")
        return 1

    results: list[dict[str, Any]] = []
    for i in range(iterations):
        print(f"Iteration {i + 1}/{iterations}...")
        # Pass a recent slice for each iteration
        data = raw_data.tail(126).to_dict()
        decision = await orchestrator.run(market_data=data, instrument=instrument)
        results.append(
            {
                "iteration": i + 1,
                "instrument": instrument,
                "timestamp": datetime.now(UTC).isoformat(),
                "decision": _serialize(decision),
            }
        )
        print(f"  -> {decision!s}")

    # Report summary
    _report_summary(results)

    # Persist if output path given
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"\nResults saved to {out_path}")

    return 0


def _serialize(obj: Any) -> Any:
    """Convert Pydantic models / complex objects to JSON-safe dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return str(obj)


def _report_summary(results: list[dict[str, Any]]) -> None:
    """Print a summary of all iterations."""
    directions: list[str] = []
    for r in results:
        d = r.get("decision", {})
        if isinstance(d, dict):
            directions.append(d.get("direction", "?"))
        else:
            directions.append(str(d))

    if directions:
        print(f"\nSummary [{len(results)} iteration(s)]:")
        for i, d in enumerate(directions, 1):
            print(f"  iter {i}: {d}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_mas",
        description="Run MAS experiments with configurable iterations",
    )
    parser.add_argument(
        "--instrument", type=str, default="SPY", help="Instrument symbol"
    )
    parser.add_argument(
        "--iterations", type=int, default=5, help="Number of MAS cycles"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output JSON file path"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print per-iteration JSON to stdout",
    )

    args = parser.parse_args()
    sys.exit(asyncio.run(_run_mas_experiment(
        instrument=args.instrument,
        iterations=args.iterations,
        output=args.output,
    )))


if __name__ == "__main__":
    main()
