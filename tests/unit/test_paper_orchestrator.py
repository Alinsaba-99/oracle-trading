"""Tests for Step 4 Opzione C — PaperOrchestrator + SlippageLedger.

Covers MVP scope:
- SlippageLedger append + read_all round-trip
- PaperOrchestrator.run_once:
  - Market order fills at current price
  - Slippage record persisted with correct signed bps
  - Buy above backtest price → positive slippage (cost)
  - Sell below backtest price → positive slippage (cost)
  - Sell above backtest price → negative slippage (gift)
  - Intent without market price → skipped (no fill, no record)
- _slippage_bps edge cases (zero backtest price)
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.paper_orchestrator import (
    OrderIntent,
    PaperOrchestrator,
    SlippageLedger,
    SlippageRecord,
)


@pytest.fixture
def ledger(tmp_path: Path) -> SlippageLedger:
    return SlippageLedger(tmp_path / "slippage.jsonl")


@pytest.fixture
def broker() -> PaperBroker:
    # No spread / slippage / partial fills — deterministic fills for slippage math.
    return PaperBroker(
        BrokerConfig(
            paper_spread_bps=0,
            paper_slippage_bps=0,
            paper_partial_fill_prob=0.0,
            paper_latency_ms=0,
        )
    )


class TestSlippageLedger:
    def test_append_and_read_round_trip(self, ledger: SlippageLedger) -> None:
        record = SlippageRecord(
            timestamp="2026-08-17T10:00:00+00:00",
            strategy="lane_b_composite",
            instrument_id="SPY",
            side="buy",
            quantity=Decimal("10"),
            backtest_price=Decimal("450.00"),
            paper_fill_price=Decimal("451.50"),
            slippage_bps=33,
            broker_order_id="paper_1",
            meta={"screen_date": "2026-08-15"},
        )
        ledger.append(record)
        rows = ledger.read_all()
        assert len(rows) == 1
        assert rows[0]["instrument_id"] == "SPY"
        assert rows[0]["slippage_bps"] == 33
        assert rows[0]["quantity"] == "10"

    def test_read_all_empty_when_no_file(self, tmp_path: Path) -> None:
        ledger = SlippageLedger(tmp_path / "does-not-exist.jsonl")
        assert ledger.read_all() == []

    def test_append_creates_parent_dir(self, tmp_path: Path) -> None:
        ledger = SlippageLedger(tmp_path / "deep" / "nested" / "ledger.jsonl")
        record = SlippageRecord(
            timestamp="2026-08-17T10:00:00+00:00",
            strategy="test",
            instrument_id="X",
            side="buy",
            quantity=Decimal("1"),
            backtest_price=Decimal("100"),
            paper_fill_price=Decimal("100"),
            slippage_bps=0,
            broker_order_id="paper_1",
            meta={},
        )
        ledger.append(record)
        assert ledger.path.exists()


class TestSlippageBps:
    def test_buy_above_backtest_positive(self) -> None:
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("100.00"), fill_price=Decimal("101.00"), side="buy"
        )
        assert bps == 100  # paid 1% more

    def test_buy_below_backtest_negative(self) -> None:
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("100.00"), fill_price=Decimal("99.00"), side="buy"
        )
        assert bps == -100  # paid 1% less (gift)

    def test_sell_below_backtest_positive(self) -> None:
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("100.00"), fill_price=Decimal("99.00"), side="sell"
        )
        assert bps == 100  # received 1% less (cost)

    def test_sell_above_backtest_negative(self) -> None:
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("100.00"), fill_price=Decimal("101.00"), side="sell"
        )
        assert bps == -100  # received 1% more (gift)

    def test_zero_backtest_price_returns_zero(self) -> None:
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("0"), fill_price=Decimal("100"), side="buy"
        )
        assert bps == 0

    def test_rounding_to_nearest_bps(self) -> None:
        # 0.0050% = 0.5 bps → rounds to 1 (Python banker's rounding uses ROUND_HALF_EVEN
        # via round() on .5; our impl uses round() which goes to nearest even → 0).
        # Use a clearly >0.5 bps case to test positive rounding.
        bps = PaperOrchestrator._slippage_bps(
            backtest_price=Decimal("10000"), fill_price=Decimal("10000.60"), side="buy"
        )
        assert bps == 1  # 0.0060% = 0.6 bps → rounds to 1


class TestPaperOrchestratorRunOnce:
    async def test_buy_intent_fills_and_records_slippage(self, ledger: SlippageLedger) -> None:
        broker = PaperBroker(
            BrokerConfig(
                paper_spread_bps=0,
                paper_slippage_bps=0,
                paper_partial_fill_prob=0.0,
                paper_latency_ms=0,
            )
        )
        await broker.connect()
        try:
            orch = PaperOrchestrator(broker, ledger)
            intents = [
                OrderIntent(
                    instrument_id="SPY",
                    side="buy",
                    quantity=Decimal("10"),
                    backtest_price=Decimal("450.00"),
                    strategy="lane_b_composite",
                    meta={"screen_date": "2026-08-15"},
                )
            ]
            fills = await orch.run_once(intents, market_prices={"SPY": Decimal("451.50")})
            assert len(fills) == 1
            assert fills[0].price == Decimal("451.50")
            rows = ledger.read_all()
            assert len(rows) == 1
            assert rows[0]["slippage_bps"] == 33  # (451.50-450)/450 * 10000 ≈ 33.33 → 33
        finally:
            await broker.disconnect()

    async def test_sell_intent_negative_slippage_when_better(self, ledger: SlippageLedger) -> None:
        broker = PaperBroker(
            BrokerConfig(
                paper_spread_bps=0,
                paper_slippage_bps=0,
                paper_partial_fill_prob=0.0,
                paper_latency_ms=0,
            )
        )
        await broker.connect()
        try:
            orch = PaperOrchestrator(broker, ledger)
            intents = [
                OrderIntent(
                    instrument_id="AAPL",
                    side="sell",
                    quantity=Decimal("20"),
                    backtest_price=Decimal("200.00"),
                    strategy="lane_b_composite",
                )
            ]
            fills = await orch.run_once(intents, market_prices={"AAPL": Decimal("202.00")})
            assert len(fills) == 1
            rows = ledger.read_all()
            assert rows[0]["slippage_bps"] == -100  # sold 1% higher than backtest
        finally:
            await broker.disconnect()

    async def test_intent_without_market_price_skipped(self, ledger: SlippageLedger) -> None:
        broker = PaperBroker(
            BrokerConfig(
                paper_spread_bps=0,
                paper_slippage_bps=0,
                paper_partial_fill_prob=0.0,
                paper_latency_ms=0,
            )
        )
        await broker.connect()
        try:
            orch = PaperOrchestrator(broker, ledger)
            intents = [
                OrderIntent(
                    instrument_id="NVDA",
                    side="buy",
                    quantity=Decimal("5"),
                    backtest_price=Decimal("800.00"),
                )
            ]
            fills = await orch.run_once(intents, market_prices={})
            assert fills == []
            assert ledger.read_all() == []
        finally:
            await broker.disconnect()

    async def test_multiple_intents_in_one_run(self, ledger: SlippageLedger) -> None:
        broker = PaperBroker(
            BrokerConfig(
                paper_spread_bps=0,
                paper_slippage_bps=0,
                paper_partial_fill_prob=0.0,
                paper_latency_ms=0,
            )
        )
        await broker.connect()
        try:
            orch = PaperOrchestrator(broker, ledger)
            intents = [
                OrderIntent(
                    instrument_id="SPY",
                    side="buy",
                    quantity=Decimal("10"),
                    backtest_price=Decimal("450"),
                ),
                OrderIntent(
                    instrument_id="QQQ",
                    side="buy",
                    quantity=Decimal("5"),
                    backtest_price=Decimal("380"),
                ),
            ]
            fills = await orch.run_once(
                intents, market_prices={"SPY": Decimal("450.90"), "QQQ": Decimal("380.76")}
            )
            assert len(fills) == 2
            rows = ledger.read_all()
            assert len(rows) == 2
            # Both buys above backtest → both positive slippage
            assert rows[0]["slippage_bps"] > 0
            assert rows[1]["slippage_bps"] > 0
        finally:
            await broker.disconnect()

    async def test_ledger_persists_across_runs(self, ledger: SlippageLedger) -> None:
        broker = PaperBroker(
            BrokerConfig(
                paper_spread_bps=0,
                paper_slippage_bps=0,
                paper_partial_fill_prob=0.0,
                paper_latency_ms=0,
            )
        )
        await broker.connect()
        try:
            orch = PaperOrchestrator(broker, ledger)
            intent = OrderIntent(
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("1"),
                backtest_price=Decimal("100"),
            )
            await orch.run_once(intents=[intent], market_prices={"SPY": Decimal("100")})
            await orch.run_once(intents=[intent], market_prices={"SPY": Decimal("101")})
            rows = ledger.read_all()
            assert len(rows) == 2
        finally:
            await broker.disconnect()
