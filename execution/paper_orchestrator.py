"""Step 4 Opzione C — Paper trading orchestrator.

Bridges backtest signal functions to the PaperBroker. For each signal
emitted by a strategy, submits a paper order at the current market price
and records the slippage vs the backtest's assumed entry price.

MVP scope (this file):
  - PaperOrchestrator class
  - SlippageLedger (JSONL persister)
  - OrderIntent dataclass (signal function output)

Out of MVP scope (next iterations):
  - Live price feed (yfinance delayed 15min / IBKR Gateway delayed)
  - Lane B / Lane D signal adapters
  - systemd timer / cron
  - Real-time loop (this MVP is single-shot run_once)

Usage:
  from execution.paper_orchestrator import PaperOrchestrator, OrderIntent
  from execution.brokers.paper import PaperBroker

  broker = PaperBroker()
  orch = PaperOrchestrator(broker, ledger_path=Path("data/lake/paper_ledger/today.jsonl"))
  intents = [OrderIntent(instrument_id="SPY", side="buy", quantity=Decimal("10"),
                         backtest_price=Decimal("450.00"))]
  await orch.run_once(intents, market_prices={"SPY": Decimal("451.50")})
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from execution.brokers.paper import PaperBroker
from execution.brokers.types import BrokerFill, BrokerOrder


@dataclass(frozen=True)
class OrderIntent:
    """One signal-emitted order intent.

    Attributes
    ----------
    instrument_id : str
        Ticker / contract id (e.g. "SPY", "ES=1FUT").
    side : str
        "buy" | "sell".
    quantity : Decimal
        Number of shares / contracts.
    backtest_price : Decimal
        The entry price assumed by the backtest when this signal was generated.
        Used as the reference for slippage computation.
    strategy : str
        Strategy name (e.g. "lane_b_composite", "lane_d_vrp").
    meta : dict
        Free-form metadata (signal_score, screen_date, etc).
    """

    instrument_id: str
    side: str
    quantity: Decimal
    backtest_price: Decimal
    strategy: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SlippageRecord:
    """One fill → one slippage record persisted to JSONL."""

    timestamp: str
    strategy: str
    instrument_id: str
    side: str
    quantity: Decimal
    backtest_price: Decimal
    paper_fill_price: Decimal
    slippage_bps: int  # signed: +100 = filled 1% worse than backtest assumed
    broker_order_id: str
    meta: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "strategy": self.strategy,
                "instrument_id": self.instrument_id,
                "side": self.side,
                "quantity": str(self.quantity),
                "backtest_price": str(self.backtest_price),
                "paper_fill_price": str(self.paper_fill_price),
                "slippage_bps": self.slippage_bps,
                "broker_order_id": self.broker_order_id,
                "meta": self.meta,
            },
            default=str,
        )


class SlippageLedger:
    """Append-only JSONL ledger for slippage records."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: SlippageRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.to_json() + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows


class PaperOrchestrator:
    """Drives signal → paper order → fill → slippage ledger.

    The orchestrator is single-shot: callers invoke ``run_once`` with the
    list of order intents for the current evaluation step. The real-time
    loop (cron / systemd / sleep) is layered on top in a future iteration.
    """

    def __init__(self, broker: PaperBroker, ledger: SlippageLedger) -> None:
        self.broker = broker
        self.ledger = ledger

    async def run_once(
        self, intents: list[OrderIntent], market_prices: dict[str, Decimal]
    ) -> list[BrokerFill]:
        """Submit each intent as a market order at the current price.

        For each intent:
        1. Seed the PaperBroker's current price via ``on_price_update``.
        2. Submit a market order.
        3. Capture fills.
        4. Compute slippage vs ``backtest_price`` and persist to ledger.

        Returns the list of fills produced.
        """
        fills: list[BrokerFill] = []
        for intent in intents:
            price = market_prices.get(intent.instrument_id)
            if price is None:
                # Skip — no market price available for this instrument.
                continue
            await self.broker.on_price_update(price)
            order = BrokerOrder(
                broker_order_id="",
                local_order_id="",
                namespaced_id="",
                instrument_id=intent.instrument_id,
                side=intent.side,
                quantity=intent.quantity,
                order_type="market",
            )
            broker_id = await self.broker.submit_order(order)
            new_fills = await self.broker.get_fills()
            for fill in new_fills:
                if fill.broker_order_id == broker_id:
                    fills.append(fill)
                    slippage_bps = self._slippage_bps(
                        intent.backtest_price, fill.price, intent.side
                    )
                    record = SlippageRecord(
                        timestamp=datetime.now(UTC).isoformat(),
                        strategy=intent.strategy,
                        instrument_id=intent.instrument_id,
                        side=intent.side,
                        quantity=fill.quantity,
                        backtest_price=intent.backtest_price,
                        paper_fill_price=fill.price,
                        slippage_bps=slippage_bps,
                        broker_order_id=broker_id,
                        meta=intent.meta,
                    )
                    self.ledger.append(record)
        return fills

    @staticmethod
    def _slippage_bps(backtest_price: Decimal, fill_price: Decimal, side: str) -> int:
        """Signed slippage in basis points vs the backtest-assumed price.

        Positive = filled WORSE than backtest assumed (cost).
        Negative = filled BETTER than backtest assumed (gift).

        For a buy: fill_price > backtest → positive slippage (paid more).
        For a sell: fill_price < backtest → positive slippage (received less).
        """
        if backtest_price == 0:
            return 0
        raw = (fill_price - backtest_price) / backtest_price
        if side.lower() == "sell":
            raw = -raw
        return round(float(raw) * 10_000)
