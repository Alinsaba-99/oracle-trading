"""OrderManager adapter for the deterministic prop-firm risk governor."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from execution.order_manager.types import OrderRequest
from policy.prop_firm.governor import OrderCheck, PropFirmRiskGovernor


@dataclass(frozen=True)
class InstrumentRiskInput:
    """Current executable price and contract multiplier used by the risk gate."""

    entry_price: Decimal
    contract_size: Decimal


class PropFirmOrderRiskAdapter:
    """Fail-closed adapter implementing the OrderManager ``check_order`` contract."""

    def __init__(
        self,
        governor: PropFirmRiskGovernor,
        market_inputs: dict[str, InstrumentRiskInput] | None = None,
    ) -> None:
        self._governor = governor
        self._market_inputs = market_inputs or {}
        self.last_check: OrderCheck | None = None

    def update_market(
        self, instrument_id: str, entry_price: Decimal, contract_size: Decimal
    ) -> None:
        self._market_inputs[instrument_id] = InstrumentRiskInput(entry_price, contract_size)

    async def check_order(self, request: OrderRequest) -> bool:
        market = self._market_inputs.get(request.instrument_id)
        if market is None:
            self.last_check = OrderCheck(
                False, "Missing verified market and contract specification"
            )
            return False
        if request.stop_price is None:
            self.last_check = OrderCheck(False, "A protective stop is required")
            return False

        entry = request.price or market.entry_price
        quantity = float(request.quantity)
        contract_cap = self._governor.profile.contract_cap
        if contract_cap is not None and quantity > contract_cap.max_mini_eq:
            self.last_check = OrderCheck(
                False,
                f"Requested quantity exceeds contract cap {contract_cap.max_mini_eq}",
                max_lots=float(contract_cap.max_mini_eq),
            )
            return False

        self.last_check = self._governor.check_new_order(
            entry=float(entry),
            stop=float(request.stop_price),
            lots=quantity,
            contract_size=float(market.contract_size),
        )
        return self.last_check.allowed
