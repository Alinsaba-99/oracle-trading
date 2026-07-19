"""Oracle operating modes — deterministic environment enum.

Every Oracle process runs in exactly one mode.  The mode determines:
- which credentials and accounts are reachable;
- whether the OMS may submit orders to a broker;
- what data sources are authoritative;
- which risk and rule profiles apply.

This module is part of ``core/domain`` — it has zero external dependencies.
"""

from __future__ import annotations

from enum import StrEnum


class OracleMode(StrEnum):
    """Operating mode for the Oracle platform.

    Modes form a progression from research to live funded trading.
    Each mode unlocks strictly more authority than the previous one.
    """

    # ── Research & development ────────────────────────────────────────
    RESEARCH = "research"
    """Local research only.  No broker connection.  Synthetic data only.

    Default mode when no mode is configured.  Fail-closed for any
    operation that requires market data or broker access.
    """

    # ── Testing with historical data ──────────────────────────────────
    REPLAY = "replay"
    """Deterministic replay of historical market data.

    Uses pre-recorded data from Parquet/CSV files.  No live broker
    connection.  Useful for backtest parity verification and strategy
    debugging.
    """

    # ── Simulated execution ───────────────────────────────────────────
    PAPER = "paper"
    """Paper trading with simulated fills and a virtual ledger.

    The PaperBroker provides market data from a live feed but routes
    orders through an in-process fill engine.  No real money at risk.
    """

    # ── Shadow (parallel) execution ───────────────────────────────────
    SHADOW = "shadow"
    """Orders are submitted to a live broker but financial impact is
    only tracked, not enforced.

    Positions are mirrored to a shadow ledger.  Used to validate
    execution logic before committing real capital.  Requires G4 risk
    kernel and G3 durable OMS.
    """

    # ── Evaluation (prop-firm challenge) ──────────────────────────────
    EVALUATION = "evaluation"
    """Live execution under a prop-firm evaluation account.

    Full risk kernel (daily loss, drawdown, contract caps) is
    enforced.  Only one specific firm/program profile is active.
    """

    # ── Live funded trading ───────────────────────────────────────────
    FUNDED = "funded"
    """Live execution on a funded prop-firm account.

    All safety controls are mandatory.  Only reachable after G7
    certification of the specific program.
    """


# ── Valid transitions ────────────────────────────────────────────────
# Modes can only advance forward in the list above.  A running system
# never switches from FUNDED back to RESEARCH without a full stop and
# credential rotation.

VALID_TRANSITIONS: dict[OracleMode, list[OracleMode]] = {
    OracleMode.RESEARCH: [OracleMode.REPLAY, OracleMode.PAPER],
    OracleMode.REPLAY: [OracleMode.PAPER],
    OracleMode.PAPER: [OracleMode.SHADOW],
    OracleMode.SHADOW: [OracleMode.EVALUATION],
    OracleMode.EVALUATION: [OracleMode.FUNDED],
    OracleMode.FUNDED: [],
}


def can_transition(from_mode: OracleMode, to_mode: OracleMode) -> bool:
    """Return True if the transition ``from_mode → to_mode`` is valid.

    Transitions outside the defined progression (e.g. FUNDED → RESEARCH)
    require a full system stop and are not permitted at runtime.
    """
    return to_mode in VALID_TRANSITIONS.get(from_mode, [])


# ── Mode-specific configuration keys ─────────────────────────────────
# Each mode uses distinct environment variable prefixes to isolate
# credentials, account IDs, and broker endpoints.

MODE_ENV_PREFIX: dict[OracleMode, str] = {
    OracleMode.RESEARCH: "ORACLE_RES_",
    OracleMode.REPLAY: "ORACLE_REPLAY_",
    OracleMode.PAPER: "ORACLE_PAPER_",
    OracleMode.SHADOW: "ORACLE_SHADOW_",
    OracleMode.EVALUATION: "ORACLE_EVAL_",
    OracleMode.FUNDED: "ORACLE_FUNDED_",
}


def mode_env_var(mode: OracleMode, var_name: str) -> str:
    """Return the mode-qualified environment variable name.

    Example::

        mode_env_var(OracleMode.PAPER, "API_KEY") → "ORACLE_PAPER_API_KEY"
    """
    return f"{MODE_ENV_PREFIX[mode]}{var_name}"
