"""Pre-defined prop-firm profiles from official sources (verified 2026-07-17).

Sources are listed per profile.  Always re-check before relying on a profile
for live / funded trading.
"""

from __future__ import annotations

from policy.prop_firm.profile import (
    ContractCap,
    DailyLossAction,
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
    # BL-095 (2026-08-21): vintage rename — 2026 sources verified 2026-08-21
    # (snapshots in docs/firm_sources/topstep/): profit target $3,000 (6%),
    # MLL $2,000 trailing EOD (locks at initial balance), optional daily
    # loss $1,000, 5 mini / 50 micro, 50% consistency target. NOTE: the
    # 2026 "Consistency Target" (best day < 50% of PROFIT TARGET) is a
    # soft rule with different semantics than the governor's
    # consistency_pct (share of TOTAL profit) — deliberately NOT modeled;
    # treat consistency_pct=0.0 as a declared gap, not "no rule".
    rule_version="2026-08-21",
    effective_from="2026-01-01",
    source_url="https://help.topstep.com/en/articles/8284197-trading-combine-parameters",
    source_checked_at="2026-08-21",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.06,  # BL-095: $3,000 on $50K (era $5,000/10% pre-2026)
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
    rule_version="2026-08-15",
    effective_from="2026-06-01",
    source_url="https://help.myfundedfutures.com/en/articles/8230009-news-trading-policy",
    source_checked_at="2026-08-15",
    support_mode=SupportMode.RESEARCH_ONLY,
    # BL-095 (2026-08-15, re-verified 2026-08-21): MFFU 2026 rules — profit
    # target $3.000 (6%) on $50K, daily loss limit removed on Rapid plans,
    # 5% overall loss remains. Gap dichiarato: the 2026 "50% consistency
    # (Eval Only)" soft rule is NOT modeled here (governor's consistency_pct
    # has share-of-total-profit semantics, not the eval rule's); the
    # simulator scripts/simulate_mff_challenge.py reports it as diagnostic.
    # Source snapshot: docs/firm_sources/myfundedfutures/.
    profit_target_pct=0.06,
    max_daily_loss_pct=0.0,  # removed on Rapid 2026 plans
    max_overall_loss_pct=0.05,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="America/New_York",
    min_trading_days=0,  # MFFU removed minimum trading days in 2026
    min_profitable_days=0,
    consistency_pct=0.0,  # BL-095: 2026 eval-only 50% soft rule NOT modeled
    # (target-based semantics ≠ governor's share-of-total); documented gap
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


# ---------------------------------------------------------------------------
# BL-721 — fixtures verified against the 2026-08-22 official snapshots in
# docs/firm_sources/ (sha256 manifest: docs/firm_sources/SNAPSHOTS.tsv).
# Every number below is traceable to a snapshot file; anything NOT in a
# snapshot is a declared gap in the per-profile comment.
# ---------------------------------------------------------------------------


# FTMO — https://ftmo.com/en/trading-objectives/ (1c817a84…d4d48)

FTMO_1_STEP = FirmProgramProfile(
    firm="FTMO",
    program="1-Step",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://ftmo.com/en/trading-objectives/",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: target 10%, daily 3% (on midnight balance, equity basis),
    # overall 10% TRAILING_EOD on midnight-max balance (only increases;
    # resets on withdrawal). Reset tz 00:00 CE(S)T.
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.TRAILING_EOD,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="Europe/Prague",
    # Gap dichiarato: Best Day ≤ 50% dei Positive Days' Profit è regola di
    # passaggio NON-breach (si continua a tradare) — semantica diversa da
    # consistency_pct; non modellata (stessa convenzione Topstep BL-095).
    # Gap: news-ban/EA policy su account funded — FAQ JS-rendered, seconda
    # passata BL-720.
)


FTMO_2_STEP_P1 = FirmProgramProfile(
    firm="FTMO",
    program="2-Step",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://ftmo.com/en/trading-objectives/",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: Challenge target 10%, daily 5%, overall 10% static,
    # min 4 trading days/fase.
    profit_target_pct=0.10,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="Europe/Prague",
    min_trading_days=4,
)


FTMO_2_STEP_P2 = FirmProgramProfile(
    firm="FTMO",
    program="2-Step",
    stage="verification",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://ftmo.com/en/trading-objectives/",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    profit_target_pct=0.05,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="Europe/Prague",
    min_trading_days=4,
)


# The5ers — the5ers.com/challenge-programs-… (f5321296…470a5)

THE5ERS_BOOTCAMP_STEP = FirmProgramProfile(
    firm="The5ers",
    program="Bootcamp",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: 3 step, target 6%/step, max loss 5%/step, NESSUNA daily rule
    # in evaluation (la 3% daily pause è solo funded).
    profit_target_pct=0.06,
    max_daily_loss_pct=0.0,
    max_overall_loss_pct=0.05,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
)


THE5ERS_BOOTCAMP_FUNDED = FirmProgramProfile(
    firm="The5ers",
    program="Bootcamp",
    stage="funded",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: funded max loss 4%, scaling target 5%, 3% daily PAUSE
    # (sospende la giornata, NON termina).
    profit_target_pct=0.05,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.04,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
    daily_loss_action=DailyLossAction.PAUSE,
)


THE5ERS_HIGH_STAKES_P1 = FirmProgramProfile(
    firm="The5ers",
    program="High Stakes",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: P1 target 8% (tabella programmi; il testo riporta "10%" in
    # un punto — contraddizione interna alla pagina, si usa la tabella;
    # da chiarire in seconda passata BL-720). Daily 5% TERMINA l'account.
    profit_target_pct=0.08,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
    min_profitable_days=3,
    news_blackout=NewsBlackout(before_minutes=2, after_minutes=2),
    daily_loss_action=DailyLossAction.TERMINATE,
)


THE5ERS_HIGH_STAKES_P2 = FirmProgramProfile(
    firm="The5ers",
    program="High Stakes",
    stage="verification",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    profit_target_pct=0.05,
    max_daily_loss_pct=0.05,
    max_overall_loss_pct=0.10,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
    min_profitable_days=3,
    news_blackout=NewsBlackout(before_minutes=2, after_minutes=2),
    daily_loss_action=DailyLossAction.TERMINATE,
)


THE5ERS_HYPER_GROWTH = FirmProgramProfile(
    firm="The5ers",
    program="Hyper Growth",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: 1-step, target 10%, stop-out 6%, 3% daily PAUSE (sospende
    # la giornata).
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.06,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
    daily_loss_action=DailyLossAction.PAUSE,
)


THE5ERS_PRO_GROWTH = FirmProgramProfile(
    firm="The5ers",
    program="Pro Growth",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: 1-step, target 10%, stop-out 6%, 3% daily TERMINATES,
    # min 3 profitable days.
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.06,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
    min_profitable_days=3,
    daily_loss_action=DailyLossAction.TERMINATE,
)


# Alpha Capital Group — alphacapitalgroup.uk T&C (7f8bfa39…f9df)

ALPHA_PRO_8 = FirmProgramProfile(
    firm="Alpha Capital",
    program="Alpha Pro 8%",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://alphacapitalgroup.uk/terms-and-conditions",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # T&C Schedule 1: Pro 8% → target 8% S1 (+5% S2, non modellato), max
    # sim DD 8% static, daily 4% balance-based, min 3 trading days/step.
    # News ±5 min (nuova apertura o chiusura vietata sullo strumento target).
    profit_target_pct=0.08,
    max_daily_loss_pct=0.04,
    max_overall_loss_pct=0.08,
    dd_mode=DrawdownMode.STATIC,
    daily_loss_basis="balance",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="Europe/London",
    min_trading_days=3,
    news_blackout=NewsBlackout(before_minutes=5, after_minutes=5),
    # Anti-HFT (T&C): durata media trade > 2 min e ≥50% profitto da trade
    # > 2 min — enforcement in BL-722, qui dichiarata.
    min_trade_duration_minutes=2.0,
)


ALPHA_ONE_6 = FirmProgramProfile(
    firm="Alpha Capital",
    program="Alpha One 6%",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://alphacapitalgroup.uk/terms-and-conditions",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # T&C Schedule 1: One 6% → target 6% single-step, max DD 4% TRAILING
    # (highest equity or balance), daily 3%, min 1 trading day.
    profit_target_pct=0.06,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.04,
    dd_mode=DrawdownMode.TRAILING_EOD,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="Europe/London",
    min_trading_days=1,
    news_blackout=NewsBlackout(before_minutes=5, after_minutes=5),
    min_trade_duration_minutes=2.0,
)


# E8 Markets — e8markets.com/e8-one (2684b40f…9303)

E8_ONE = FirmProgramProfile(
    firm="E8 Markets",
    program="E8 One",
    stage="evaluation",
    platform="MT5",
    account_size=100_000,
    rule_version="2026-08-22",
    effective_from="2026-08-22",
    source_url="https://www.e8markets.com/e8-one",
    source_checked_at="2026-08-22",
    support_mode=SupportMode.ASSISTED_ONLY,
    # Snapshot: Dynamic Drawdown — il floor sale SOLO sui profitti CHIUSI
    # ("we count what you keep"); challenge senza consistency né profit cap.
    # Gap dichiarato: i default di target/DD/payout NON sono leggibili nella
    # pagina (customizzabili al checkout) → valori = 0 finché la seconda
    # passata BL-720 non li snapshot-ta. Il profilo codifica la MECCANICA
    # (TRAILING_CLOSED), non i numeri. NON usare per simulazioni.
    profit_target_pct=0.0,
    max_daily_loss_pct=0.0,
    max_overall_loss_pct=0.0,
    dd_mode=DrawdownMode.TRAILING_CLOSED,
    daily_loss_basis="equity",
    overall_loss_basis="equity",
    daily_loss_reset_timezone="UTC",
)


# FundedNext — gap dichiarato: i numeri dei programmi CFD (Stellar/Legacy)
# NON sono negli snapshot 2026-08-22 (pagine prodotto JS-rendered); seconda
# passata BL-720. Resta FUNDEDNEXT_FLEX (futures) sopra.
