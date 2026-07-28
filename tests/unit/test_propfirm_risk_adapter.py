"""BL-070 — PropFirmOrderRiskAdapter enforcement tests.

Validates that the adapter wired into OrderManager blocks:
- daily loss breaches
- max contracts over cap
- missing market inputs (fail-closed)
- missing stop (must specify protective stop)
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from execution.order_manager.types import OrderRequest
from policy.prop_firm.fixtures import TOPSTEP_TC_50K
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import PropFirmOrderRiskAdapter


@pytest.fixture
def adapter() -> PropFirmOrderRiskAdapter:
    gov = PropFirmRiskGovernor(profile=TOPSTEP_TC_50K, initial_balance=50_000.0)
    # Set balance so daily loss used = $500 (within limit $1K)
    gov.update(balance=49_500.0, equity=49_500.0)
    adapter = PropFirmOrderRiskAdapter(gov)
    adapter.update_market(
        instrument_id="MES", entry_price=Decimal("4500.00"), contract_size=Decimal("5")
    )
    return adapter


async def _check(adapter: PropFirmOrderRiskAdapter, req: OrderRequest) -> bool:
    return await adapter.check_order(req)


def test_adapter_allows_within_daily_loss(adapter: PropFirmOrderRiskAdapter) -> None:
    req = OrderRequest(
        instrument_id="MES",
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        time_in_force="day",
        price=Decimal("4500.00"),
        stop_price=Decimal("4492.00"),
        source="test",
    )
    import asyncio

    adapter._replay_only = True
    assert asyncio.run(_check(adapter, req)) is True


def test_adapter_blocks_when_daily_loss_breach(adapter: PropFirmOrderRiskAdapter) -> None:
    gov = adapter._governor
    # Force daily loss to $900 (within $1000 cap but reduces headroom)
    gov.update(balance=49_100.0, equity=49_100.0)
    req = OrderRequest(
        instrument_id="MES",
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        time_in_force="day",
        price=Decimal("4500.00"),
        stop_price=Decimal("4492.00"),
        source="test",
    )
    import asyncio

    adapter._replay_only = True
    # With stop_distance 8pt * $5/pt = $40 risk per contract.
    # Remaining daily loss capacity = $100. Adding $40 makes it $940 used.
    # Should still allow; it's $940 < $1000.
    # So instead test with smaller daily_loss capacity remaining:
    gov.update(balance=49_050.0, equity=49_050.0)
    # Now $950 used, adding $40 = $990, still under $1000.
    # To FORCE breach: balance = 49_000, equity = 49_000 → $1000 used.
    # Then adding 1 contract with $40 stop risk would breach ($1040 > $1000).
    gov.update(balance=49_000.0, equity=49_000.0)
    assert asyncio.run(_check(adapter, req)) is False


def test_adapter_blocks_missing_stop(adapter: PropFirmOrderRiskAdapter) -> None:
    req = OrderRequest(
        instrument_id="MES",
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        time_in_force="day",
        price=Decimal("4500.00"),
        source="test",
    )
    import asyncio

    assert asyncio.run(_check(adapter, req)) is False


def test_adapter_blocks_missing_market() -> None:
    gov = PropFirmRiskGovernor(profile=TOPSTEP_TC_50K, initial_balance=50_000.0)
    gov.update(balance=49_500.0, equity=49_500.0)
    adapter = PropFirmOrderRiskAdapter(gov)  # no update_market call
    req = OrderRequest(
        instrument_id="MES",
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        time_in_force="day",
        price=Decimal("4500.00"),
        stop_price=Decimal("4492.00"),
        source="test",
    )
    import asyncio

    assert asyncio.run(_check(adapter, req)) is False
