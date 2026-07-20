"""Pre-defined prop-firm profiles from official sources (verified 2026-07-17).

Sources are listed per profile.  Always re-check before relying on a profile
for live / funded trading.
"""

from __future__ import annotations

from policy.prop_firm.profile import (
    ContractCap,
    DrawdownMode,
    FirmProgramProfile,
    NewsBlackout,
    ScalingPlan,
    SessionRule,
    SupportMode,
)

# =========================================================================
# TOPSTEP
# =========================================================================
# Source: https://help.topstep.com/

TOPSTEP_TC_50K = FirmProgramProfile(
    firm="TOPSTEP",
    program="Trading Combine",
    stage="evaluation",
    platform="TopstepX",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://help.topstep.com/en/articles/8284197-trading-combine-parameters",
    source_checked_at="2026-07-19",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.10,
    max_daily_loss_pct=0.02,
    max_overall_loss_pct=0.04,
    max_daily_loss_amount=1_000,
    max_overall_loss_amount=2_000,
    overall_loss_lock_at_initial=True,
    dd_mode=DrawdownMode.TRAILING_EOD,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/Chicago",
    min_trading_days=0,
    min_profitable_days=0,
    max_concurrent_positions=0,
    contract_cap=ContractCap(max_mini_eq=5, per_product={"MES": 50}),
    allowed_products=["ES", "MES"],
    session_rule=SessionRule.STANDARD,
    risk_per_trade_pct=0.01,
)

TOPSTEP_XFA_STANDARD = FirmProgramProfile(
    firm="TOPSTEP",
    program="XFA",
    stage="funded",
    platform="TopstepX",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://help.topstep.com/en/articles/8284215-express-funded-account-parameters",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.0,  # no profit target in XFA
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.12,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/Chicago",
    min_trading_days=5,
    min_profitable_days=5,
    contract_cap=ContractCap(max_mini_eq=10),
    scaling_plan=ScalingPlan([(0.10, 15), (0.20, 20)]),
    session_rule=SessionRule.STANDARD,
    risk_per_trade_pct=0.01,
)

TOPSTEP_XFA_CONSISTENCY = FirmProgramProfile(
    firm="TOPSTEP",
    program="XFA",
    stage="funded",
    platform="TopstepX",
    account_size=50_000,
    rule_version="2026-07-01-consistency",
    effective_from="2026-06-01",
    source_url="https://help.topstep.com/en/articles/8284215-express-funded-account-parameters",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.0,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.12,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/Chicago",
    min_trading_days=5,
    min_profitable_days=5,
    consistency_pct=0.40,
    contract_cap=ContractCap(max_mini_eq=10),
    scaling_plan=ScalingPlan([(0.10, 15)]),
    session_rule=SessionRule.STANDARD,
    risk_per_trade_pct=0.01,
)

# =========================================================================
# APEX Trader Funding
# =========================================================================
# Source: https://apextraderfunding.com/help-center/
# Automation DENIED per official rules: no bot / API submit/modify/cancel.

APEX_MANUAL = FirmProgramProfile(
    firm="APEX",
    program="Standard",
    stage="evaluation",
    platform="Rithmic",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://apextraderfunding.com/help-center/getting-started/prohibited-activities/",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.ASSISTED_ONLY,
    profit_target_pct=0.08,
    max_daily_loss_pct=0.04,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/Chicago",
    min_trading_days=10,
    min_profitable_days=7,
    consistency_pct=0.30,
    contract_cap=ContractCap(max_mini_eq=8),
    session_rule=SessionRule.STANDARD,
    news_blackout=NewsBlackout(before_minutes=5, after_minutes=5),
    risk_per_trade_pct=0.01,
)

# =========================================================================
# Take Profit Trader (TPT)
# =========================================================================
# Source: https://takeprofittraderhelp.zendesk.com

TPT_TEST = FirmProgramProfile(
    firm="TPT",
    program="Test",
    stage="evaluation",
    platform="Tradovate",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170265979165-Rule-3-Do-Not-Hit-End-Of-Day-EOD-Maximum-Trailing-Drawdown",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.08,
    max_daily_loss_pct=0.04,
    max_overall_loss_pct=0.08,
    dd_mode=DrawdownMode.TRAILING_EOD,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/New_York",
    min_trading_days=5,
    min_profitable_days=5,
    consistency_pct=0.50,
    contract_cap=ContractCap(max_mini_eq=10),
    session_rule=SessionRule.STANDARD,
    risk_per_trade_pct=0.01,
)

TPT_PRO = FirmProgramProfile(
    firm="TPT",
    program="PRO",
    stage="funded",
    platform="Tradovate",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.ASSISTED_ONLY,
    profit_target_pct=0.0,
    max_daily_loss_pct=0.04,
    max_overall_loss_pct=0.08,
    dd_mode=DrawdownMode.TRAILING_INTRADAY,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/New_York",
    min_trading_days=0,
    contract_cap=ContractCap(max_mini_eq=10),
    session_rule=SessionRule.STANDARD,
    news_blackout=NewsBlackout(before_minutes=5, after_minutes=5),
    risk_per_trade_pct=0.01,
)

# =========================================================================
# MyFundedFutures (MFFU)
# =========================================================================
# Source: https://help.myfundedfutures.com/

MFFU_NEWS_RESTRICTED = FirmProgramProfile(
    firm="MFFU",
    program="Standard",
    stage="evaluation",
    platform="Tradovate",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://help.myfundedfutures.com/en/articles/8230009-news-trading-policy",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.10,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.12,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/New_York",
    min_trading_days=5,
    min_profitable_days=5,
    consistency_pct=0.30,
    contract_cap=ContractCap(max_mini_eq=10),
    session_rule=SessionRule.STANDARD,
    news_blackout=NewsBlackout(before_minutes=3, after_minutes=3),
    risk_per_trade_pct=0.01,
)

# =========================================================================
# FundedNext Futures
# =========================================================================
# Source: https://helpfutures.fundednext.com/

FUNDEDNEXT_FLEX = FirmProgramProfile(
    firm="FundedNext",
    program="Flex",
    stage="evaluation",
    platform="Tradovate",
    account_size=50_000,
    rule_version="2026-07-01",
    effective_from="2026-01-01",
    source_url="https://helpfutures.fundednext.com/en/articles/14878751-what-is-fundednext-futures-flex-challenge",
    source_checked_at="2026-07-17",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.10,
    max_daily_loss_pct=0.04,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.TRAILING_EOD,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/New_York",
    min_trading_days=0,
    min_profitable_days=0,
    contract_cap=ContractCap(max_mini_eq=15),
    session_rule=SessionRule.STANDARD,
    risk_per_trade_pct=0.01,
)
