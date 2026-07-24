"""Tests for cross-environment credential isolation and mode wiring."""

from __future__ import annotations

import pytest

from core.domain.guard import ModeGuardError, check_credential_isolation, current_mode, guard
from core.domain.mode import OracleMode


class TestCredentialIsolation:
    """Credentials from higher-authority modes must not leak into lower modes."""

    def test_paper_without_funded_creds_ok(self) -> None:
        """Paper mode without funded credentials should pass."""
        violations = check_credential_isolation(
            {"ORACLE_MODE": "paper", "ORACLE_FUNDED_API_KEY": ""}
        )
        assert violations == []

    def test_paper_with_funded_creds_fails(self) -> None:
        """Paper mode with funded credentials should flag violation."""
        violations = check_credential_isolation(
            {"ORACLE_MODE": "paper", "ORACLE_FUNDED_API_KEY": "should-not-be-here"}
        )
        assert len(violations) == 1
        assert "ORACLE_FUNDED_API_KEY" in violations[0]
        assert "paper" in violations[0]

    def test_shadow_with_funded_creds_fails(self) -> None:
        violations = check_credential_isolation(
            {
                "ORACLE_MODE": "shadow",
                "ORACLE_FUNDED_API_KEY": "leaked",
                "ORACLE_FUNDED_BROKER_TOKEN": "leaked",
            }
        )
        assert len(violations) == 2

    def test_funded_mode_has_no_forbidden_creds(self) -> None:
        """Funded mode should not forbid any credentials."""
        violations = check_credential_isolation(
            {
                "ORACLE_MODE": "funded",
                "ORACLE_FUNDED_API_KEY": "key",
                "ORACLE_FUNDED_BROKER_TOKEN": "token",
            }
        )
        assert violations == []

    def test_research_has_no_restrictions(self) -> None:
        violations = check_credential_isolation(
            {"ORACLE_MODE": "research", "ORACLE_FUNDED_API_KEY": "whatever"}
        )
        assert violations == []

    def test_evaluation_with_funded_fails(self) -> None:
        violations = check_credential_isolation(
            {"ORACLE_MODE": "evaluation", "ORACLE_FUNDED_BROKER_TOKEN": "leaked"}
        )
        assert len(violations) == 1


class TestModeWiringCLI:
    """CLI entry point enforces mode guard."""

    def test_cli_research_default(self) -> None:
        """Research mode should work without ORACLE_MODE."""
        guard(OracleMode.RESEARCH, env={})

    def test_cli_paper_requires_key(self) -> None:
        """Paper mode in CLI should require API key."""
        with pytest.raises(ModeGuardError, match="ORACLE_PAPER_API_KEY"):
            guard(OracleMode.PAPER, env={"ORACLE_MODE": "paper"})

    def test_cli_funded_blocked(self) -> None:
        """Funded mode in CLI should require broker token."""
        with pytest.raises(ModeGuardError, match="ORACLE_FUNDED_BROKER_TOKEN"):
            guard(OracleMode.FUNDED, env={"ORACLE_MODE": "funded", "ORACLE_FUNDED_API_KEY": "key"})


class TestModeWiringAPI:
    """API entry point enforces mode guard + production fail-closed."""

    def test_api_research_allowed(self) -> None:
        """Research mode should start without credentials."""
        import os
        import subprocess

        result = subprocess.run(
            ["uv", "run", "--frozen", "python", "-c", "from apps.api.main import app; print('ok')"],
            capture_output=True,
            text=True,
            cwd="/home/alin/_repos/oracle-trading",
            env={"ORACLE_MODE": "research", "PATH": os.environ.get("PATH", "")},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_api_funded_blocked_without_creds(self) -> None:
        """Funded mode API should refuse to start without broker token."""
        import os
        import subprocess

        result = subprocess.run(
            ["uv", "run", "--frozen", "python", "-c", "from apps.api.main import app; print('ok')"],
            capture_output=True,
            text=True,
            cwd="/home/alin/_repos/oracle-trading",
            env={"ORACLE_MODE": "funded", "PATH": os.environ.get("PATH", "")},
        )
        assert result.returncode != 0
        assert "ORACLE_FUNDED_BROKER_TOKEN" in result.stderr


class TestModeDetection:
    """Current mode detection from environment."""

    def test_oracle_mode_research(self) -> None:
        assert current_mode({"ORACLE_MODE": "research"}) == OracleMode.RESEARCH

    def test_oracle_mode_paper(self) -> None:
        assert current_mode({"ORACLE_MODE": "paper"}) == OracleMode.PAPER

    def test_oracle_mode_funded_with_prefix(self) -> None:
        """Mode with prefix env vars should set correct mode."""
        mode = current_mode(
            {
                "ORACLE_MODE": "evaluation",
                "ORACLE_EVAL_API_KEY": "test-key",
                "ORACLE_EVAL_BROKER_TOKEN": "test-token",
            }
        )
        assert mode == OracleMode.EVALUATION
