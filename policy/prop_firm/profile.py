"""Prop-firm evaluation profiles.

Each profile encodes the *exact* rules a funded-account program enforces:
profit target, max daily loss, max overall loss (static or trailing),
minimum trading days, and the consistency rule.  Profiles are immutable
configuration consumed by :class:`~policy.prop_firm.governor.PropFirmRiskGovernor`.

NOTE: firm rules change frequently.  The5ers numbers below were verified
via the official site on 2026-07-13; Lucid numbers are sector-typical
placeholders (lucidtrading.com returned HTTP 403 and could not be
verified).  Confirm exact parameters before live use.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropFirmProfile:
    """Immutable rule-set for a single funded-account program.

    All percentage fields are decimals (0.03 = 3%).
    """

    name: str
    # --- Profitability -------------------------------------------------
    profit_target_pct: float
    # --- Loss limits ---------------------------------------------------
    max_daily_loss_pct: float
    max_overall_loss_pct: float
    #: ``"static"`` = fixed floor at ``initial*(1-pct)``;
    #: ``"trailing"`` = floor trails the peak balance upward.
    dd_mode: str = "static"
    #: Reference for the daily loss: ``"balance"`` or ``"equity"``.
    #: Equity-based is stricter (includes floating P&L).
    daily_loss_basis: str = "equity"
    #: Reference for the overall loss: ``"balance"`` or ``"equity"``.
    overall_loss_basis: str = "equity"
    # --- Time / volume constraints ------------------------------------
    min_trading_days: int = 0
    min_profitable_days: int = 0
    #: Max fraction of total profit attributable to a single day.  0.0
    #: disables the consistency rule.
    consistency_pct: float = 0.0
    #: Max simultaneous open positions (0 = unlimited).
    max_concurrent_positions: int = 0
    # --- Position sizing ----------------------------------------------
    #: Default per-trade risk as a fraction of balance (1% rule).
    risk_per_trade_pct: float = 0.01


#: The5ers "High Stakes" style profile (verified 2026-07-13).
#: target 10%, daily 3%, overall 6%, MT5, forex/metals/indices.
THE5ERS = PropFirmProfile(
    name="The5ers High Stakes",
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.06,
    dd_mode="static",
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    min_trading_days=0,
    min_profitable_days=3,
    consistency_pct=0.0,
    risk_per_trade_pct=0.01,
)

#: Lucid profile — SECTOR-TYPICAL, NOT VERIFIED (site returned 403).
#: Confirm exact numbers before relying on this.
LUCID = PropFirmProfile(
    name="Lucid (unverified)",
    profit_target_pct=0.08,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode="static",
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    min_trading_days=3,
    min_profitable_days=0,
    consistency_pct=0.0,
    risk_per_trade_pct=0.01,
)
