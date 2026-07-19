"""Tests for RBAC authorization."""

from __future__ import annotations

import os

import pytest

from core.auth import (
    AuthorizationError,
    Role,
    authorize,
    require_role,
)


class TestAuthorization:
    """RBAC authorization tests."""

    def test_admin_has_full_access(self) -> None:
        """Admin role can access any resource."""
        os.environ["ORACLE_API_KEY"] = "admin-key"
        role = authorize("admin-key", "orders", "write")
        assert role == Role.ADMIN

    def test_readonly_cannot_write(self) -> None:
        """Readonly role cannot write."""
        os.environ["ORACLE_API_KEY"] = "readonly-key"
        os.environ["ORACLE_API_KEY_ROLE_READONLY"] = "readonly"
        os.environ["ORACLE_API_KEY_READONLY"] = "readonly-key"

        # Reading is fine
        role = authorize("readonly-key", "performance", "read")
        assert role == Role.READONLY

        # Writing should fail
        with pytest.raises(AuthorizationError):
            authorize("readonly-key", "orders", "write")

    def test_operator_can_trade(self) -> None:
        """Operator can manage orders."""
        os.environ["ORACLE_API_KEY"] = "op-key"
        os.environ["ORACLE_API_KEY_ROLE_OP"] = "operator"
        os.environ["ORACLE_API_KEY_OP"] = "op-key"

        role = authorize("op-key", "orders", "write")
        assert role == Role.OPERATOR

        # But cannot manage accounts
        with pytest.raises(AuthorizationError):
            authorize("op-key", "admin", "execute")

    def test_emergency_can_kill(self) -> None:
        """Emergency role can execute kill switch."""
        os.environ["ORACLE_API_KEY"] = "emergency-key"
        os.environ["ORACLE_API_KEY_ROLE_EMERGENCY"] = "emergency"
        os.environ["ORACLE_API_KEY_EMERGENCY"] = "emergency-key"

        role = authorize("emergency-key", "kill", "execute")
        assert role == Role.EMERGENCY

        # But cannot trade
        with pytest.raises(AuthorizationError):
            authorize("emergency-key", "orders", "write")

    def test_unknown_key_raises(self) -> None:
        """Unknown API key raises AuthorizationError."""
        with pytest.raises(AuthorizationError):
            authorize("nonexistent-key", "health", "read")

    def test_empty_key_raises(self) -> None:
        """Empty API key raises AuthorizationError."""
        with pytest.raises(AuthorizationError):
            authorize("", "health", "read")

    def test_require_role_admin(self) -> None:
        """require_role checks minimum role level."""
        os.environ["ORACLE_API_KEY"] = "admin-key-2"
        role = require_role("admin-key-2", Role.OPERATOR)
        assert role == Role.ADMIN

    def test_require_role_insufficient(self) -> None:
        """require_role fails if role is too low."""
        os.environ["ORACLE_API_KEY"] = "low-key"
        os.environ["ORACLE_API_KEY_ROLE_LOW"] = "readonly"
        os.environ["ORACLE_API_KEY_LOW"] = "low-key"

        with pytest.raises(AuthorizationError, match="readonly.*operator"):
            require_role("low-key", Role.OPERATOR)
