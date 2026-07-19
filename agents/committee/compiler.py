"""Compile desired portfolio positions into broker-neutral trade intents."""

from __future__ import annotations

from agents.committee.contracts import IntentAction, PortfolioPlan, TradeIntent


class PortfolioPlanCompiler:
    """Translate target positions into idempotent position deltas.

    The compiler does not submit orders and does not enforce risk. It only
    compares an LLM-authored target portfolio with reconciled broker positions.
    """

    def compile(self, plan: PortfolioPlan, current_positions: dict[str, int]) -> list[TradeIntent]:
        intents: list[TradeIntent] = []
        for target in plan.targets:
            current = current_positions.get(target.instrument_id, 0)
            desired = target.target_contracts
            delta = desired - current
            if delta == 0:
                continue

            intents.append(
                TradeIntent(
                    decision_id=plan.decision_id,
                    instrument_id=target.instrument_id,
                    action=self._classify(current, desired),
                    side="buy" if delta > 0 else "sell",
                    quantity=abs(delta),
                    execution=target.execution,
                    rationale=target.thesis,
                )
            )
        return intents

    @staticmethod
    def _classify(current: int, desired: int) -> IntentAction:
        if current == 0:
            return IntentAction.OPEN
        if desired == 0:
            return IntentAction.CLOSE
        if (current > 0) != (desired > 0):
            return IntentAction.REVERSE
        if abs(desired) > abs(current):
            return IntentAction.INCREASE
        return IntentAction.REDUCE
