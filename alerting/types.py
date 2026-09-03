"""Shared types and pure renderers for the alerting layer.

Kept in a leaf module so that :mod:`alerting.events` and
:mod:`alerting.channels` can both import from here without creating a
circular dependency.

Public surface
---------------

* :class:`AlertKind` — what happened.
* :class:`Severity` — operational severity (used for routing).
* :func:`severity_rank` — total order on :class:`Severity`.
* :class:`AlertEvent` — immutable record of an alert.
* :func:`format_event` — render an event to a human-readable string.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# ─────────────────────────────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────────────────────────────


class AlertKind(StrEnum):
    """The kind of event an :class:`AlertEvent` represents.

    StrEnum so values serialize cleanly through JSON / YAML / NATS.
    """

    FILL = "FILL"
    ERROR = "ERROR"
    KILL_SWITCH = "KILL_SWITCH"
    RISK_BREACH = "RISK_BREACH"
    HEARTBEAT_MISSED = "HEARTBEAT_MISSED"


class Severity(StrEnum):
    """Operational severity used by the routing layer.

    Ordering follows least→most urgent so :func:`severity_rank` gives a
    stable severity rank without depending on Enum internals.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# Numeric rank for ordered comparisons.
_SEVERITY_RANK: dict[Severity, int] = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


def severity_rank(severity: Severity) -> int:
    """Return a numeric rank for ``severity`` (higher = more urgent)."""
    return _SEVERITY_RANK[severity]


# ─────────────────────────────────────────────────────────────────────
#  Event record
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AlertEvent:
    """A single alert emitted by the trading stack.

    Attributes
    ----------
    kind : AlertKind
        What happened.
    payload : dict[str, Any]
        Free-form structured data.  :func:`format_event` knows how to
        read the well-known keys (``side``, ``quantity``, ``symbol``,
        ``price``, ``slippage_bps`` …) for showcase messages.
    severity : Severity
        Routing severity — see :class:`Severity`.
    timestamp : datetime
        UTC timestamp.  Defaults to ``datetime.now(UTC)`` when the
        :class:`~alerting.events.Alerter` constructs the event; tests
        can pin a value explicitly.
    environment : str
        Short tag rendered in the headline (e.g. ``PAPER``, ``LIVE``).
    """

    kind: AlertKind
    payload: dict[str, Any]
    severity: Severity
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    environment: str = "PAPER"

    # ── Convenience accessors ──────────────────────────────────────
    @property
    def subject(self) -> str:
        """Short subject line, e.g. ``PAPER FILL BUY 100 SPY``."""
        return _subject_line(self.kind, self.environment, self.payload)

    @property
    def body(self) -> str:
        """Human-readable multi-line body (never raises)."""
        return format_event(self)

    # ── Dedup key ─────────────────────────────────────────────────
    def coalesce_key(self) -> str:
        """Stable key for time-window coalescing.

        Only ``ERROR`` events are coalesced — FILL / KILL_SWITCH /
        RISK_BREACH / HEARTBEAT_MISSED must always reach the operator
        and so always return a unique key.
        """
        if self.kind is not AlertKind.ERROR:
            # Deterministic, unique per instance (timestamp + kind).
            digest = hashlib.sha256(repr(self).encode()).hexdigest()[:16]
            return f"{self.kind.value}:{digest}"
        # ERROR: collapse on (kind, exception_type, message)
        etype = str(self.payload.get("exception_type", ""))
        msg = str(self.payload.get("message", ""))
        return f"ERROR:{etype}:{msg}"


# ─────────────────────────────────────────────────────────────────────
#  Rendering
# ─────────────────────────────────────────────────────────────────────


def format_event(event: AlertEvent) -> str:
    """Render an :class:`AlertEvent` as a human-readable string.

    Examples
    --------
    >>> from datetime import datetime, UTC
    >>> from alerting.types import AlertEvent, AlertKind, Severity, format_event
    >>> evt = AlertEvent(
    ...     kind=AlertKind.FILL,
    ...     payload={"side": "BUY", "quantity": 100, "symbol": "SPY",
    ...              "price": 573.25, "slippage_bps": 1.2,
    ...              "strategy_id": "lane_b"},
    ...     severity=Severity.INFO,
    ...     timestamp=datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC),
    ...     environment="PAPER",
    ... )
    >>> format_event(evt)
    '[PAPER] FILL BUY 100 SPY @ 573.25 slippage 1.2bps strategy=lane_b (2026-09-02T12:00:00Z)'
    """
    ts = event.timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = f"[{event.environment}] {event.kind.value}"
    detail = _detail_for(event.kind, event.payload)
    tail = f" ({ts})"
    return f"{head} {detail}{tail}" if detail else f"{head}{tail}"


def _subject_line(kind: AlertKind, environment: str, payload: dict[str, Any]) -> str:
    """Compact subject for one-line channels (Telegram push, SMS, …)."""
    head = f"{environment} {kind.value}"
    detail = _subject_detail(kind, payload)
    return f"{head} {detail}".strip()


def _subject_detail(kind: AlertKind, payload: dict[str, Any]) -> str:
    if kind is AlertKind.FILL:
        side = str(payload.get("side", "?")).upper()
        qty = payload.get("quantity", "?")
        symbol = str(payload.get("symbol", "?"))
        return f"{side} {qty} {symbol}".strip()
    if kind is AlertKind.KILL_SWITCH:
        reason = str(payload.get("reason", ""))
        return reason[:60]
    if kind is AlertKind.RISK_BREACH:
        rule = str(payload.get("rule", ""))
        return rule[:60]
    if kind is AlertKind.HEARTBEAT_MISSED:
        since = str(payload.get("since", ""))
        return f"since {since}" if since else ""
    if kind is AlertKind.ERROR:
        etype = str(payload.get("exception_type", "Error"))
        return etype
    return ""


def _detail_for(kind: AlertKind, payload: dict[str, Any]) -> str:
    """Body detail per kind.  Always pure string formatting, no I/O."""
    if kind is AlertKind.FILL:
        side = str(payload.get("side", "?")).upper()
        qty = payload.get("quantity", "?")
        symbol = str(payload.get("symbol", "?"))
        price = payload.get("price")
        slippage_bps = payload.get("slippage_bps")
        order_id = payload.get("order_id")
        strategy_id = payload.get("strategy_id")
        parts: list[str] = [f"{side} {qty} {symbol}"]
        if price is not None:
            parts.append(f"@ {price}")
        if slippage_bps is not None:
            parts.append(f"slippage {_fmt_bps(slippage_bps)}")
        if strategy_id:
            parts.append(f"strategy={strategy_id}")
        if order_id:
            parts.append(f"order_id={order_id}")
        return " ".join(parts)

    if kind is AlertKind.KILL_SWITCH:
        reason = payload.get("reason", "(no reason given)")
        actor = payload.get("actor", "")
        parts = [f"reason={reason}"]
        if actor:
            parts.append(f"actor={actor}")
        return " ".join(parts)

    if kind is AlertKind.RISK_BREACH:
        rule = payload.get("rule", "?")
        detail = payload.get("detail", "")
        parts = [f"rule={rule}"]
        if detail:
            parts.append(f"detail={detail}")
        return " ".join(parts)

    if kind is AlertKind.HEARTBEAT_MISSED:
        since = payload.get("since", "?")
        threshold = payload.get("threshold_s", "?")
        return f"since={since} threshold_s={threshold}"

    if kind is AlertKind.ERROR:
        etype = payload.get("exception_type", "Error")
        msg = payload.get("message", "")
        return f"{etype}: {msg}".strip(": ")

    # Fallback: compact repr so callers never see a crash.
    return ", ".join(f"{k}={v}" for k, v in payload.items()) or "(no detail)"


def _fmt_bps(value: Any) -> str:
    """Format a value as basis points (1 decimal place)."""
    try:
        return f"{float(value):.1f}bps"
    except (TypeError, ValueError):
        return f"{value}bps"


__all__ = ["AlertEvent", "AlertKind", "Severity", "format_event", "severity_rank"]
