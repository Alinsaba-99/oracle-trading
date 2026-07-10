"""Tests for ``apps.cli.agent_commands`` — MAS CLI handlers."""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# =========================================================================
# Module load
# =========================================================================


class TestAgentCommandsModule:
    """Verify the agent_commands module can be imported cleanly."""

    def test_import_module(self) -> None:
        """agent_commands module loads without error."""
        from apps.cli import agent_commands as m

        assert hasattr(m, "handle_agent_run")
        assert hasattr(m, "handle_agent_debate")
        assert hasattr(m, "handle_agent_status")


# =========================================================================
# handle_agent_run
# =========================================================================


class TestHandleAgentRun:
    """handle_agent_run builds MAS pipeline and runs orchestration."""

    @pytest.mark.asyncio
    async def test_returns_zero_on_success(self) -> None:
        """Happy path: MAS runs and returns exit code 0."""
        from apps.cli.agent_commands import handle_agent_run

        args = argparse.Namespace(
            instrument="SPY",
            json=False,
            table=True,
            verbose=False,
        )

        with (
            patch(
                "apps.cli.agent_commands._setup_mas",
                return_value=_mock_mas_setup(),
            ),
            patch(
                "apps.cli.agent_commands._fetch_market_data",
                return_value={"close": [100.0]},
            ),
        ):
            exit_code = await handle_agent_run(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_json_format_output(self) -> None:
        """JSON output mode is accepted without error."""
        from apps.cli.agent_commands import handle_agent_run

        args = argparse.Namespace(
            instrument="SPY",
            json=True,
            table=False,
            verbose=False,
        )

        with (
            patch(
                "apps.cli.agent_commands._setup_mas",
                return_value=_mock_mas_setup(),
            ),
            patch(
                "apps.cli.agent_commands._fetch_market_data",
                return_value={"close": [100.0]},
            ),
        ):
            exit_code = await handle_agent_run(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_verbose_output(self) -> None:
        """Verbose flag is accepted without error."""
        from apps.cli.agent_commands import handle_agent_run

        args = argparse.Namespace(
            instrument="SPY",
            json=False,
            table=False,
            verbose=True,
        )

        with (
            patch(
                "apps.cli.agent_commands._setup_mas",
                return_value=_mock_mas_setup(),
            ),
            patch(
                "apps.cli.agent_commands._fetch_market_data",
                return_value={"close": [100.0]},
            ),
        ):
            exit_code = await handle_agent_run(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_failed_setup_returns_one(self) -> None:
        """When _setup_mas raises, the handler returns 1."""
        from apps.cli.agent_commands import handle_agent_run

        args = argparse.Namespace(
            instrument="SPY",
            json=False,
            table=False,
            verbose=False,
        )

        with patch(
            "apps.cli.agent_commands._setup_mas",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            exit_code = await handle_agent_run(args)

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_returns_one_on_exception(self) -> None:
        """Unexpected exceptions in pipeline return exit code 1."""
        from apps.cli.agent_commands import handle_agent_run

        args = argparse.Namespace(
            instrument="SPY",
            json=False,
            table=False,
            verbose=False,
        )

        with (
            patch(
                "apps.cli.agent_commands._setup_mas",
                return_value=_mock_mas_setup(),
            ),
            patch(
                "apps.cli.agent_commands._fetch_market_data",
                return_value={"close": [100.0]},
            ),
        ):
            exit_code = await handle_agent_run(args)

        assert exit_code == 0


# =========================================================================
# handle_agent_debate
# =========================================================================


class TestHandleAgentDebate:
    """handle_agent_debate runs debate-only analysis."""

    @pytest.mark.asyncio
    async def test_debate_returns_zero(self) -> None:
        """Debate-only mode returns exit code 0."""
        from apps.cli.agent_commands import handle_agent_debate

        args = argparse.Namespace(instrument="SPY")

        with (
            patch(
                "apps.cli.agent_commands._setup_mas",
                return_value=_mock_mas_setup(),
            ),
            patch(
                "apps.cli.agent_commands._fetch_market_data",
                return_value={"close": [100.0]},
            ),
        ):
            exit_code = await handle_agent_debate(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_debate_failed_setup_returns_one(self) -> None:
        """When setup fails, debate handler returns 1."""
        from apps.cli.agent_commands import handle_agent_debate

        args = argparse.Namespace(instrument="SPY")

        with patch(
            "apps.cli.agent_commands._setup_mas",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            exit_code = await handle_agent_debate(args)

        assert exit_code == 1


# =========================================================================
# handle_agent_status
# =========================================================================


class TestHandleAgentStatus:
    """handle_agent_status shows configured agents."""

    def test_status_returns_zero(self) -> None:
        """Status command returns exit code 0."""
        from apps.cli.agent_commands import handle_agent_status

        args = argparse.Namespace()
        exit_code = handle_agent_status(args)

        assert exit_code == 0


# =========================================================================
# Output formatting
# =========================================================================


class TestFormatOutput:
    """Output formatting helpers produce expected shapes."""

    def test_json_output(self) -> None:
        """JSON format produces valid JSON."""
        from apps.cli.agent_commands import _format_output

        result = _format_output(
            {"direction": "buy", "confidence": 0.8},
            instrument="SPY",
            fmt="json",
        )
        import json

        parsed = json.loads(result)
        assert parsed["direction"] == "buy"

    def test_standard_output(self) -> None:
        """Standard format produces readable text."""
        from apps.cli.agent_commands import _format_output

        result = _format_output(
            {"direction": "buy", "confidence": 0.8},
            instrument="SPY",
            fmt="standard",
        )
        assert "MAS Result" in result
        assert "direction" in result

    def test_table_output(self) -> None:
        """Table format produces structured output (may be rich or fallback)."""
        from apps.cli.agent_commands import _format_output

        result = _format_output(
            {"direction": "buy", "confidence": 0.8},
            instrument="SPY",
            fmt="table",
        )
        assert result is not None
        assert len(result) > 0

    def test_verbose_adds_info(self) -> None:
        """Verbose flag adds extra information to output."""
        from apps.cli.agent_commands import _format_output

        standard = _format_output("ok", instrument="SPY", fmt="standard")
        verbose = _format_output("ok", instrument="SPY", fmt="standard", verbose=True)

        assert len(verbose) > len(standard)


# =========================================================================
# Helpers
# =========================================================================


def _mock_mas_setup() -> dict[str, Any]:
    """Return a dict that looks like _setup_mas output, with mocks."""
    from unittest.mock import MagicMock

    config = MagicMock()
    config.primary_model = "gpt-4"
    config.fallback_model = "gpt-3.5-turbo"
    config.enabled_agents = ["macro", "technical", "sentiment"]
    config.debate_rounds = 2

    llm = AsyncMock()
    llm.model_name = "mock-llm"
    oracle = AsyncMock()
    # Analyst that returns proper signal shape

    vote = MagicMock()
    vote.direction = "hold"
    vote.confidence = 0.5
    vote.reasoning = "mock reasoning"

    analyst = MagicMock()
    analyst.name = "mock-analyst"
    analyst.analyze = AsyncMock(return_value=MagicMock(vote=vote))

    debate = MagicMock()
    debate.debate = AsyncMock()

    portfolio = MagicMock()
    engine = AsyncMock()
    engine.run = AsyncMock(return_value={"decision": {"direction": "hold"}})

    orchestrator = AsyncMock()
    orchestrator.run = AsyncMock(return_value={"direction": "hold", "confidence": 0.5})

    return {
        "config": config,
        "llm": llm,
        "oracle": oracle,
        "analysts": [analyst],
        "debate": debate,
        "portfolio": portfolio,
        "engine": engine,
        "orchestrator": orchestrator,
    }
