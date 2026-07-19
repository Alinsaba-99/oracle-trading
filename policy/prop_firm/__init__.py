"""Prop-firm risk governance for funded-account challenges.

Public API::

    from policy.prop_firm import THE5ERS, PropFirmRiskGovernor

    gov = PropFirmRiskGovernor(THE5ERS, initial_balance=100_000)
"""

from policy.prop_firm.fixtures import (
    APEX_MANUAL,
    FUNDEDNEXT_FLEX,
    MFFU_NEWS_RESTRICTED,
    TOPSTEP_TC_50K,
    TOPSTEP_XFA_CONSISTENCY,
    TOPSTEP_XFA_STANDARD,
    TPT_PRO,
    TPT_TEST,
)
from policy.prop_firm.governor import (
    AccountState,
    Breach,
    BreachType,
    ChallengeStatus,
    OrderCheck,
    PropFirmRiskGovernor,
)
from policy.prop_firm.order_risk import InstrumentRiskInput, PropFirmOrderRiskAdapter
from policy.prop_firm.profile import (
    ContractCap,
    DrawdownMode,
    FirmProgramProfile,
    FirmProgramRegistry,
    NewsBlackout,
    ScalingPlan,
    SessionRule,
    SupportMode,
)

# ---------------------------------------------------------------------------
# Well-known profiles
# ---------------------------------------------------------------------------

#: The5ers "High Stakes" — R0.4 legacy alias, kept for backward compatibility.
#: Verified via official site on 2026-07-17.
THE5ERS = FirmProgramProfile(
    firm="The5ers",
    program="High Stakes",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://the5ers.com/high-stakes",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.ASSISTED_ONLY,
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.06,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    min_profitable_days=3,
)

#: Lucid — sector-typical placeholder (site returned HTTP 403).
LUCID = FirmProgramProfile(
    firm="Lucid",
    program="Standard",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="unverified",
    effective_from="2026-01-01",
    source_url="https://lucidtrading.com",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.UNSUPPORTED,
    profit_target_pct=0.08,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    min_trading_days=3,
)

# ---------------------------------------------------------------------------
# Aliases for backward compatibility
# ---------------------------------------------------------------------------
PropFirmProfile = FirmProgramProfile
PropFirmGovernor = PropFirmRiskGovernor

__all__ = [
    "APEX_MANUAL",
    "FUNDEDNEXT_FLEX",
    "LUCID",
    "MFFU_NEWS_RESTRICTED",
    "THE5ERS",
    "TOPSTEP_TC_50K",
    "TOPSTEP_XFA_CONSISTENCY",
    "TOPSTEP_XFA_STANDARD",
    "TPT_PRO",
    "TPT_TEST",
    "AccountState",
    "Breach",
    "BreachType",
    "ChallengeStatus",
    "ContractCap",
    "DrawdownMode",
    "FirmProgramProfile",
    "FirmProgramRegistry",
    "InstrumentRiskInput",
    "NewsBlackout",
    "OrderCheck",
    "PropFirmGovernor",
    "PropFirmOrderRiskAdapter",
    "PropFirmProfile",
    "PropFirmRiskGovernor",
    "ScalingPlan",
    "SessionRule",
    "SupportMode",
]
