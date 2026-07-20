"""Tests for execution.session_guards — M32-015..019 resilience drills."""

from __future__ import annotations

from decimal import Decimal

import pytest

from execution.session_guards import (
    AlertLevel,
    CircuitState,
    ExtremeMarketConference,
    RiskAlertBus,
    SignalProviderCircuit,
    StaleFeedDetector,
)

# =========================================================================
# Fake clock for deterministic tests
# =========================================================================


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# =========================================================================
# M32-015 / M32-016 — SignalProviderCircuit
# =========================================================================


class TestSignalProviderCircuit:
    """LLM (M32-015) and Eliza (M32-016) outages share the same pattern."""

    async def test_closed_by_default(self) -> None:
        circuit = SignalProviderCircuit(name="llm")
        assert circuit.state == CircuitState.CLOSED
        assert circuit.is_available()

    async def test_success_returns_result(self) -> None:
        circuit = SignalProviderCircuit(name="llm")

        async def ok() -> str:
            return "BUY"

        assert await circuit.call(ok) == "BUY"
        assert circuit.state == CircuitState.CLOSED
        assert circuit.consecutive_failures == 0

    async def test_failure_returns_none(self) -> None:
        circuit = SignalProviderCircuit(name="llm", failure_threshold=3)

        async def boom() -> str:
            raise ConnectionError("llm timeout")

        assert await circuit.call(boom) is None
        assert circuit.consecutive_failures == 1
        assert circuit.state == CircuitState.CLOSED  # threshold not reached

    async def test_trips_open_after_threshold(self) -> None:
        circuit = SignalProviderCircuit(name="llm", failure_threshold=3)

        async def boom() -> str:
            raise ConnectionError("llm down")

        for _ in range(3):
            await circuit.call(boom)
        assert circuit.state == CircuitState.OPEN
        assert not circuit.is_available()

    async def test_open_short_circuits_without_calling(self) -> None:
        circuit = SignalProviderCircuit(name="llm", failure_threshold=1)
        call_count = 0

        async def counting_boom() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("llm down")

        await circuit.call(counting_boom)
        assert circuit.state == CircuitState.OPEN

        # Subsequent calls return None without invoking fn.
        assert await circuit.call(counting_boom) is None
        assert call_count == 1  # not called again

    async def test_half_open_after_recovery_timeout(self) -> None:
        clock = FakeClock()
        circuit = SignalProviderCircuit(
            name="llm", failure_threshold=1, recovery_timeout_s=10.0, clock=clock
        )

        async def boom() -> str:
            raise ConnectionError("llm down")

        await circuit.call(boom)
        assert circuit.state == CircuitState.OPEN

        clock.advance(5)
        assert circuit.state == CircuitState.OPEN  # not yet

        clock.advance(6)
        assert circuit.state == CircuitState.HALF_OPEN  # type: ignore[comparison-overlap]
        assert circuit.is_available()

    async def test_closes_on_success_after_half_open(self) -> None:
        clock = FakeClock()
        circuit = SignalProviderCircuit(
            name="llm", failure_threshold=1, recovery_timeout_s=10.0, clock=clock
        )

        async def boom() -> str:
            raise ConnectionError("llm down")

        async def ok() -> str:
            return "BUY"

        await circuit.call(boom)
        clock.advance(11)
        assert circuit.state == CircuitState.HALF_OPEN

        assert await circuit.call(ok) == "BUY"
        assert circuit.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]
        assert circuit.consecutive_failures == 0

    async def test_half_open_failure_reopens(self) -> None:
        clock = FakeClock()
        circuit = SignalProviderCircuit(
            name="llm", failure_threshold=1, recovery_timeout_s=10.0, clock=clock
        )

        async def boom() -> str:
            raise ConnectionError("llm down")

        await circuit.call(boom)
        clock.advance(11)
        assert circuit.state == CircuitState.HALF_OPEN

        # Probe fails → back to OPEN.
        assert await circuit.call(boom) is None
        assert circuit.state == CircuitState.OPEN  # type: ignore[comparison-overlap]

    async def test_eliza_outage_independent_of_llm(self) -> None:
        """Two circuits (llm + eliza) are independent."""
        llm = SignalProviderCircuit(name="llm", failure_threshold=1)
        eliza = SignalProviderCircuit(name="eliza", failure_threshold=1)

        async def boom() -> str:
            raise ConnectionError("down")

        await llm.call(boom)
        assert llm.state == CircuitState.OPEN
        assert eliza.state == CircuitState.CLOSED  # unaffected

    async def test_manual_reset(self) -> None:
        circuit = SignalProviderCircuit(name="llm", failure_threshold=1)

        async def boom() -> str:
            raise ConnectionError("down")

        await circuit.call(boom)
        assert circuit.state == CircuitState.OPEN
        circuit.reset()
        assert circuit.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]


# =========================================================================
# M32-017 — StaleFeedDetector
# =========================================================================


class TestStaleFeedDetector:
    def test_stale_when_never_ticked(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        assert detector.is_stale()

    def test_not_stale_immediately_after_tick(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        detector.on_tick()
        assert not detector.is_stale()

    def test_stale_after_timeout(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        detector.on_tick()
        clock.advance(6)
        assert detector.is_stale()

    def test_not_stale_within_timeout(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        detector.on_tick()
        clock.advance(3)
        assert not detector.is_stale()

    def test_tick_refreshes_heartbeat(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        detector.on_tick()
        clock.advance(4)
        detector.on_tick()  # refresh
        clock.advance(4)
        assert not detector.is_stale()  # only 4s since refresh

    def test_time_since_last_tick(self) -> None:
        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        assert detector.time_since_last_tick() is None
        detector.on_tick()
        clock.advance(2.5)
        assert detector.time_since_last_tick() == pytest.approx(2.5)


# =========================================================================
# M32-018 — RiskAlertBus
# =========================================================================


class _FakeBreach:
    def __init__(self, severity: str, type_: str = "daily_loss", message: str = "") -> None:
        self.severity = severity
        self.type = type_
        self.message = message or f"{type_} breach"


class TestRiskAlertBus:
    def test_soft_breach_emits_warning(self) -> None:
        bus = RiskAlertBus()
        alerts = bus.ingest_breaches([_FakeBreach("soft")])
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert bus.can_submit()  # soft doesn't block

    def test_hard_breach_emits_critical_and_blocks(self) -> None:
        bus = RiskAlertBus()
        alerts = bus.ingest_breaches([_FakeBreach("hard")])
        assert alerts[0].level == AlertLevel.CRITICAL
        assert not bus.can_submit()
        assert bus.awaiting_ack

    def test_acknowledge_restores_submissions(self) -> None:
        bus = RiskAlertBus()
        bus.ingest_breaches([_FakeBreach("hard")])
        assert not bus.can_submit()
        bus.acknowledge()
        assert bus.can_submit()
        assert not bus.awaiting_ack

    def test_multiple_breaches_accumulate(self) -> None:
        bus = RiskAlertBus()
        bus.ingest_breaches(
            [_FakeBreach("soft", "daily_loss"), _FakeBreach("hard", "overall_loss")]
        )
        assert len(bus.alerts) == 2
        assert not bus.can_submit()

    def test_alert_details_preserved(self) -> None:
        bus = RiskAlertBus()
        bus.ingest_breaches([_FakeBreach("hard", "daily_loss", "daily loss hit")])
        alert = bus.alerts[0]
        assert alert.code == "daily_loss"
        assert alert.message == "daily loss hit"
        assert alert.details["severity"] == "hard"


# =========================================================================
# M32-019 — ExtremeMarketConference
# =========================================================================


class TestExtremeMarketConference:
    def test_normal_market_no_conference(self) -> None:
        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.05"), flash_window_ticks=3)
        for price in [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103")]:
            assert conf.on_tick(price) is None
        assert not conf.in_conference
        assert conf.can_submit()

    def test_flash_move_triggers_conference(self) -> None:
        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.03"), flash_window_ticks=3)
        for price in [Decimal("100"), Decimal("100.5"), Decimal("101")]:
            assert conf.on_tick(price) is None
        # +5% in one tick from anchor 100 → exceeds 3%.
        event = conf.on_tick(Decimal("105"))
        assert event is not None
        assert event.kind == "flash_move"
        assert conf.in_conference
        assert not conf.can_submit()

    def test_conference_persists_until_ack(self) -> None:
        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.03"), flash_window_ticks=3)
        for p in [Decimal("100"), Decimal("100"), Decimal("100")]:
            conf.on_tick(p)
        conf.on_tick(Decimal("105"))
        assert conf.in_conference
        # More ticks don't clear it.
        conf.on_tick(Decimal("104"))
        assert conf.in_conference
        conf.acknowledge()
        assert not conf.in_conference
        assert conf.can_submit()

    def test_spread_blowout_triggers(self) -> None:
        conf = ExtremeMarketConference(
            flash_move_pct=Decimal("0.10"),  # very high — won't fire
            flash_window_ticks=3,
            spread_blowout_pct=Decimal("0.02"),
        )
        conf.on_tick(Decimal("100"))
        conf.on_tick(Decimal("100"))
        conf.on_tick(Decimal("100"))
        # Bid/ask spread of 5% (huge) — triggers.
        event = conf.on_tick(Decimal("100"), bid=Decimal("97.5"), ask=Decimal("102.5"))
        assert event is not None
        assert event.kind == "spread_blowout"
        assert conf.in_conference

    def test_normal_spread_does_not_trigger(self) -> None:
        conf = ExtremeMarketConference(spread_blowout_pct=Decimal("0.02"))
        for _ in range(5):
            event = conf.on_tick(Decimal("100"), bid=Decimal("99.9"), ask=Decimal("100.1"))
            assert event is None
        assert not conf.in_conference

    def test_flash_move_downward(self) -> None:
        """Crash direction also triggers."""
        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.03"), flash_window_ticks=3)
        for p in [Decimal("100"), Decimal("100"), Decimal("100")]:
            conf.on_tick(p)
        event = conf.on_tick(Decimal("95"))  # -5%
        assert event is not None
        assert event.kind == "flash_move"
        assert conf.in_conference

    def test_acknowledge_clears_event(self) -> None:
        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.03"), flash_window_ticks=3)
        for p in [Decimal("100"), Decimal("100"), Decimal("100")]:
            conf.on_tick(p)
        conf.on_tick(Decimal("105"))
        assert conf.triggering_event is not None
        conf.acknowledge()
        assert conf.triggering_event is None


# =========================================================================
# Integration: guards + PaperBroker
# =========================================================================


class TestGuardsWithPaperBroker:
    """End-to-end: stale feed + extreme conference + risk alert with a real broker."""

    async def test_stale_feed_blocks_new_submissions(self) -> None:
        """Pattern: when feed is stale, session loop gates on detector."""
        from execution.brokers.paper import PaperBroker

        clock = FakeClock()
        detector = StaleFeedDetector(timeout_s=5.0, clock=clock)
        broker = PaperBroker()

        # Tick once to make the detector non-stale.
        detector.on_tick()

        async def try_submit() -> str | None:
            if detector.is_stale():
                return None

            class _Entry:
                order_id = None
                instrument_id = "ES"
                side = "buy"
                quantity = Decimal("1")
                price = None
                order_type = "market"

            oid = await broker.submit_order(_Entry())
            detector.on_tick()  # successful submit refreshes heartbeat
            return oid

        # First call goes through.
        oid1 = await try_submit()
        assert oid1 is not None

        # Advance clock past staleness; next submit blocked.
        clock.advance(10)
        assert await try_submit() is None

        # Only one position opened with qty=1 (second buy never submitted).
        positions = await broker.positions()
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("1")

    async def test_conference_blocks_until_ack(self) -> None:
        from execution.brokers.paper import PaperBroker

        conf = ExtremeMarketConference(flash_move_pct=Decimal("0.03"), flash_window_ticks=2)
        broker = PaperBroker()
        await broker.on_price_update(Decimal("100"))

        async def try_submit(price: Decimal) -> str | None:
            conf.on_tick(price)
            if not conf.can_submit():
                return None

            class _Entry:
                order_id = None
                instrument_id = "ES"
                side = "buy"
                quantity = Decimal("1")
                price = None
                order_type = "market"

            return await broker.submit_order(_Entry())

        # Normal market → submit goes through.
        oid1 = await try_submit(Decimal("100"))
        assert oid1 is not None

        # Flash move (+5% in 2 ticks) → conference blocks.
        await try_submit(Decimal("102"))
        blocked = await try_submit(Decimal("106"))
        assert blocked is None
        assert conf.in_conference

        # Ack → submissions resume.
        conf.acknowledge()
        oid2 = await try_submit(Decimal("106"))
        assert oid2 is not None

    async def test_risk_alert_blocks_new_entries(self) -> None:
        from execution.brokers.paper import PaperBroker

        bus = RiskAlertBus()
        broker = PaperBroker()

        async def try_submit() -> str | None:
            if not bus.can_submit():
                return None

            class _Entry:
                order_id = None
                instrument_id = "ES"
                side = "buy"
                quantity = Decimal("1")
                price = None
                order_type = "market"

            return await broker.submit_order(_Entry())

        # Normal → submit.
        assert await try_submit() is not None

        # Hard breach → blocked.
        bus.ingest_breaches([_FakeBreach("hard", "daily_loss")])
        assert await try_submit() is None

        # Ack → resume.
        bus.acknowledge()
        assert await try_submit() is not None

        # Total fills: 2 (first + post-ack); the blocked one never happened.
        fills = await broker.get_fills()
        assert len(fills) == 2
