"""Session-level guard rails for the paper/live trading loop.

Implements M32-015..019 resilience drills:

- ``SignalProviderCircuit`` (M32-015 / M32-016): health-checked wrapper
  around an external signal source (LLM researcher, Eliza bridge).
  Trips open after ``failure_threshold`` consecutive failures; signals
  read while OPEN return ``None`` (caller treats as HOLD). Half-open
  after ``recovery_timeout_s``; closes on first success.

- ``StaleFeedDetector`` (M32-017): heartbeat-based staleness check.
  ``on_tick(now)`` refreshes the heartbeat; ``is_stale(now)`` returns
  True if no tick arrived within ``timeout_s``.

- ``RiskAlertBus`` (M32-018): converts PropFirmRiskGovernor breaches
  into actionable alerts. HARD breaches halt new entries; SOFT breaches
  only emit a warning. ``require_ack()`` blocks submissions until a
  human acknowledges.

- ``ExtremeMarketConference`` (M32-019): detects flash-crash-like moves
  (|Δ%| over N ticks) and spread blowouts. Triggers "conference mode":
  submissions blocked until explicitly acknowledged.

These guards are deliberately orthogonal to PaperBroker: they sit one
layer up, in the session loop, and gate the ``submit`` path.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

# =========================================================================
# M32-015 / M32-016 — Signal provider circuit breaker
# =========================================================================


class CircuitState(StrEnum):
    CLOSED = "closed"  # normal — calls go through
    OPEN = "open"  # tripped — calls short-circuit to None
    HALF_OPEN = "half_open"  # probing — one call allowed through


class SignalProviderCircuit:
    """Circuit breaker for an external signal provider.

    Usage::

        circuit = SignalProviderCircuit(name="llm", failure_threshold=3)
        signal = await circuit.call(fetch_signal)  # returns None when OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and self._clock() - self._opened_at >= self.recovery_timeout_s
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def is_available(self) -> bool:
        """True when a call would be attempted (CLOSED or HALF_OPEN)."""
        return self.state != CircuitState.OPEN

    async def call(self, fn: Callable[[], Awaitable[Any]]) -> Any | None:
        """Invoke ``fn``. Returns its result on success, ``None`` on failure
        or when the circuit is OPEN. Never raises.
        """
        state = self.state
        if state == CircuitState.OPEN:
            return None
        try:
            result = await fn()
        except Exception:
            self._record_failure()
            return None
        self._record_success()
        return result

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state == CircuitState.HALF_OPEN:
            # Probe failed — go back to OPEN.
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()
            return
        if self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def reset(self) -> None:
        """Manual reset (operator action)."""
        self._record_success()


# =========================================================================
# M32-017 — Stale feed detector
# =========================================================================


class StaleFeedDetector:
    """Heartbeat-based staleness detector for a market-data feed."""

    def __init__(self, timeout_s: float = 5.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.timeout_s = timeout_s
        self._clock = clock
        self._last_tick_at: float | None = None

    def on_tick(self, now: float | None = None) -> None:
        """Record a fresh tick."""
        self._last_tick_at = self._clock() if now is None else now

    def is_stale(self, now: float | None = None) -> bool:
        """True when no tick has been seen within ``timeout_s``."""
        if self._last_tick_at is None:
            return True  # never seen a tick → considered stale
        current = self._clock() if now is None else now
        return (current - self._last_tick_at) > self.timeout_s

    def time_since_last_tick(self, now: float | None = None) -> float | None:
        if self._last_tick_at is None:
            return None
        current = self._clock() if now is None else now
        return current - self._last_tick_at


# =========================================================================
# M32-018 — Risk alert bus
# =========================================================================


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RiskAlert:
    """A single risk alert emitted by the governor evaluation path."""

    level: AlertLevel
    code: str  # e.g. "daily_loss_hard", "daily_loss_soft", "overall_breach"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class RiskAlertBus:
    """Translates governor breaches into alerts; gates new submissions.

    - ``severity="hard"`` breach → CRITICAL alert + ``require_ack()`` blocks
      new entries until ``acknowledge()`` is called.
    - ``severity="soft"`` breach → WARNING alert; submissions continue.
    """

    def __init__(self) -> None:
        self._alerts: list[RiskAlert] = []
        self._awaiting_ack: bool = False

    @property
    def alerts(self) -> list[RiskAlert]:
        return list(self._alerts)

    @property
    def awaiting_ack(self) -> bool:
        return self._awaiting_ack

    def can_submit(self) -> bool:
        """Whether new order submission is currently allowed."""
        return not self._awaiting_ack

    def ingest_breaches(self, breaches: list[Any]) -> list[RiskAlert]:
        """Translate a list of ``Breach`` objects (governor.evaluate()) into
        alerts. Returns only the NEW alerts emitted by this call.
        """
        new_alerts: list[RiskAlert] = []
        for breach in breaches:
            severity = getattr(breach, "severity", "soft")
            breach_type = str(getattr(breach, "type", "unknown"))
            message = str(getattr(breach, "message", breach_type))
            if severity == "hard":
                alert = RiskAlert(
                    level=AlertLevel.CRITICAL,
                    code=breach_type,
                    message=message,
                    details={"severity": "hard"},
                )
                self._awaiting_ack = True
            else:
                alert = RiskAlert(
                    level=AlertLevel.WARNING,
                    code=breach_type,
                    message=message,
                    details={"severity": "soft"},
                )
            self._alerts.append(alert)
            new_alerts.append(alert)
        return new_alerts

    def acknowledge(self) -> None:
        """Human/operator ack: re-enable submissions."""
        self._awaiting_ack = False

    def reset(self) -> None:
        self._alerts.clear()
        self._awaiting_ack = False


# =========================================================================
# M32-019 — Extreme-market conference
# =========================================================================


@dataclass(frozen=True)
class ExtremeMarketEvent:
    """Description of the detected extreme condition."""

    kind: str  # "flash_move" | "spread_blowout" | "halt"
    magnitude_pct: Decimal
    window_ticks: int
    details: dict[str, Any] = field(default_factory=dict)


class ExtremeMarketConference:
    """Detects extreme market conditions; halts submissions until ack.

    - "flash_move": |price_now - price_N_ticks_ago| / price_N_ticks_ago
      exceeds ``flash_move_pct``.
    - "spread_blowout": (ask - bid) / mid exceeds ``spread_blowout_pct``.
    """

    def __init__(
        self,
        flash_move_pct: Decimal = Decimal("0.03"),  # 3%
        flash_window_ticks: int = 5,
        spread_blowout_pct: Decimal = Decimal("0.02"),  # 2%
    ) -> None:
        self.flash_move_pct = flash_move_pct
        self.flash_window_ticks = flash_window_ticks
        self.spread_blowout_pct = spread_blowout_pct
        self._prices: list[Decimal] = []
        self._in_conference: bool = False
        self._triggering_event: ExtremeMarketEvent | None = None

    @property
    def in_conference(self) -> bool:
        return self._in_conference

    @property
    def triggering_event(self) -> ExtremeMarketEvent | None:
        return self._triggering_event

    def can_submit(self) -> bool:
        return not self._in_conference

    def on_tick(
        self, price: Decimal, bid: Decimal | None = None, ask: Decimal | None = None
    ) -> ExtremeMarketEvent | None:
        """Feed a tick; returns the triggering event if conference mode
        was just entered, otherwise ``None``.
        """
        self._prices.append(price)
        if len(self._prices) > self.flash_window_ticks + 1:
            self._prices.pop(0)

        if not self._in_conference:
            event = self._check_flash_move() or self._check_spread(bid, ask)
            if event is not None:
                self._in_conference = True
                self._triggering_event = event
                return event
        return None

    def acknowledge(self) -> None:
        """Operator ack — exits conference mode and resumes submissions."""
        self._in_conference = False
        self._triggering_event = None
        self._prices.clear()

    def reset(self) -> None:
        self.acknowledge()

    # ------------------------------------------------------------------
    def _check_flash_move(self) -> ExtremeMarketEvent | None:
        if len(self._prices) < self.flash_window_ticks + 1:
            return None
        anchor = self._prices[0]
        if anchor == 0:
            return None
        move = abs(self._prices[-1] - anchor) / anchor
        if move >= self.flash_move_pct:
            return ExtremeMarketEvent(
                kind="flash_move",
                magnitude_pct=move,
                window_ticks=self.flash_window_ticks,
                details={"anchor": str(anchor), "latest": str(self._prices[-1])},
            )
        return None

    def _check_spread(self, bid: Decimal | None, ask: Decimal | None) -> ExtremeMarketEvent | None:
        if bid is None or ask is None or ask <= bid:
            return None
        mid = (bid + ask) / 2
        if mid == 0:
            return None
        spread_pct = (ask - bid) / mid
        if spread_pct >= self.spread_blowout_pct:
            return ExtremeMarketEvent(
                kind="spread_blowout",
                magnitude_pct=spread_pct,
                window_ticks=1,
                details={"bid": str(bid), "ask": str(ask), "mid": str(mid)},
            )
        return None
