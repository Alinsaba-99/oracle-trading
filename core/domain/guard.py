"""Startup mode guard — fail-closed mode enforcement.

Every Oracle entry point (CLI, API, worker) must call ``guard(mode)``
at startup.  The guard verifies that the requested mode is allowed and
that all required credentials are present.
"""

from __future__ import annotations

import os

from core.domain.mode import MODE_ENV_PREFIX, VALID_TRANSITIONS, OracleMode, can_transition

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
    mode: OracleMode, *, env: dict[str, str] | None = None, previous_mode: OracleMode | None = None
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
        except ValueError as exc:
            raise ModeGuardError(
                f"Invalid ORACLE_MODE={mode_str!r}. "
                f"Valid modes: {', '.join(m.value for m in OracleMode)}",
                MODE_MISMATCH,
            ) from exc
        if configured_mode != mode:
            raise ModeGuardError(
                f"ORACLE_MODE={configured_mode!r} does not match requested mode={mode!r}",
                MODE_MISMATCH,
            )
    elif mode != OracleMode.RESEARCH:
        raise ModeGuardError(
            "ORACLE_MODE is not set.  Set it explicitly for any mode other than 'research'.",
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
            f"Missing required environment variables for mode {mode!r}: {', '.join(missing)}",
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


# ── Cross-environment credential isolation ──────────────────────────
# Each mode must only access credentials and endpoints appropriate to
# its authority level.  The following rules prevent accidental or
# malicious credential crossing.

# Credential sets that belong to each mode.  Keys are env var names.
_MODE_CREDENTIALS: dict[OracleMode, set[str]] = {
    OracleMode.RESEARCH: set(),
    OracleMode.REPLAY: set(),
    OracleMode.PAPER: {"ORACLE_PAPER_API_KEY"},
    OracleMode.SHADOW: {"ORACLE_SHADOW_API_KEY", "ORACLE_SHADOW_BROKER_TOKEN"},
    OracleMode.EVALUATION: {"ORACLE_EVAL_API_KEY", "ORACLE_EVAL_BROKER_TOKEN"},
    OracleMode.FUNDED: {"ORACLE_FUNDED_API_KEY", "ORACLE_FUNDED_BROKER_TOKEN"},
}

# Credential sets that MUST NOT be present when running in a given mode.
# For example, when running in PAPER mode, funded credentials should not
# be set — this prevents accidental paper→funded crossing.
_FORBIDDEN_CREDENTIALS: dict[OracleMode, set[str]] = {
    OracleMode.RESEARCH: set(),
    OracleMode.REPLAY: set(),
    OracleMode.PAPER: {"ORACLE_FUNDED_API_KEY", "ORACLE_FUNDED_BROKER_TOKEN"},
    OracleMode.SHADOW: {"ORACLE_FUNDED_API_KEY", "ORACLE_FUNDED_BROKER_TOKEN"},
    OracleMode.EVALUATION: {"ORACLE_FUNDED_API_KEY", "ORACLE_FUNDED_BROKER_TOKEN"},
    OracleMode.FUNDED: set(),
}


def check_credential_isolation(env: dict[str, str] | None = None) -> list[str]:
    """Verify cross-environment credential isolation.

    Returns a list of violations (empty list = clean).  A violation is
    raised when a credential from a higher-authority mode is present in
    a lower-authority mode's environment.

    Example::

        violations = check_credential_isolation(os.environ)
        if violations:
            raise ModeGuardError(
                "Environment crossing detected",
                f"Found higher-mode credentials: {violations}",
            )
    """
    env = env or dict(os.environ)
    mode = current_mode(env)
    violations: list[str] = []

    for cred in _FORBIDDEN_CREDENTIALS.get(mode, set()):
        if env.get(cred):
            violations.append(f"{cred} is set but current mode is {mode.value}")

    return violations
