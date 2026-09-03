"""Unit tests for ``alerting.events`` (BL-734).

Covers:

* :class:`AlertEvent` construction + ``format_event`` rendering.
* Each :class:`Alerter` convenience method (``emit_fill``,
  ``emit_error``, ``emit_kill_switch``, ``emit_risk_breach``,
  ``emit_heartbeat_missed``).
* ERROR time-window coalescing with an injectable clock.
* Fail-open: a misbehaving channel does not propagate exceptions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from alerting.events import Alerter
from alerting.types import AlertEvent, AlertKind, Severity, format_event, severity_rank

# ─────────────────────────────────────────────────────────────────────
#  AlertEvent + formatting
# ─────────────────────────────────────────────────────────────────────


class TestAlertEventFormatting:
    def test_format_fill_renders_showcase_line(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.FILL,
            payload={
                "side": "BUY",
                "quantity": 100,
                "symbol": "SPY",
                "price": 573.25,
                "slippage_bps": 1.2,
                "strategy_id": "lane_b",
            },
            severity=Severity.INFO,
            timestamp=datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC),
            environment="PAPER",
        )
        assert format_event(evt) == (
            "[PAPER] FILL BUY 100 SPY @ 573.25 "
            "slippage 1.2bps strategy=lane_b "
            "(2026-09-02T12:00:00Z)"
        )

    def test_format_fill_with_no_price(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.FILL,
            payload={"side": "SELL", "quantity": 50, "symbol": "QQQ"},
            severity=Severity.INFO,
            timestamp=datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC),
        )
        body = format_event(evt)
        assert "SELL" in body
        assert "50" in body
        assert "QQQ" in body
        # No price in payload → no `@ ...` token.
        assert "@" not in body

    def test_format_kill_switch(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.KILL_SWITCH,
            payload={"reason": "daily loss limit", "actor": "risk_guard"},
            severity=Severity.CRITICAL,
            timestamp=datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC),
        )
        body = format_event(evt)
        assert "KILL_SWITCH" in body
        assert "reason=daily loss limit" in body
        assert "actor=risk_guard" in body

    def test_format_risk_breach(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.RISK_BREACH,
            payload={"rule": "daily_loss_5pct", "detail": "loss=5.4%"},
            severity=Severity.CRITICAL,
        )
        body = format_event(evt)
        assert "RISK_BREACH" in body
        assert "rule=daily_loss_5pct" in body
        assert "detail=loss=5.4%" in body

    def test_format_heartbeat_missed(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.HEARTBEAT_MISSED,
            payload={"since": "12:00:00Z", "threshold_s": 120},
            severity=Severity.WARNING,
        )
        body = format_event(evt)
        assert "HEARTBEAT_MISSED" in body
        assert "since=12:00:00Z" in body
        assert "threshold_s=120" in body

    def test_format_error(self) -> None:
        evt = AlertEvent(
            kind=AlertKind.ERROR,
            payload={"exception_type": "ConnectionError", "message": "broker down"},
            severity=Severity.WARNING,
        )
        body = format_event(evt)
        assert "ERROR" in body
        assert "ConnectionError" in body
        assert "broker down" in body

    def test_timestamp_default_is_now_utc(self) -> None:
        before = datetime.now(UTC)
        evt = AlertEvent(kind=AlertKind.FILL, payload={"x": 1}, severity=Severity.INFO)
        after = datetime.now(UTC)
        assert before <= evt.timestamp <= after
        assert evt.timestamp.tzinfo is UTC

    def test_environment_default(self) -> None:
        evt = AlertEvent(kind=AlertKind.FILL, payload={}, severity=Severity.INFO)
        assert evt.environment == "PAPER"


# ─────────────────────────────────────────────────────────────────────
#  Severity helpers
# ─────────────────────────────────────────────────────────────────────


class TestSeverity:
    def test_rank_orders_correctly(self) -> None:
        assert severity_rank(Severity.INFO) < severity_rank(Severity.WARNING)
        assert severity_rank(Severity.WARNING) < severity_rank(Severity.CRITICAL)


# ─────────────────────────────────────────────────────────────────────
#  Coalesce key
# ─────────────────────────────────────────────────────────────────────


class TestCoalesceKey:
    def test_error_uses_payload_signature(self) -> None:
        a = AlertEvent(
            kind=AlertKind.ERROR,
            payload={"exception_type": "X", "message": "msg"},
            severity=Severity.WARNING,
        )
        b = AlertEvent(
            kind=AlertKind.ERROR,
            payload={"exception_type": "X", "message": "msg"},
            severity=Severity.WARNING,
        )
        # Different timestamps ⇒ different events, but same coalesce key.
        assert a.coalesce_key() == b.coalesce_key()

    def test_fill_is_unique_per_event(self) -> None:
        a = AlertEvent(kind=AlertKind.FILL, payload={"order_id": "1"}, severity=Severity.INFO)
        b = AlertEvent(kind=AlertKind.FILL, payload={"order_id": "1"}, severity=Severity.INFO)
        # Two FILL events with same payload but different timestamps:
        # keys MUST differ so we never collapse fills.
        assert a.coalesce_key() != b.coalesce_key()

    def test_error_messages_with_different_messages(self) -> None:
        a = AlertEvent(
            kind=AlertKind.ERROR,
            payload={"exception_type": "X", "message": "msg-1"},
            severity=Severity.WARNING,
        )
        b = AlertEvent(
            kind=AlertKind.ERROR,
            payload={"exception_type": "X", "message": "msg-2"},
            severity=Severity.WARNING,
        )
        assert a.coalesce_key() != b.coalesce_key()


# ─────────────────────────────────────────────────────────────────────
#  Alerter facade
# ─────────────────────────────────────────────────────────────────────


class _CapturingChannel:
    """Records every event delivered."""

    def __init__(self, name: str = "capture") -> None:
        self.name = name
        self.received: list[AlertEvent] = []

    def is_enabled(self) -> bool:
        return True

    def send(self, event: AlertEvent) -> None:
        self.received.append(event)


class TestAlerterFill:
    def test_emit_fill_dispatches_with_showcase_payload(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap], environment="PAPER")
        evt = alerter.emit_fill(
            order_id="O-42",
            symbol="SPY",
            side="BUY",
            quantity=100,
            price=573.25,
            slippage_bps=1.2,
            strategy_id="lane_b",
        )
        assert evt.kind is AlertKind.FILL
        assert evt.severity is Severity.INFO
        assert evt.payload["order_id"] == "O-42"
        assert evt.payload["symbol"] == "SPY"
        assert evt.payload["strategy_id"] == "lane_b"
        assert cap.received == [evt]

    def test_emit_fill_merges_extra(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap])
        evt = alerter.emit_fill(
            order_id="O",
            symbol="X",
            side="SELL",
            quantity=10,
            price=100.0,
            extra={"venue": "NASDAQ", "client_order_id": "C-7"},
        )
        assert evt.payload["venue"] == "NASDAQ"
        assert evt.payload["client_order_id"] == "C-7"


class TestAlerterError:
    def test_first_event_dispatched(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap], error_coalesce_window_s=30.0)
        evt = alerter.emit_error(ConnectionError("broker down"))
        assert evt is not None
        assert cap.received == [evt]

    def test_identical_error_within_window_is_collapsed(self) -> None:
        cap = _CapturingChannel()
        # Clock returns constant value → every call is "within window".
        clock_value = {"t": 1000.0}

        def clock() -> float:
            return clock_value["t"]

        alerter = Alerter(channels=[cap], error_coalesce_window_s=30.0, clock=clock)

        # First emit reaches the channel.
        first = alerter.emit_error(ConnectionError("broker down"))
        assert first is not None
        # Identical follow-up collapses.
        second = alerter.emit_error(ConnectionError("broker down"))
        third = alerter.emit_error(ConnectionError("broker down"))
        assert second is None
        assert third is None
        assert cap.received == [first]

    def test_event_after_window_carries_suppressed_count(self) -> None:
        cap = _CapturingChannel()
        clock_value = {"t": 1000.0}

        def clock() -> float:
            return clock_value["t"]

        alerter = Alerter(channels=[cap], error_coalesce_window_s=30.0, clock=clock)

        alerter.emit_error(ConnectionError("broker down"))  # dispatched
        alerter.emit_error(ConnectionError("broker down"))  # collapsed
        alerter.emit_error(ConnectionError("broker down"))  # collapsed
        # Advance the clock past the window.
        clock_value["t"] = 2000.0
        next_evt = alerter.emit_error(ConnectionError("broker down"))
        assert next_evt is not None
        # ``suppressed_count`` is the total number of identical errors
        # since the previous dispatch: 1 (the original) + 2 (collapsed)
        # = 3.
        assert next_evt.payload["suppressed_count"] == 3
        # Channel saw the first event + this new one (with the count).
        assert len(cap.received) == 2
        assert cap.received[1] is next_evt

    def test_different_error_messages_are_not_collapsed(self) -> None:
        cap = _CapturingChannel()
        clock_value = {"t": 1000.0}

        def clock() -> float:
            return clock_value["t"]

        alerter = Alerter(channels=[cap], error_coalesce_window_s=30.0, clock=clock)
        a = alerter.emit_error(ConnectionError("a"))
        b = alerter.emit_error(ConnectionError("b"))
        assert a is not None
        assert b is not None
        assert len(cap.received) == 2

    def test_coalesce_disabled_when_window_zero(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap], error_coalesce_window_s=0.0)
        a = alerter.emit_error(ConnectionError("x"))
        b = alerter.emit_error(ConnectionError("x"))
        c = alerter.emit_error(ConnectionError("x"))
        assert a is not None and b is not None and c is not None
        assert len(cap.received) == 3


class TestAlerterCritical:
    def test_kill_switch_dispatch(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap])
        evt = alerter.emit_kill_switch(
            "daily loss limit hit", actor="risk_guard", extra={"pnl": -0.054}
        )
        assert evt.kind is AlertKind.KILL_SWITCH
        assert evt.severity is Severity.CRITICAL
        assert evt.payload["reason"] == "daily loss limit hit"
        assert evt.payload["actor"] == "risk_guard"
        assert evt.payload["pnl"] == -0.054
        assert cap.received == [evt]

    def test_risk_breach_dispatch(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap])
        evt = alerter.emit_risk_breach(rule="max_drawdown_5pct", detail="DD=5.3%")
        assert evt.kind is AlertKind.RISK_BREACH
        assert evt.payload["rule"] == "max_drawdown_5pct"
        assert evt.payload["detail"] == "DD=5.3%"

    def test_heartbeat_missed_dispatch(self) -> None:
        cap = _CapturingChannel()
        alerter = Alerter(channels=[cap])
        evt = alerter.emit_heartbeat_missed(since="12:00:00Z", threshold_s=120.0)
        assert evt.kind is AlertKind.HEARTBEAT_MISSED
        assert evt.severity is Severity.WARNING
        assert evt.payload["since"] == "12:00:00Z"
        assert evt.payload["threshold_s"] == 120.0

    def test_critical_events_never_coalesce(self) -> None:
        cap = _CapturingChannel()
        clock_value = {"t": 1000.0}

        def clock() -> float:
            return clock_value["t"]

        alerter = Alerter(channels=[cap], clock=clock)
        a = alerter.emit_kill_switch("r1")
        b = alerter.emit_kill_switch("r2")
        c = alerter.emit_risk_breach("r1", "d1")
        d = alerter.emit_heartbeat_missed("12:00:00Z", threshold_s=120)
        # Even at the same instant, every CRITICAL/WARNING should
        # reach the channel — only ERROR events collapse.
        assert all(e is not None for e in (a, b, c, d))
        assert len(cap.received) == 4


# ─────────────────────────────────────────────────────────────────────
#  Fail-open behavior
# ─────────────────────────────────────────────────────────────────────


class TestAlerterFailOpen:
    def test_channel_exception_does_not_propagate(self) -> None:
        class Boom:
            name = "boom"

            def is_enabled(self) -> bool:
                return True

            def send(self, event: AlertEvent) -> None:
                raise RuntimeError("channel went boom")

        good = _CapturingChannel("good")
        alerter = Alerter(channels=[Boom(), good])
        # Must NOT raise even though ``Boom.send`` blew up.
        alerter.emit_fill(order_id="O", symbol="X", side="BUY", quantity=1, price=1.0)
        # The well-behaved channel still received the event.
        assert good.received
        assert good.received[0].kind is AlertKind.FILL

    def test_multiple_channels_one_broken_other_works(self) -> None:
        class Boom:
            name = "boom"

            def is_enabled(self) -> bool:
                return True

            def send(self, event: AlertEvent) -> None:
                raise ValueError("nope")

        a = _CapturingChannel("a")
        b = _CapturingChannel("b")
        alerter = Alerter(channels=[Boom(), a, Boom(), b])
        alerter.emit_kill_switch("reason")
        assert len(a.received) == 1
        assert len(b.received) == 1


# ─────────────────────────────────────────────────────────────────────
#  Injectable clock (sanity)
# ─────────────────────────────────────────────────────────────────────


def test_default_clock_returns_monotonic() -> None:
    alerter = Alerter(channels=[])
    # Calling the default clock twice returns floats.
    a = alerter.clock()
    b = alerter.clock()
    assert isinstance(a, float)
    assert isinstance(b, float)
    assert a <= b


def test_emit_fill_does_not_mutate_extra_payloads() -> None:
    """Caller-owned dicts must not be aliased into the event."""
    cap = _CapturingChannel()
    alerter = Alerter(channels=[cap])
    extra = {"venue": "XNAS"}
    evt = alerter.emit_fill(
        order_id="O", symbol="A", side="BUY", quantity=1, price=2.0, extra=extra
    )
    # Mutate caller's dict after the call; event must be unaffected.
    extra["venue"] = "MUTATED"
    assert evt.payload["venue"] == "XNAS"
