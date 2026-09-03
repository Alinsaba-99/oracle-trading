"""BL-730 — Tests for the always-on paper runner.

Covers:
- Config loading from YAML + CLI flag override semantics.
- One full cycle with a fake clock + injected providers produces
  fills, positions, and equity snapshots.
- 1440-cycle simulated run (24h at 1m bars) without state drift.
- Graceful shutdown (SIGTERM-equivalent) is safe and emits audit.
- Heartbeat cadence respected.
- Noop signal source produces zero intents → no fills, but heartbeats
  + equity snapshots still land.
- ``on_fill`` callback (additive hook) wires intent → fill → store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.paper_orchestrator import OrderIntent
from execution.runner import (
    CycleResult,
    LakePriceProvider,
    NoopSignalSource,
    PaperRunner,
    PaperRunnerConfig,
)
from execution.store import ExecutionStore

# =========================================================================
# Helpers
# =========================================================================


@dataclass
class _RecordingSignalSource:
    """Test double: emits a fixed intent on every call."""

    intent: OrderIntent
    call_count: int = 0
    last_prices: dict[str, Decimal] = field(default_factory=dict)

    async def generate_intents(
        self,
        *,
        symbols: list[str],  # noqa: ARG002
        prices: dict[str, Decimal],
        positions: dict[str, Decimal],  # noqa: ARG002
    ) -> list[OrderIntent]:
        self.call_count += 1
        self.last_prices = dict(prices)
        return [self.intent]


@dataclass
class _StubPriceProvider:
    """Always returns the configured prices (Decimal)."""

    prices: dict[str, Decimal]
    call_count: int = 0

    async def get_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        self.call_count += 1
        return {s: self.prices.get(s, Decimal("0")) for s in symbols}


class _CyclingSignalSource:
    """Buy/Sell SPY on alternate cycles — produces steady-state fills."""

    def __init__(self) -> None:
        self._n = 0

    async def generate_intents(
        self,
        *,
        symbols: list[str],  # noqa: ARG002
        prices: dict[str, Decimal],
        positions: dict[str, Decimal],  # noqa: ARG002
    ) -> list[OrderIntent]:
        self._n += 1
        # Cycle 1 = buy, cycle 2 = sell, … 1440 (even) = sell → flat.
        side = "buy" if self._n % 2 == 1 else "sell"
        return [
            OrderIntent(
                instrument_id="SPY",
                side=side,
                quantity=Decimal("1"),
                backtest_price=prices["SPY"],
                strategy="test",
            )
        ]


class _CyclingPriceProvider:
    """SPY oscillates 100..109, QQQ drifts up — deterministic per cycle."""

    def __init__(self) -> None:
        self._n = 0

    async def get_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        self._n += 1
        spy = Decimal(str(100 + (self._n % 10)))
        qqq = Decimal(str(200 + (self._n // 10)))
        return {s: spy if s == "SPY" else qqq for s in symbols}


def _config(tmp_path: Path, **overrides: object) -> PaperRunnerConfig:
    base: dict[str, object] = {
        "db_path": str(tmp_path / "runner.db"),
        "symbols": ["SPY", "QQQ"],
        "tick_interval_s": 0.001,
        "heartbeat_cycle_s": 1,
        "starting_cash": Decimal("100000"),
    }
    base.update(overrides)
    return PaperRunnerConfig(**base)  # type: ignore[arg-type]


def _zero_slippage_broker() -> PaperBroker:
    """PaperBroker with deterministic fills at the requested price."""
    return PaperBroker(
        BrokerConfig(
            paper_spread_bps=0,
            paper_slippage_bps=0,
            paper_partial_fill_prob=0.0,
            paper_latency_ms=0,
        )
    )


# =========================================================================
# Configuration loading
# =========================================================================


class TestConfigFromYaml:
    def test_minimal_yaml_loads_with_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "paper.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "db_path": str(tmp_path / "store.db"),
                    "symbols": ["SPY", "AAPL"],
                    "tick_interval_s": 30.0,
                    "starting_cash": 250000,
                }
            )
        )
        cfg = PaperRunnerConfig.from_yaml(path)
        assert cfg.db_path == str(tmp_path / "store.db")
        assert cfg.symbols == ["SPY", "AAPL"]
        assert cfg.tick_interval_s == 30.0
        assert cfg.starting_cash == Decimal("250000")
        # Unspecified fields fall back to defaults.
        assert cfg.heartbeat_cycle_s == 10
        assert cfg.timeframe == "1m"

    def test_unknown_keys_are_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "paper.yaml"
        path.write_text(yaml.safe_dump({"future_field": "ignored", "tick_interval_s": 5.0}))
        cfg = PaperRunnerConfig.from_yaml(path)
        assert cfg.tick_interval_s == 5.0

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PaperRunnerConfig.from_yaml(tmp_path / "nope.yaml")

    def test_root_not_mapping_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- 1\n- 2\n")
        with pytest.raises(ValueError, match="Expected mapping"):
            PaperRunnerConfig.from_yaml(path)


# =========================================================================
# One-cycle behaviour
# =========================================================================


class TestOneCycle:
    @pytest.mark.asyncio
    async def test_cycle_noop_signal_emits_heartbeat_and_snapshot(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        broker = _zero_slippage_broker()
        prices = _StubPriceProvider({"SPY": Decimal("100"), "QQQ": Decimal("200")})
        runner = PaperRunner(
            cfg, broker=broker, price_provider=prices, signal_source=NoopSignalSource()
        )
        await runner.setup()
        try:
            result = await runner._run_one_cycle()
            assert isinstance(result, CycleResult)
            assert result.intents_submitted == 0
            assert result.fills == []
            assert result.equity == Decimal("100000")  # no positions

            store = runner._store
            assert store is not None
            assert store.latest_equity() is not None
            assert store.latest_heartbeat() is not None
            # heartbeat_cycle_s=1 → every cycle emits a heartbeat.
            beats = store.list_audit(kind="heartbeat")
            assert len(beats) == 1
        finally:
            await runner.shutdown()

    @pytest.mark.asyncio
    async def test_cycle_with_intent_emits_fill_and_order(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        broker = _zero_slippage_broker()
        prices = _StubPriceProvider({"SPY": Decimal("100"), "QQQ": Decimal("200")})
        signal = _RecordingSignalSource(
            intent=OrderIntent(
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("10"),
                backtest_price=Decimal("99"),
                strategy="lane_b_composite",
            )
        )
        runner = PaperRunner(cfg, broker=broker, price_provider=prices, signal_source=signal)
        await runner.setup()
        try:
            result = await runner._run_one_cycle()
            assert result.intents_submitted == 1
            assert len(result.fills) == 1
            store = runner._store
            assert store is not None
            assert store.count_fills() == 1
            assert store.count_fills(instrument_id="SPY") == 1
            assert store.get_position("SPY") is not None
            # Equity reflects SPY position: 10 * 100 = 1000.
            assert result.equity == Decimal("101000")
            assert signal.call_count == 1
        finally:
            await runner.shutdown()


# =========================================================================
# Graceful shutdown mid-cycle
# =========================================================================


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_request_stop_finishes_cycle_clean(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path, tick_interval_s=10.0)
        broker = _zero_slippage_broker()
        prices = _StubPriceProvider({"SPY": Decimal("100")})
        runner = PaperRunner(
            cfg, broker=broker, price_provider=prices, signal_source=NoopSignalSource()
        )
        await runner.setup()
        runner.request_stop()
        try:
            code = await runner.run()
            assert code == 0
        finally:
            await runner.shutdown()
        # ``run`` calls shutdown() internally; re-open the store to
        # verify the shutdown audit row landed durably.
        store = ExecutionStore(cfg.db_path)
        try:
            kinds = {e.kind for e in store.list_audit()}
            assert "shutdown" in kinds
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        broker = _zero_slippage_broker()
        runner = PaperRunner(cfg, broker=broker, price_provider=_StubPriceProvider({}))
        await runner.setup()
        await runner.shutdown()
        await runner.shutdown()  # must not raise


# =========================================================================
# 1440-cycle simulated run — driven directly (no sleep loop)
# =========================================================================


class TestAcceleratedRun:
    @pytest.mark.asyncio
    async def test_1440_cycles_no_drift(self, tmp_path: Path) -> None:
        """1440 cycles (24h at 1m bars). Positions stay consistent with
        fills recorded (no orphan positions, equity curve has 1440 points).
        """
        cfg = _config(tmp_path, symbols=["SPY", "QQQ"], heartbeat_cycle_s=10)
        broker = _zero_slippage_broker()
        runner = PaperRunner(
            cfg,
            broker=broker,
            price_provider=_CyclingPriceProvider(),
            signal_source=_CyclingSignalSource(),
        )
        await runner.setup()
        try:
            for _ in range(1440):
                await runner._run_one_cycle()

            # Re-open the store fresh to verify durable state.
            fresh = ExecutionStore(cfg.db_path)
            try:
                fills = fresh.list_fills(instrument_id="SPY", limit=10_000)
                # _CyclingSignalSource emits buy odd cycles, sell even.
                # 1440 cycles → 720 buys + 720 sells → flat (net_qty == 0).
                net_qty = sum(int(f.quantity) * (1 if f.side == "buy" else -1) for f in fills)
                assert net_qty == 0
                # Heartbeats: 1440 / 10 → 144 heartbeats (cycle 10, 20, ..., 1440).
                beats = fresh.list_audit(kind="heartbeat")
                assert len(beats) == 144
                # Equity curve has exactly 1440 points (one per cycle).
                assert len(fresh.equity_curve()) == 1440
                # Position upserts: SPY is flat at 0; QQQ never traded.
                pos = fresh.get_position("SPY")
                assert pos is not None
                assert pos.quantity == Decimal("0")
            finally:
                fresh.close()
        finally:
            await runner.shutdown()


# =========================================================================
# Heartbeat cadence
# =========================================================================


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_every_n_cycles(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path, heartbeat_cycle_s=3)
        broker = _zero_slippage_broker()
        prices = _StubPriceProvider({"SPY": Decimal("100")})
        runner = PaperRunner(
            cfg, broker=broker, price_provider=prices, signal_source=NoopSignalSource()
        )
        await runner.setup()
        try:
            for _ in range(7):
                await runner._run_one_cycle()
            store = runner._store
            assert store is not None
            beats = store.list_audit(kind="heartbeat")
            # 7 cycles / heartbeat_cycle_s=3 → cycle 3 and 6 emit → 2 beats.
            assert len(beats) == 2
        finally:
            await runner.shutdown()


# =========================================================================
# LakePriceProvider — fallback to 0 when parquet is missing
# =========================================================================


class TestLakePriceProvider:
    @pytest.mark.asyncio
    async def test_missing_data_returns_zero(self, tmp_path: Path) -> None:
        pp = LakePriceProvider(lake_root=tmp_path / "nope", legacy_root=tmp_path / "nope")
        prices = await pp.get_prices(["SPY", "QQQ"])
        assert prices == {"SPY": Decimal("0"), "QQQ": Decimal("0")}


# =========================================================================
# on_fill callback wiring (additive hook on PaperOrchestrator)
# =========================================================================


class TestOnFillCallback:
    @pytest.mark.asyncio
    async def test_callback_receives_intent_and_fill(self, tmp_path: Path) -> None:
        from execution.paper_orchestrator import PaperOrchestrator, SlippageLedger

        ledger = SlippageLedger(tmp_path / "slip.jsonl")
        orch = PaperOrchestrator(_zero_slippage_broker(), ledger)
        captured: list[tuple[OrderIntent, Any, int]] = []

        def _cb(intent: OrderIntent, fill: Any, bps: int) -> None:
            captured.append((intent, fill, bps))

        intents = [
            OrderIntent(
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("5"),
                backtest_price=Decimal("100"),
            )
        ]
        fills = await orch.run_once(intents, {"SPY": Decimal("101")}, on_fill=_cb)
        assert len(fills) == 1
        assert len(captured) == 1
        intent, fill, bps = captured[0]
        assert intent.instrument_id == "SPY"
        assert fill.price == Decimal("101")
        # (101-100)/100*10000 = 100 bps.
        assert bps == 100

    @pytest.mark.asyncio
    async def test_callback_failure_does_not_break_orchestrator(self, tmp_path: Path) -> None:
        from execution.paper_orchestrator import PaperOrchestrator, SlippageLedger

        ledger = SlippageLedger(tmp_path / "slip.jsonl")
        orch = PaperOrchestrator(_zero_slippage_broker(), ledger)

        def _boom(intent: OrderIntent, fill: Any, bps: int) -> None:  # noqa: ARG001
            raise RuntimeError("callback explosion")

        # Orchestrator must NOT propagate the callback exception.
        fills = await orch.run_once(
            [
                OrderIntent(
                    instrument_id="SPY",
                    side="buy",
                    quantity=Decimal("1"),
                    backtest_price=Decimal("100"),
                )
            ],
            {"SPY": Decimal("100")},
            on_fill=_boom,
        )
        assert len(fills) == 1
        # Legacy slippage ledger still got the record.
        assert len(ledger.read_all()) == 1


# =========================================================================
# Audit at lifecycle boundaries
# =========================================================================


class TestLifecycleAudit:
    @pytest.mark.asyncio
    async def test_shutdown_emits_audit(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        runner = PaperRunner(
            cfg, broker=_zero_slippage_broker(), price_provider=_StubPriceProvider({})
        )
        await runner.setup()
        await runner.shutdown()
        store = ExecutionStore(cfg.db_path)
        try:
            kinds = {e.kind for e in store.list_audit()}
            assert "shutdown" in kinds
        finally:
            store.close()


# =========================================================================
# PaperOrchestrator on_fill backward-compat (no callback → legacy path)
# =========================================================================


class TestOnFillBackwardCompat:
    @pytest.mark.asyncio
    async def test_run_once_without_callback_still_works(self, tmp_path: Path) -> None:
        from execution.paper_orchestrator import PaperOrchestrator, SlippageLedger

        ledger = SlippageLedger(tmp_path / "slip.jsonl")
        orch = PaperOrchestrator(_zero_slippage_broker(), ledger)
        fills = await orch.run_once(
            [
                OrderIntent(
                    instrument_id="SPY",
                    side="buy",
                    quantity=Decimal("1"),
                    backtest_price=Decimal("100"),
                )
            ],
            {"SPY": Decimal("100")},
        )
        assert len(fills) == 1
        assert len(ledger.read_all()) == 1


# =========================================================================
# BL-734 — alerting wiring
# =========================================================================


@dataclass
class _RecordingAlerter:
    """Test double for the AlertSink protocol."""

    fills: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    kill_switches: list[str] = field(default_factory=list)
    heartbeats_missed: list[str] = field(default_factory=list)

    def emit_fill(
        self,
        *,
        order_id: str,
        symbol: str,
        side: str,  # noqa: ARG002
        quantity: float,
        price: float,  # noqa: ARG002
        slippage_bps: float | None = None,  # noqa: ARG002
        strategy_id: str = "",  # noqa: ARG002
    ) -> object:
        self.fills.append({"order_id": order_id, "symbol": symbol, "quantity": quantity})
        return None

    def emit_error(self, exc: BaseException, *, context: str = "") -> object:
        self.errors.append(f"{exc!r} {context}")
        return None

    def emit_kill_switch(self, reason: str, *, actor: str = "") -> object:  # noqa: ARG002
        self.kill_switches.append(reason)
        return None

    def emit_heartbeat_missed(self, since: str, *, threshold_s: float) -> object:  # noqa: ARG002
        self.heartbeats_missed.append(since)
        return None


class TestAlertingWiring:
    @pytest.mark.asyncio
    async def test_fill_emits_alert(self, tmp_path: Path) -> None:
        cfg = _config(tmp_path)
        alerter = _RecordingAlerter()
        signal = _RecordingSignalSource(
            intent=OrderIntent(
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("10"),
                backtest_price=Decimal("99"),
                strategy="lane_b_composite",
            )
        )
        runner = PaperRunner(
            cfg,
            broker=_zero_slippage_broker(),
            price_provider=_StubPriceProvider({"SPY": Decimal("100")}),
            signal_source=signal,
            alerter=alerter,
        )
        await runner.setup()
        try:
            await runner._run_one_cycle()
            assert len(alerter.fills) == 1
            assert alerter.fills[0]["symbol"] == "SPY"
        finally:
            await runner.shutdown()

    @pytest.mark.asyncio
    async def test_no_alerter_is_fine(self, tmp_path: Path) -> None:
        """Backward compat: alerter=None keeps the runner fully functional."""
        cfg = _config(tmp_path)
        runner = PaperRunner(
            cfg,
            broker=_zero_slippage_broker(),
            price_provider=_StubPriceProvider({"SPY": Decimal("100")}),
            signal_source=NoopSignalSource(),
        )
        await runner.setup()
        try:
            result = await runner._run_one_cycle()
            assert result.cycle_index == 1
        finally:
            await runner.shutdown()

    @pytest.mark.asyncio
    async def test_three_failures_emit_kill_switch(self, tmp_path: Path) -> None:
        """3 consecutive cycle failures → kill-switch alert + exit code 2."""
        cfg = _config(tmp_path)
        cfg.tick_interval_s = 0.001
        alerter = _RecordingAlerter()

        class _ExplodingProvider:
            async def get_prices(self, symbols: list[str]) -> dict[str, Decimal]:  # noqa: ARG002
                raise RuntimeError("lake exploded")

        runner = PaperRunner(
            cfg,
            price_provider=_ExplodingProvider(),
            signal_source=NoopSignalSource(),
            alerter=alerter,
        )
        await runner.setup()
        code = await runner.run()
        assert code == 2
        assert len(alerter.kill_switches) == 1
        assert len(alerter.errors) >= 3

    @pytest.mark.asyncio
    async def test_stale_heartbeat_alerts(self, tmp_path: Path) -> None:
        """A persisted heartbeat older than the threshold triggers the alert."""
        from dataclasses import replace
        from datetime import UTC, datetime, timedelta

        cfg = _config(tmp_path)
        cfg.heartbeat_timeout_s = 60.0
        alerter = _RecordingAlerter()
        runner = PaperRunner(
            cfg,
            broker=_zero_slippage_broker(),
            price_provider=_StubPriceProvider({"SPY": Decimal("100")}),
            signal_source=NoopSignalSource(),
            alerter=alerter,
        )
        await runner.setup()
        try:
            store = runner._store
            assert store is not None
            old_ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
            store.heartbeat(cycle_index=0, payload={"ts": old_ts})
            original = store.latest_heartbeat

            def _stale() -> Any:
                ev = original()
                if ev is None:
                    return None
                return replace(ev, ts=old_ts)

            store.latest_heartbeat = _stale  # type: ignore[method-assign]
            await runner._run_one_cycle()
            assert len(alerter.heartbeats_missed) == 1
        finally:
            await runner.shutdown()
