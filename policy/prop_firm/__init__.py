"""Prop-firm risk governance for funded-account challenges.

Public API::

    from policy.prop_firm import THE5ERS, PropFirmRiskGovernor

    gov = PropFirmRiskGovernor(THE5ERS, initial_balance=100_000)
"""

from policy.prop_firm.dual_channel import (
    FUNDED_CONSISTENCY_PCT_MAX,
    FUNDED_MC_CONFIDENCE_LEVEL,
    FUNDED_MIN_PAPER_SESSIONS,
    FUNDED_MONTE_CARLO_PASS_RATE_MIN,
    FUNDED_SIMULATED_PASS_RATE_MIN,
    PERSONAL_DSR_MIN,
    PERSONAL_HAIRCUT_SHARPE_MIN,
    PERSONAL_MAX_DRAWDOWN_MAX,
    PERSONAL_WALK_FORWARD_ALPHA_MIN,
    Channel,
    FundedPromotionMetrics,
    PersonalPromotionMetrics,
    PromotionDecision,
    check_dual_channel,
    check_funded_channel,
    check_personal_channel,
    eligible_profiles,
    governor_clean,
)
from policy.prop_firm.fixtures import (
    ALPHA_ONE_6,
    ALPHA_PRO_8,
    APEX_MANUAL,
    E8_ONE,
    FTMO_1_STEP,
    FTMO_2_STEP_P1,
    FTMO_2_STEP_P2,
    FUNDEDNEXT_FLEX,
    MFFU_NEWS_RESTRICTED,
    THE5ERS_BOOTCAMP_FUNDED,
    THE5ERS_BOOTCAMP_STEP,
    THE5ERS_HIGH_STAKES_P1,
    THE5ERS_HIGH_STAKES_P2,
    THE5ERS_HYPER_GROWTH,
    THE5ERS_PRO_GROWTH,
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
    DailyLossAction,
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
    "ALPHA_ONE_6",
    "ALPHA_PRO_8",
    "APEX_MANUAL",
    "E8_ONE",
    "FTMO_1_STEP",
    "FTMO_2_STEP_P1",
    "FTMO_2_STEP_P2",
    "FUNDEDNEXT_FLEX",
    "FUNDED_CONSISTENCY_PCT_MAX",
    "FUNDED_MC_CONFIDENCE_LEVEL",
    "FUNDED_MIN_PAPER_SESSIONS",
    "FUNDED_MONTE_CARLO_PASS_RATE_MIN",
    "FUNDED_SIMULATED_PASS_RATE_MIN",
    "LUCID",
    "MFFU_NEWS_RESTRICTED",
    "PERSONAL_DSR_MIN",
    "PERSONAL_HAIRCUT_SHARPE_MIN",
    "PERSONAL_MAX_DRAWDOWN_MAX",
    "PERSONAL_WALK_FORWARD_ALPHA_MIN",
    "THE5ERS",
    "THE5ERS_BOOTCAMP_FUNDED",
    "THE5ERS_BOOTCAMP_STEP",
    "THE5ERS_HIGH_STAKES_P1",
    "THE5ERS_HIGH_STAKES_P2",
    "THE5ERS_HYPER_GROWTH",
    "THE5ERS_PRO_GROWTH",
    "TOPSTEP_TC_50K",
    "TOPSTEP_XFA_CONSISTENCY",
    "TOPSTEP_XFA_STANDARD",
    "TPT_PRO",
    "TPT_TEST",
    "AccountState",
    "Breach",
    "BreachType",
    "ChallengeStatus",
    "Channel",
    "ContractCap",
    "DailyLossAction",
    "DrawdownMode",
    "FirmProgramProfile",
    "FirmProgramRegistry",
    "FundedPromotionMetrics",
    "InstrumentRiskInput",
    "NewsBlackout",
    "OrderCheck",
    "PersonalPromotionMetrics",
    "PromotionDecision",
    "PropFirmGovernor",
    "PropFirmOrderRiskAdapter",
    "PropFirmProfile",
    "PropFirmRiskGovernor",
    "ScalingPlan",
    "SessionRule",
    "SupportMode",
    "check_dual_channel",
    "check_funded_channel",
    "check_personal_channel",
    "eligible_profiles",
    "governor_clean",
]
