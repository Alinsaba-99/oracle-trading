"""Tests for OracleMode and mode guard."""

from __future__ import annotations

import pytest

from core.domain.guard import ModeGuardError, current_mode, guard
from core.domain.mode import VALID_TRANSITIONS, OracleMode, can_transition


class TestOracleMode:
    """OracleMode enum semantics."""

    def test_modes_are_strings(self) -> None:
        assert OracleMode.RESEARCH == "research"
        assert OracleMode.REPLAY == "replay"
        assert OracleMode.PAPER == "paper"
        assert OracleMode.SHADOW == "shadow"
        assert OracleMode.EVALUATION == "evaluation"
        assert OracleMode.FUNDED == "funded"

    def test_mode_order(self) -> None:
        """Modes must progress strictly forward."""
        modes = list(OracleMode)
        assert modes == [
            OracleMode.RESEARCH,
            OracleMode.REPLAY,
            OracleMode.PAPER,
            OracleMode.SHADOW,
            OracleMode.EVALUATION,
            OracleMode.FUNDED,
        ]


class TestTransitions:
    """Mode transition rules."""

    def test_research_to_replay(self) -> None:
        assert can_transition(OracleMode.RESEARCH, OracleMode.REPLAY)

    def test_research_to_paper(self) -> None:
        assert can_transition(OracleMode.RESEARCH, OracleMode.PAPER)

    def test_no_backwards_transition(self) -> None:
        assert not can_transition(OracleMode.FUNDED, OracleMode.RESEARCH)
        assert not can_transition(OracleMode.EVALUATION, OracleMode.PAPER)

    def test_no_skip_transition(self) -> None:
        assert not can_transition(OracleMode.RESEARCH, OracleMode.FUNDED)

    def test_all_transitions_are_defined(self) -> None:
        for mode in OracleMode:
            assert mode in VALID_TRANSITIONS


class TestGuard:
    """Startup guard enforcement."""

    def test_research_default_allowed(self) -> None:
        guard(OracleMode.RESEARCH, env={"ORACLE_MODE": "research"})

    def test_research_no_env(self) -> None:
        guard(OracleMode.RESEARCH, env={})

    def test_paper_requires_api_key(self) -> None:
        with pytest.raises(ModeGuardError, match="ORACLE_PAPER_API_KEY"):
            guard(OracleMode.PAPER, env={"ORACLE_MODE": "paper"})

    def test_paper_with_api_key(self) -> None:
        guard(
            OracleMode.PAPER, env={"ORACLE_MODE": "paper", "ORACLE_PAPER_API_KEY": "test-key-123"}
        )

    def test_evaluation_requires_broker_token(self) -> None:
        with pytest.raises(ModeGuardError, match="ORACLE_EVAL_BROKER_TOKEN"):
            guard(
                OracleMode.EVALUATION,
                env={"ORACLE_MODE": "evaluation", "ORACLE_EVAL_API_KEY": "key"},
            )

    def test_invalid_mode_string(self) -> None:
        with pytest.raises(ModeGuardError, match="Invalid ORACLE_MODE"):
            guard(OracleMode.RESEARCH, env={"ORACLE_MODE": "invalid"})

    def test_invalid_transition(self) -> None:
        with pytest.raises(ModeGuardError, match="Invalid mode transition"):
            guard(
                OracleMode.FUNDED, env={"ORACLE_MODE": "funded"}, previous_mode=OracleMode.RESEARCH
            )

    def test_valid_transition(self) -> None:
        guard(
            OracleMode.PAPER,
            env={"ORACLE_MODE": "paper", "ORACLE_PAPER_API_KEY": "key"},
            previous_mode=OracleMode.RESEARCH,
        )


class TestCurrentMode:
    """Mode detection from environment."""

    def test_default_research(self) -> None:
        assert current_mode({}) == OracleMode.RESEARCH

    def test_explicit_mode(self) -> None:
        assert current_mode({"ORACLE_MODE": "paper"}) == OracleMode.PAPER

    def test_invalid_fallback_research(self) -> None:
        assert current_mode({"ORACLE_MODE": "invalid"}) == OracleMode.RESEARCH
