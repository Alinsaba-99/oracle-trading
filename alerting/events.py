"""The :class:`Alerter` facade (BL-734).

The :class:`Alerter` is the single entry point the rest of Oracle uses
to emit alerts.  Wiring the runner to it is intentionally *out of scope*
for BL-734 — see BL-730 + the Stream C items in ``BACKLOG.md``.

Layered responsibilities
------------------------

1. :class:`~alerting.types.AlertEvent` (in :mod:`alerting.types`) — an
   immutable, fully typed record of something that happened.  No
   behavior.
2. :func:`~alerting.types.format_event` (in :mod:`alerting.types`) —
   pure renderer that turns an event into a human-readable line.
3. :class:`Alerter` — facade that constructs events, dedupes / rate
   limits them, and forwards them to one or more
   :class:`~alerting.channels.AlertChannel` instances.

The dedupe / coalescing window is **per-error only** — FILL /
KILL_SWITCH / RISK_BREACH / HEARTBEAT_MISSED must always reach the
operator; ERROR events get collapsed within a short window because a
hot loop that throws 1000 exceptions/sec is useless to receive.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from alerting.channels import AlertChannel, LoggingChannel
from alerting.types import AlertEvent, AlertKind, Severity

# ─────────────────────────────────────────────────────────────────────
#  Alerter facade
# ─────────────────────────────────────────────────────────────────────


#: Signature of the injectable clock used for coalescing. Returns
#: a monotonic timestamp (seconds since epoch).  Defaults to
#: :func:`time.monotonic`.
Clock = Callable[[], float]


def _default_clock() -> float:
    import time

    return time.monotonic()


@dataclass
class Alerter:
    """Single entry point the rest of Oracle uses to emit alerts.

    Parameters
    ----------
    channels : Iterable[AlertChannel]
        Channels to dispatch events to.  Each ``send`` is wrapped in
        try/except so a faulty channel never propagates.
    environment : str
        Tag rendered in the subject line (e.g. ``PAPER``, ``LIVE``).
    error_coalesce_window_s : float
        Within this window, identical ``ERROR`` events are collapsed
        into a single notification carrying the count.  Set to ``0``
        to disable coalescing.
    clock : Clock
        Injectable for tests.  Defaults to ``time.monotonic``.
    """

    channels: Iterable[AlertChannel]
    environment: str = "PAPER"
    error_coalesce_window_s: float = 30.0
    clock: Clock = _default_clock
    # Per-key last-emitted timestamp + count.
    _coalesce_state: dict[str, tuple[float, int]] = field(
        default_factory=dict, init=False, repr=False
    )

    # ── Public convenience methods ─────────────────────────────────
    def emit_fill(
        self,
        *,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        slippage_bps: float | None = None,
        strategy_id: str = "",
        extra: dict[str, Any] | None = None,
        severity: Severity = Severity.INFO,
    ) -> AlertEvent:
        """Emit a :attr:`AlertKind.FILL` event."""
        payload: dict[str, Any] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
        }
        if slippage_bps is not None:
            payload["slippage_bps"] = slippage_bps
        if strategy_id:
            payload["strategy_id"] = strategy_id
        if extra:
            payload.update(extra)
        result = self._emit(AlertKind.FILL, payload, severity)
        assert result is not None  # FILL never coalesces.
        return result

    def emit_error(
        self, exc: BaseException, *, context: str = "", severity: Severity = Severity.WARNING
    ) -> AlertEvent | None:
        """Emit an :attr:`AlertKind.ERROR` event.

        Returns the *first* event of the coalescing window, or ``None``
        when the event was collapsed into a previously-emitted one.
        The latter case still increments the internal counter so the
        operator eventually sees ``[x42]``-style annotations.
        """
        payload: dict[str, Any] = {"exception_type": type(exc).__name__, "message": str(exc)}
        if context:
            payload["context"] = context
        return self._emit(AlertKind.ERROR, payload, severity, coalesce=True)

    def emit_kill_switch(
        self,
        reason: str,
        *,
        actor: str = "",
        severity: Severity = Severity.CRITICAL,
        extra: dict[str, Any] | None = None,
    ) -> AlertEvent:
        """Emit a :attr:`AlertKind.KILL_SWITCH` event (never coalesced)."""
        payload: dict[str, Any] = {"reason": reason}
        if actor:
            payload["actor"] = actor
        if extra:
            payload.update(extra)
        result = self._emit(AlertKind.KILL_SWITCH, payload, severity)
        assert result is not None  # KILL_SWITCH never coalesces.
        return result

    def emit_risk_breach(
        self,
        rule: str,
        detail: str,
        *,
        severity: Severity = Severity.CRITICAL,
        extra: dict[str, Any] | None = None,
    ) -> AlertEvent:
        """Emit a :attr:`AlertKind.RISK_BREACH` event (never coalesced)."""
        payload: dict[str, Any] = {"rule": rule, "detail": detail}
        if extra:
            payload.update(extra)
        result = self._emit(AlertKind.RISK_BREACH, payload, severity)
        assert result is not None  # RISK_BREACH never coalesces.
        return result

    def emit_heartbeat_missed(
        self,
        since: str,
        *,
        threshold_s: float,
        severity: Severity = Severity.WARNING,
        extra: dict[str, Any] | None = None,
    ) -> AlertEvent:
        """Emit a :attr:`AlertKind.HEARTBEAT_MISSED` event."""
        payload: dict[str, Any] = {"since": since, "threshold_s": threshold_s}
        if extra:
            payload.update(extra)
        result = self._emit(AlertKind.HEARTBEAT_MISSED, payload, severity)
        assert result is not None  # HEARTBEAT_MISSED never coalesces.
        return result

    # ── Core dispatch + coalescing ─────────────────────────────────
    def _emit(
        self,
        kind: AlertKind,
        payload: dict[str, Any],
        severity: Severity,
        *,
        coalesce: bool = False,
    ) -> AlertEvent | None:
        event = AlertEvent(
            kind=kind, payload=dict(payload), severity=severity, environment=self.environment
        )

        # Coalesce path — only ERROR events collapse.  Non-coalesce
        # path still records the state so a subsequent identical ERROR
        # starts a fresh window.
        key = event.coalesce_key()
        now = self.clock()
        if coalesce and self.error_coalesce_window_s > 0:
            last_ts, last_count = self._coalesce_state.get(key, (now - 1e9, 0))
            if now - last_ts < self.error_coalesce_window_s:
                # Collapse: store count, do NOT dispatch.
                self._coalesce_state[key] = (last_ts, last_count + 1)
                return None
            # Window elapsed: if we collapsed N events, annotate the
            # new payload so the operator sees the total.
            if last_count > 0:
                event.payload["suppressed_count"] = last_count
            self._coalesce_state[key] = (now, 1)
        else:
            # Non-coalesce path: still clear any stale ERROR window
            # state so a later ERROR starts fresh.
            self._coalesce_state.pop(key, None)

        self._dispatch(event)
        return event

    def _dispatch(self, event: AlertEvent) -> None:
        """Send ``event`` to every channel, swallowing any exception.

        LoggingChannel guarantees a working channel even when no
        external service is configured, so the trading loop can never
        crash because the alerter is mis-wired.
        """
        for channel in self.channels:
            try:
                channel.send(event)
            except Exception as exc:
                # The channel itself is responsible for fail-open on
                # its network I/O, but we belt-and-brace it here too:
                # if a custom channel's ``send`` raises, we log and
                # move on.
                _log_channel_failure(channel, event, exc)


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────


def _log_channel_failure(channel: AlertChannel, event: AlertEvent, exc: BaseException) -> None:
    """Log a channel failure through structlog (best effort)."""
    try:
        from core.logging import get_logger

        log = get_logger("alerting.alerter")
        log.error(
            "alert_channel_failed",
            channel=type(channel).__name__,
            event_kind=event.kind.value,
            event_severity=event.severity.value,
            error_type=type(exc).__name__,
            error=str(exc),
        )
    except Exception:
        # stdlib fallback so a totally broken structlog still surfaces
        # the failure somewhere.
        import logging

        logging.getLogger("alerting.alerter").exception(
            "alert_channel_failed: %s event=%s err=%s",
            type(channel).__name__,
            event.kind.value,
            exc,
        )


def build_default_alerter(
    *,
    environment: str = "PAPER",
    extra_channels: Iterable[AlertChannel] = (),
    error_coalesce_window_s: float = 30.0,
) -> Alerter:
    """Construct a sensible default :class:`Alerter`.

    Always includes :class:`~alerting.channels.LoggingChannel` so the
    system never crashes for lack of a channel.  Adds Telegram and
    e-mail channels when their credentials are present (auto-disabled
    otherwise — see the channel constructors).
    """
    from alerting.channels import EmailChannel, TelegramChannel

    channels: list[AlertChannel] = [LoggingChannel()]
    channels.extend(extra_channels)
    with contextlib.suppress(Exception):
        # Already logged inside TelegramChannel; keep going on any
        # construction error (e.g. malformed creds).
        channels.append(TelegramChannel.from_env())
    with contextlib.suppress(Exception):
        channels.append(EmailChannel.from_env())
    return Alerter(
        channels=channels, environment=environment, error_coalesce_window_s=error_coalesce_window_s
    )


__all__ = ["Alerter", "Clock", "build_default_alerter"]
