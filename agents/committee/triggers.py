"""Committee convocation triggers."""

from __future__ import annotations

from enum import StrEnum


class CommitteeTrigger(StrEnum):
    """Reason the investment committee was convened."""

    MARKET_REVIEW = "market_review"
    REBALANCE = "rebalance"
    STRATEGY_REVIEW = "strategy_review"
    RISK_ALERT = "risk_alert"
    EXTREME_MARKET = "extreme_market"
