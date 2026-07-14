"""Prop-firm risk governance for funded-account challenges.

Public API::

    from policy.prop_firm import THE5ERS, PropFirmRiskGovernor

    gov = PropFirmRiskGovernor(THE5ERS, initial_balance=100_000)
"""

from policy.prop_firm.governor import (
    AccountState,
    Breach,
    BreachType,
    ChallengeStatus,
    OrderCheck,
    PropFirmRiskGovernor,
)
from policy.prop_firm.profile import LUCID, THE5ERS, PropFirmProfile

__all__ = [
    "LUCID",
    "THE5ERS",
    "AccountState",
    "Breach",
    "BreachType",
    "ChallengeStatus",
    "OrderCheck",
    "PropFirmGovernor",
    "PropFirmProfile",
    "PropFirmRiskGovernor",
]

#: Alias for the canonical governor name.
PropFirmGovernor = PropFirmRiskGovernor
