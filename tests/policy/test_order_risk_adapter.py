"""Tests for the hard prop-firm gate used by the OrderManager."""

from decimal import Decimal

import pytest

from execution.order_manager.types import OrderRequest
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import InstrumentRiskInput, PropFirmOrderRiskAdapter
from policy.prop_firm.profile import ContractCap, FirmProgramProfile, SupportMode


def _profile() -> FirmProgramProfile:
    return FirmProgramProfile(
        firm="TEST",
        program="Automated Futures",
        stage="evaluation",
        platform="paper",
        account_size=100_000,
        rule_version="test-v1",
        effective_from="2026-01-01",
        source_url="https://example.invalid/rules",
        source_checked_at="2026-01-01T00:00:00Z",
        support_mode=SupportMode.AUTO_SUPPORTED,
        profit_target_pct=0.1,
        max_daily_loss_pct=0.03,
        max_overall_loss_pct=0.06,
        risk_per_trade_pct=0.01,
        contract_cap=ContractCap(3),
    )


def _request(quantity: str = "1", stop: str | None = "5490") -> OrderRequest:
    return OrderRequest(
        instrument_id="MES",
        side="buy",
        quantity=Decimal(quantity),
        order_type="limit",
        price=Decimal("5500"),
        stop_price=Decimal(stop) if stop else None,
    )


@pytest.mark.asyncio
async def test_adapter_allows_order_inside_all_limits() -> None:
    adapter = PropFirmOrderRiskAdapter(
        PropFirmRiskGovernor(_profile(), 100_000),
        {"MES": InstrumentRiskInput(Decimal("5500"), Decimal("5"))},
    )

    assert await adapter.check_order(_request()) is True


@pytest.mark.asyncio
async def test_adapter_fails_closed_without_stop_or_contract_spec() -> None:
    adapter = PropFirmOrderRiskAdapter(PropFirmRiskGovernor(_profile(), 100_000))

    assert await adapter.check_order(_request(stop=None)) is False
    assert adapter.last_check is not None
    assert "Missing verified" in adapter.last_check.reason


@pytest.mark.asyncio
async def test_adapter_enforces_contract_cap() -> None:
    adapter = PropFirmOrderRiskAdapter(
        PropFirmRiskGovernor(_profile(), 100_000),
        {"MES": InstrumentRiskInput(Decimal("5500"), Decimal("5"))},
    )

    assert await adapter.check_order(_request(quantity="4")) is False
    assert adapter.last_check is not None
    assert "contract cap" in adapter.last_check.reason


@pytest.mark.asyncio
async def test_governor_enforces_per_trade_risk_budget() -> None:
    adapter = PropFirmOrderRiskAdapter(
        PropFirmRiskGovernor(_profile(), 100_000),
        {"MES": InstrumentRiskInput(Decimal("5500"), Decimal("50"))},
    )

    assert await adapter.check_order(_request(quantity="3")) is False
    assert adapter.last_check is not None
    assert "risk budget" in adapter.last_check.reason
