"""Tests for the MetaTrader 5 broker adapter (mock-backed)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from execution.brokers.metatrader import (
    ORDER_TYPE_BUY,
    ORDER_TYPE_SELL,
    ORDER_TYPE_SELL_LIMIT,
    MetaTraderBroker,
    MockMT5Client,
    SymbolMapper,
    _magic_for,
)


def _order(
    side: str = "buy",
    otype: str = "market",
    qty: float = 0.1,
    price: float | None = None,
    stop: float | None = None,
    instr: str = "EURUSD",
) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id=instr,
        side=side,
        order_type=otype,
        quantity=qty,
        price=price,
        stop_price=stop,
        order_id="loc-1",
    )


class TestSymbolMapper:
    def test_suffix(self) -> None:
        m = SymbolMapper(suffix=".r")
        assert m.to_broker("EURUSD") == "EURUSD.r"
        assert m.from_broker("EURUSD.r") == "EURUSD"

    def test_no_suffix_passthrough(self) -> None:
        assert SymbolMapper().to_broker("EURUSD") == "EURUSD"

    def test_explicit_overrides_suffix(self) -> None:
        m = SymbolMapper(suffix=".r", explicit={"XAUUSD": "GOLD"})
        assert m.to_broker("XAUUSD") == "GOLD"
        assert m.from_broker("GOLD") == "XAUUSD"


class TestMagic:
    def test_deterministic(self) -> None:
        assert _magic_for("alpha") == _magic_for("alpha")
        assert _magic_for("alpha") != _magic_for("beta")

    def test_in_int32_range(self) -> None:
        assert 0 <= _magic_for("x") < 2_000_000_000


class TestMetaTraderBroker:
    async def test_connect_and_submit_market_buy(self) -> None:
        client = MockMT5Client(prices={"EURUSD.r": 1.10})
        broker = MetaTraderBroker(client, symbol_mapper=SymbolMapper(suffix=".r"))
        await broker.connect()
        assert await broker.is_connected()

        oid = await broker.submit_order(_order())
        assert oid  # broker order id returned

        positions = await broker.positions()
        assert len(positions) == 1
        assert positions[0].instrument_id == "EURUSD"  # mapped back to internal id
        assert positions[0].quantity == Decimal("0.1")
        # Recorded as a BUY on the MT5 side.
        assert client.positions_get()[0]["type"] == ORDER_TYPE_BUY

    async def test_sell_maps_to_negative_quantity(self) -> None:
        client = MockMT5Client(prices={"EURUSD": 1.10})
        broker = MetaTraderBroker(client)
        await broker.connect()
        await broker.submit_order(_order(side="sell", qty=0.2))
        positions = await broker.positions()
        assert positions[0].quantity == Decimal("-0.2")
        assert client.positions_get()[0]["type"] == ORDER_TYPE_SELL

    async def test_limit_order_carries_price(self) -> None:
        client = MockMT5Client(prices={"EURUSD": 1.10})
        broker = MetaTraderBroker(client)
        await broker.connect()
        await broker.submit_order(_order(otype="limit", price=1.0850, side="sell"))
        rec = client.positions_get()[0]
        assert rec["type"] == ORDER_TYPE_SELL_LIMIT
        assert rec["price_open"] == 1.0850

    async def test_account_snapshot(self) -> None:
        client = MockMT5Client(balance=100_000.0, prices={"EURUSD": 1.10})
        broker = MetaTraderBroker(client)
        await broker.connect()
        # Open a long, then move price up -> equity rises.
        await broker.submit_order(_order(qty=1.0))
        bal0, _ = broker.account_snapshot()
        assert bal0 == 100_000.0
        client.set_price("EURUSD", 1.12)  # +200 pips on 1 lot (100k) = +2000
        _, eq1 = broker.account_snapshot()
        assert eq1 == pytest.approx(100_000.0 + (1.12 - 1.10) * 100_000.0)

    async def test_order_send_failure_raises(self) -> None:
        class FailingClient(MockMT5Client):
            def order_send(self, _request):  # type: ignore[override]
                return {"retcode": 10004, "order": 0, "deal": 0}

        broker = MetaTraderBroker(FailingClient())
        await broker.connect()
        with pytest.raises(RuntimeError, match="retcode"):
            await broker.submit_order(_order())
