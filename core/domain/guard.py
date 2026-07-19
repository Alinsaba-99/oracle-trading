"""Startup mode guard — fail-closed mode enforcement.

Every Oracle entry point (CLI, API, worker) must call ``guard(mode)``
at startup.  The guard verifies that the requested mode is allowed and
that all required credentials are present.
"""

from __future__ import annotations

import os
import sys

from core.domain.mode import OracleMode, MODE_ENV_PREFIX, VALID_TRANSITIONS, can_transition

# ── Error codes ──────────────────────────────────────────────────────

MODE_MISMATCH = "MODE_MISMATCH"
MISSING_CREDENTIALS = "MISSING_CREDENTIALS"
INVALID_TRANSITION = "INVALID_TRANSITION"


class ModeGuardError(RuntimeError):
    """Raised when the mode guard rejects startup."""


# ── Required environment variables per mode ──────────────────────────

MODE_REQUIRED_ENV: dict[OracleMode, list[str]] = {
    OracleMode.RESEARCH: [],
    OracleMode.REPLAY: ["DATA_DIR"],
    OracleMode.PAPER: ["API_KEY"],
    OracleMode.SHADOW: ["API_KEY"],
    OracleMode.EVALUATION: ["API_KEY", "BROKER_TOKEN"],
    OracleMode.FUNDED: ["API_KEY", "BROKER_TOKEN"],
}


def guard(
    mode: OracleMode,
    *,
    env: dict[str, str] | None = None,
    previous_mode: OracleMode | None = None,
) -> None:
    """Startup guard for Oracle mode.

    Args:
        mode: The mode the process is trying to start in.
        env: Environment variables (defaults to ``os.environ``).
        previous_mode: If set, verifies that the mode transition is valid.

    Raises:
        ModeGuardError: If the mode guard rejects startup.
            The error message includes details about what failed.
    """
    env = env or dict(os.environ)

    # 1. Verify the mode is explicitly set
    mode_str = env.get("ORACLE_MODE", "").lower()
    if mode_str:
        try:
            configured_mode = OracleMode(mode_str)
        except ValueError:
            raise ModeGuardError(
                f"Invalid ORACLE_MODE={mode_str!r}. "
                f"Valid modes: {', '.join(m.value for m in OracleMode)}",
                MODE_MISMATCH,
            )
        if configured_mode != mode:
            raise ModeGuardError(
                f"ORACLE_MODE={configured_mode!r} does not match requested "
                f"mode={mode!r}",
                MODE_MISMATCH,
            )
    elif mode != OracleMode.RESEARCH:
        raise ModeGuardError(
            "ORACLE_MODE is not set.  Set it explicitly for any mode "
            "other than 'research'.",
            MODE_MISMATCH,
        )

    # 2. Verify mode transition
    if previous_mode is not None and not can_transition(previous_mode, mode):
        raise ModeGuardError(
            f"Invalid mode transition: {previous_mode} → {mode}. "
            f"Valid transitions from {previous_mode}: "
            f"{', '.join(m.value for m in VALID_TRANSITIONS.get(previous_mode, []))}",
            INVALID_TRANSITION,
        )

    # 3. Check required env vars
    prefix = MODE_ENV_PREFIX[mode]
    missing: list[str] = []
    for var in MODE_REQUIRED_ENV.get(mode, []):
        prefixed = f"{prefix}{var}"
        if not env.get(prefixed):
            missing.append(prefixed)

    if missing:
        raise ModeGuardError(
            f"Missing required environment variables for mode {mode!r}: "
            f"{', '.join(missing)}",
            MISSING_CREDENTIALS,
        )


def current_mode(env: dict[str, str] | None = None) -> OracleMode:
    """Detect the current operating mode from the environment.

    Falls back to ``RESEARCH`` if ``ORACLE_MODE`` is not set or empty.
    """
    env = env or dict(os.environ)
    mode_str = env.get("ORACLE_MODE", "").lower()
    if not mode_str:
        return OracleMode.RESEARCH
    try:
        return OracleMode(mode_str)
    except ValueError:
        return OracleMode.RESEARCH
