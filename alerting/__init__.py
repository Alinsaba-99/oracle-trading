"""Alerting layer for the paper trading system (BL-733).

This package is intentionally kept *narrow* and *self-contained*:

- :mod:`alerting.types` — typed :class:`~alerting.types.AlertEvent` and
  pure renderers (:func:`~alerting.types.format_event`).
- :mod:`alerting.channels` — the :class:`~alerting.channels.AlertChannel`
  protocol, concrete channels (logging, Telegram, e-mail), and the
  :class:`~alerting.channels.CompositeChannel` router.
- :mod:`alerting.events` — the :class:`~alerting.events.Alerter` facade
  with convenience methods (``emit_fill``, ``emit_error`` …) and
  :func:`~alerting.events.build_default_alerter`.

Design rules:

* **Fail-open.** A channel error is logged, never raised into the trading
  loop.  The paper runner never crashes because Telegram is down.
* **Zero config to start.** :class:`~alerting.channels.LoggingChannel`
  always works (it writes through structlog).  Telegram / e-mail channels
  are *auto-disabled* with a warning when their credentials are missing.
* **Showcase-quality messages.** :func:`~alerting.types.format_event`
  produces human-readable lines like
  ``[PAPER] FILL BUY 100 SPY @ 573.25 slippage 1.2bps``.
"""

from __future__ import annotations

from alerting.channels import (
    AlertChannel,
    CompositeChannel,
    EmailChannel,
    LoggingChannel,
    TelegramChannel,
)
from alerting.events import Alerter, build_default_alerter
from alerting.types import AlertEvent, AlertKind, Severity, format_event, severity_rank

__all__ = [
    "AlertChannel",
    "AlertEvent",
    "AlertKind",
    "Alerter",
    "CompositeChannel",
    "EmailChannel",
    "LoggingChannel",
    "Severity",
    "TelegramChannel",
    "build_default_alerter",
    "format_event",
    "severity_rank",
]
