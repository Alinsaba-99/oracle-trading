"""Structured contracts for Oracle's LLM-led investment committee.

.. deprecated::
   These types have moved to ``application/contracts``.  This module
   re-exports them for backward compatibility.  New code should import
   directly from ``application.contracts``.
"""

from __future__ import annotations

from agents.committee.triggers import CommitteeTrigger
from application.contracts import (
    ExecutionPreference,
    IntentAction,
    OrderStyle,
    PortfolioPlan,
    PositionTarget,
    TradeIntent,
    TradingMode,
    Urgency,
)

__all__ = [
    "CommitteeTrigger",
    "ExecutionPreference",
    "IntentAction",
    "OrderStyle",
    "PortfolioPlan",
    "PositionTarget",
    "TradeIntent",
    "TradingMode",
    "Urgency",
]
