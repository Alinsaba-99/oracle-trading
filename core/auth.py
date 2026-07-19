"""API Role-Based Access Control (RBAC) — scope-based authorization.

Defines roles and permissions for API endpoints.
Every API request must carry an API key that maps to a role.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    """Pre-defined roles with increasing authority."""

    READONLY = "readonly"
    """Can read data only. No trade operations."""

    RESEARCH = "research"
    """Can run analyses and backtests. No orders."""

    OPERATOR = "operator"
    """Can manage orders and positions. No account management."""

    ADMIN = "admin"
    """Full access including account management."""

    EMERGENCY = "emergency"
    """Can execute kill switch and flatten operations."""


@dataclass(frozen=True)
class Permission:
    """A single permission: resource + action."""

    resource: str
    action: str  # read, write, execute, admin


# ── Permission sets per role ────────────────────────────────────────

ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.READONLY: [
        Permission("performance", "read"),
        Permission("positions", "read"),
        Permission("trades", "read"),
        Permission("ga_runs", "read"),
        Permission("health", "read"),
    ],
    Role.RESEARCH: [
        Permission("performance", "read"),
        Permission("positions", "read"),
        Permission("trades", "read"),
        Permission("ga_runs", "read"),
        Permission("ga_runs", "write"),
        Permission("backtest", "write"),
        Permission("health", "read"),
    ],
    Role.OPERATOR: [
        Permission("performance", "read"),
        Permission("positions", "read"),
        Permission("positions", "write"),
        Permission("trades", "read"),
        Permission("trades", "write"),
        Permission("orders", "read"),
        Permission("orders", "write"),
        Permission("ga_runs", "read"),
        Permission("health", "read"),
    ],
    Role.ADMIN: [
        Permission("*", "*"),  # Full access
    ],
    Role.EMERGENCY: [
        Permission("kill", "execute"),
        Permission("positions", "read"),
        Permission("health", "read"),
    ],
}

# ── API key → role mapping ──────────────────────────────────────────
# In production, this should come from a secrets manager or database.
# For development, it's configured via environment variables.

# Format: ORACLE_API_KEY_ROLE_keyname=role
# Prefix: ORACLE_API_KEY_ROLE_
# Example: ORACLE_API_KEY_ROLE_ALICE=operator


def _parse_api_key_roles() -> dict[str, Role]:
    """Parse API key roles from environment variables."""
    roles: dict[str, Role] = {}
    prefix = "ORACLE_API_KEY_ROLE_"

    # The primary API key defaults to admin
    primary_key = os.environ.get("ORACLE_API_KEY", "")
    if primary_key:
        roles[primary_key] = Role.ADMIN

    # Additional keys with specific roles
    for env_var, value in os.environ.items():
        if env_var.startswith(prefix):
            key_name = env_var[len(prefix):].lower()
            try:
                role = Role(value.lower())
                # The actual key value is stored in another env var
                key_value = os.environ.get(f"ORACLE_API_KEY_{key_name.upper()}", "")
                if key_value:
                    roles[key_value] = role
            except ValueError:
                continue

    return roles


# ── Authorization check ─────────────────────────────────────────────


class AuthorizationError(PermissionError):
    """Raised when an API request lacks required permissions."""


def authorize(api_key: str, resource: str, action: str) -> Role:
    """Check if an API key is authorized for a resource+action.

    Args:
        api_key: The API key from the request header.
        resource: The resource being accessed.
        action: The action being performed.

    Returns:
        The role that authorized this request.

    Raises:
        AuthorizationError: If the key is unknown or lacks permission.
    """
    roles = _parse_api_key_roles()

    if not api_key or api_key not in roles:
        raise AuthorizationError("Unknown or missing API key")

    role = roles[api_key]
    permissions = ROLE_PERMISSIONS.get(role, [])

    # Admin has wildcard access
    if role == Role.ADMIN:
        return role

    # Check specific permission
    for perm in permissions:
        if (perm.resource == "*" or perm.resource == resource) and \
           (perm.action == "*" or perm.action == action):
            return role

    raise AuthorizationError(
        f"API key with role '{role}' not authorized for "
        f"'{action}' on '{resource}'"
    )


def require_role(api_key: str, required_role: Role) -> Role:
    """Check if an API key has at least the required role.

    Args:
        api_key: The API key from the request header.
        required_role: Minimum role required.

    Returns:
        The role that authorized this request.

    Raises:
        AuthorizationError: If the key's role is insufficient.
    """
    roles = _parse_api_key_roles()

    if not api_key or api_key not in roles:
        raise AuthorizationError("Unknown or missing API key")

    role = roles[api_key]
    role_level = list(Role).index(role)
    required_level = list(Role).index(required_role)

    if role_level < required_level:
        raise AuthorizationError(
            f"API key has role '{role}' but '{required_role}' is required"
        )

    return role
