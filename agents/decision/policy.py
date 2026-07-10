"""Bridge to Phase 0 PolicyEngine — institutional policy enforcement.

Provides a deterministic check layer between the decision pipeline
and external policy rules.
"""

from __future__ import annotations

from agents.protocol import PortfolioDecision

__all__ = ["PolicyBridge"]


class PolicyBridge:
    """Bridge to Phase 0 PolicyEngine — checks institutional policy limits."""

    def __init__(self) -> None:
        self._hard_limits: list[str] = []

    def check(self, decision: PortfolioDecision) -> tuple[bool, list[str]]:
        """Check institutional policy limits.

        Returns (approved, reasons). Current implementation always passes.
        """
        _ = decision  # consumed when hard limits are defined
        return (True, [])
