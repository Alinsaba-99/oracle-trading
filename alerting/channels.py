"""Alert channels for the paper trading system (BL-733).

This module implements the transport side of the alerting layer:

* :class:`AlertChannel` — the protocol every channel implements.
* :class:`LoggingChannel` — always-on fallback (structlog).
* :class:`TelegramChannel` — Telegram Bot API via stdlib ``urllib``.
* :class:`EmailChannel` — provider-agnostic SMTP via stdlib ``smtplib``.
* :class:`CompositeChannel` — router that dispatches by severity.

All concrete channels are **fail-open**: any network or protocol error
is logged through structlog and swallowed.  The trading loop never
sees an exception from a misbehaving notification path.

Missing credentials
-------------------

Both :class:`TelegramChannel` and :class:`EmailChannel` look at their
``enabled`` flag on construction.  When credentials are missing they
log a single warning and flip ``enabled`` to ``False`` so subsequent
:samp:`send(event)` calls become a no-op without spamming the log.
Use :meth:`TelegramChannel.from_env` / :meth:`EmailChannel.from_env`
to honour the ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` and
``EMAIL_*`` env vars.
"""

from __future__ import annotations

import os
import smtplib
from collections.abc import Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from alerting.types import AlertEvent, Severity, severity_rank

# All public names are re-exported by ``alerting.__init__``; this keeps
# the import surface minimal in case callers want internal symbols.
__all__ = ["AlertChannel", "CompositeChannel", "EmailChannel", "LoggingChannel", "TelegramChannel"]


# ─────────────────────────────────────────────────────────────────────
#  Protocol
# ─────────────────────────────────────────────────────────────────────


class AlertChannel(Protocol):
    """Anything that can deliver an :class:`AlertEvent`.

    Implementations MUST be fail-open: any error raised inside ``send``
    is a contract violation because the trading loop depends on alerts
    never crashing the system.
    """

    name: str

    def send(self, event: AlertEvent) -> None:
        """Deliver ``event``.  Never raise."""
        ...

    def is_enabled(self) -> bool:
        """Return True when this channel is configured and ready to send."""
        ...


# ─────────────────────────────────────────────────────────────────────
#  Logging fallback
# ─────────────────────────────────────────────────────────────────────


@dataclass
class LoggingChannel:
    """Always-on fallback channel.

    Renders events through :func:`alerting.events.format_event` and
    emits them at a severity-appropriate level through structlog.
    Zero config: instantiates with no arguments.
    """

    name: str = "logging"
    logger_name: str = "alerting.logging"

    def is_enabled(self) -> bool:
        return True

    def send(self, event: AlertEvent) -> None:
        log_method = _severity_to_log_method(event.severity)
        log_method(format_event_for_log(event))

    # LoggingChannel is always functional; never raise.


def format_event_for_log(event: AlertEvent) -> str:
    """Compact, single-line representation for log records."""
    return event.body


def _severity_to_log_method(severity: Severity) -> Any:
    """Map a :class:`Severity` to the matching structlog method."""
    if severity is Severity.CRITICAL:
        return _get_structlog_logger("alerting.logging").critical
    if severity is Severity.WARNING:
        return _get_structlog_logger("alerting.logging").warning
    return _get_structlog_logger("alerting.logging").info


# Lazy logger accessor — defers structlog import so that an
# unconfigured project still imports this module cleanly.
_logger_cache: dict[str, Any] = {}


def _get_structlog_logger(name: str) -> Any:
    cached: Any = _logger_cache.get(name)
    if cached is not None:
        return cached
    logger: Any
    try:
        from core.logging import get_logger

        logger = get_logger(name)
    except Exception:
        import logging

        logger = logging.getLogger(name)
    _logger_cache[name] = logger
    return logger


# ─────────────────────────────────────────────────────────────────────
#  Telegram channel
# ─────────────────────────────────────────────────────────────────────


#: Default Telegram Bot API endpoint.  Tests monkeypatch this URL.
DEFAULT_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
#: Connect / read timeout (seconds).  Short: alerts must be fast.
DEFAULT_HTTP_TIMEOUT_S: float = 5.0


@dataclass
class TelegramChannel:
    """Telegram Bot API channel (sendMessage).

    Reads its credentials from the ``TELEGRAM_BOT_TOKEN`` and
    ``TELEGRAM_CHAT_ID`` env vars via :meth:`from_env`, or accepts them
    directly via the constructor.

    When credentials are missing, ``enabled`` is set to ``False`` and
    :meth:`send` is a silent no-op.
    """

    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False
    api_url_template: str = DEFAULT_TELEGRAM_API_URL
    timeout_s: float = DEFAULT_HTTP_TIMEOUT_S
    name: str = "telegram"
    # Last warning timestamp so we don't spam the log when credentials
    # are missing.  ``0`` means "no warning logged yet".
    _warned_disabled_at: float = 0.0
    # Injectable HTTP poster — tests use this to capture payloads.
    _http_post: Any = field(default=None, repr=False)

    # ── Factories ──────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> TelegramChannel:
        """Build a channel from ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID``."""
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if token and chat_id:
            return cls(bot_token=token, chat_id=chat_id, enabled=True)
        log = _get_structlog_logger("alerting.channels.telegram")
        log.warning(
            "telegram_channel_disabled", reason="missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
        )
        return cls(enabled=False)

    # ── Protocol surface ───────────────────────────────────────────
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)

    def send(self, event: AlertEvent) -> None:
        if not self.is_enabled():
            return
        url = self.api_url_template.format(token=self.bot_token)
        payload = _telegram_payload(event, self.chat_id)
        try:
            self._post(url=url, payload=payload)
        except Exception as exc:
            self._log_failure(event, exc)

    # ── Internal helpers ───────────────────────────────────────────
    def _post(self, *, url: str, payload: dict[str, Any]) -> None:
        """POST ``payload`` to ``url`` as JSON.

        Override in tests via the ``_http_post`` hook to capture
        payloads without making real network calls.
        """
        import json

        poster = self._http_post
        if poster is not None:
            poster(url=url, payload=payload)
            return
        data = json.dumps(payload).encode("utf-8")
        req = Request(url=url, data=data, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=self.timeout_s).read()

    def _log_failure(self, event: AlertEvent, exc: BaseException) -> None:
        log = _get_structlog_logger("alerting.channels.telegram")
        log.error(
            "telegram_send_failed",
            event_kind=event.kind.value,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def _telegram_payload(event: AlertEvent, chat_id: str) -> dict[str, Any]:
    """Build a Telegram sendMessage payload with sane defaults."""
    return {
        "chat_id": chat_id,
        "text": event.body,
        # Show the severity tag so the operator can triage visually.
        "disable_web_page_preview": True,
        "parse_mode": "",
    }


# Re-export exception types for tests / callers that want to inspect
# the kind of network failure that happened.
_TELEGRAM_NETWORK_ERRORS = (HTTPError, URLError, TimeoutError, OSError)


# ─────────────────────────────────────────────────────────────────────
#  Email channel
# ─────────────────────────────────────────────────────────────────────


@dataclass
class EmailChannel:
    """Provider-agnostic SMTP channel.

    Reads ``EMAIL_HOST`` / ``EMAIL_PORT`` / ``EMAIL_USER`` /
    ``EMAIL_PASSWORD`` / ``EMAIL_FROM`` / ``EMAIL_TO`` env vars via
    :meth:`from_env`.  Plain (``EMAIL_USE_TLS=false``) and TLS SMTP
    are both supported.

    When any required env var is missing, ``enabled`` is ``False`` and
    :meth:`send` is a silent no-op.
    """

    host: str = ""
    port: int = 587
    user: str = ""
    auth_token: str = ""
    sender: str = ""
    recipients: tuple[str, ...] = ()
    use_tls: bool = True
    timeout_s: float = 10.0
    enabled: bool = False
    name: str = "email"
    # Injectable SMTP factory — tests use this to capture messages
    # without opening a real socket.
    _smtp_factory: Any = field(default=None, repr=False)

    # ── Factories ──────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> EmailChannel:
        host = os.getenv("EMAIL_HOST", "").strip()
        port_str = os.getenv("EMAIL_PORT", "587").strip()
        user = os.getenv("EMAIL_USER", "").strip()
        env_auth = os.getenv("EMAIL_PASSWORD", "")
        sender = os.getenv("EMAIL_FROM", "").strip()
        recipients_raw = os.getenv("EMAIL_TO", "").strip()
        use_tls_raw = os.getenv("EMAIL_USE_TLS", "true").strip().lower()
        recipients = tuple(r.strip() for r in recipients_raw.split(",") if r.strip())
        try:
            port = int(port_str) if port_str else 587
        except ValueError:
            port = 587
        use_tls = use_tls_raw not in {"false", "0", "no"}
        if host and sender and recipients:
            return cls(
                host=host,
                port=port,
                user=user,
                auth_token=env_auth,
                sender=sender,
                recipients=recipients,
                use_tls=use_tls,
                enabled=True,
            )
        log = _get_structlog_logger("alerting.channels.email")
        log.warning("email_channel_disabled", reason="missing EMAIL_HOST / EMAIL_FROM / EMAIL_TO")
        return cls(enabled=False)

    # ── Protocol surface ───────────────────────────────────────────
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.host) and bool(self.sender) and bool(self.recipients)

    def send(self, event: AlertEvent) -> None:
        if not self.is_enabled():
            return
        try:
            msg = _build_email_message(event, self.sender, self.recipients)
            self._smtp_send(msg)
        except Exception as exc:
            self._log_failure(event, exc)

    # ── Internal helpers ───────────────────────────────────────────
    def _smtp_send(self, msg: EmailMessage) -> None:
        factory = self._smtp_factory
        if factory is not None:
            factory(msg)
            return
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout_s) as smtp:
            smtp.ehlo()
            if self.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self.user:
                smtp.login(self.user, self.auth_token)
            smtp.send_message(msg)

    def _log_failure(self, event: AlertEvent, exc: BaseException) -> None:
        log = _get_structlog_logger("alerting.channels.email")
        log.error(
            "email_send_failed",
            event_kind=event.kind.value,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def _build_email_message(event: AlertEvent, sender: str, recipients: Sequence[str]) -> EmailMessage:
    """Construct an :class:`EmailMessage` carrying the alert body."""
    msg = EmailMessage()
    msg["Subject"] = event.subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(event.body)
    return msg


# ─────────────────────────────────────────────────────────────────────
#  Composite / router
# ─────────────────────────────────────────────────────────────────────


@dataclass
class CompositeChannel:
    """Severity-based router.

    The constructor accepts an iterable of channels and a *routing
    table* mapping each :class:`Severity` to the channels that should
    receive events of that severity.  Channels not listed for a given
    severity are skipped.

    Convenience constructors :meth:`quiet`, :meth:`standard` and
    :meth:`loud` cover the common patterns.
    """

    channels: tuple[AlertChannel, ...]
    routing: dict[Severity, tuple[AlertChannel, ...]]
    name: str = "composite"

    def is_enabled(self) -> bool:
        return any(c.is_enabled() for c in self.channels)

    def send(self, event: AlertEvent) -> None:
        for channel in self.routing.get(event.severity, ()):
            if not channel.is_enabled():
                continue
            try:
                channel.send(event)
            except Exception as exc:
                _log_channel_composite_failure(channel, event, exc)

    # ── Factories ──────────────────────────────────────────────────
    @classmethod
    def quiet(cls, *channels: AlertChannel) -> CompositeChannel:
        """INFO→logging only, WARNING→logging+telegram, CRITICAL→all."""
        logging = _ensure_logging(channels)
        tg = _pick("telegram", channels)
        mail = _pick("email", channels)
        routing: dict[Severity, tuple[AlertChannel, ...]] = {
            Severity.INFO: (logging,),
            Severity.WARNING: tuple(c for c in (logging, tg) if c is not None),
            Severity.CRITICAL: tuple(c for c in (logging, tg, mail) if c is not None),
        }
        return cls(channels=channels, routing=routing)

    @classmethod
    def standard(cls, *channels: AlertChannel) -> CompositeChannel:
        """WARNING→telegram, CRITICAL→telegram+email.  INFO is silent."""
        tg = _pick("telegram", channels)
        mail = _pick("email", channels)
        logging = _ensure_logging(channels)
        routing = {
            Severity.INFO: (logging,),  # LoggingChannel always present.
            Severity.WARNING: tuple(c for c in (tg, logging) if c is not None),
            Severity.CRITICAL: tuple(c for c in (tg, mail, logging) if c is not None),
        }
        return cls(channels=channels, routing=routing)

    @classmethod
    def loud(cls, *channels: AlertChannel) -> CompositeChannel:
        """Every event hits every channel (still filtered by is_enabled)."""
        return cls(
            channels=channels,
            routing={
                Severity.INFO: channels,
                Severity.WARNING: channels,
                Severity.CRITICAL: channels,
            },
        )

    # Convenience for unit tests — confirm a given severity routes
    # through the expected set.
    def channels_for(self, severity: Severity) -> tuple[AlertChannel, ...]:
        """Return the channels that will receive ``severity`` events."""
        return self.routing.get(severity, ())


def _pick(name: str, channels: Sequence[AlertChannel]) -> AlertChannel | None:
    """Return the first channel whose ``name`` attribute equals ``name``."""
    for c in channels:
        if getattr(c, "name", "") == name:
            return c
    return None


def _ensure_logging(channels: Sequence[AlertChannel]) -> AlertChannel:
    """Return the first LoggingChannel, or add a fresh one."""
    existing = _pick("logging", channels)
    if existing is not None:
        return existing
    return LoggingChannel()


def _log_channel_composite_failure(
    channel: AlertChannel, event: AlertEvent, exc: BaseException
) -> None:
    """Best-effort logging for failures dispatched via the router."""
    log = _get_structlog_logger("alerting.composite")
    log.error(
        "composite_channel_failed",
        channel=getattr(channel, "name", type(channel).__name__),
        event_kind=event.kind.value,
        event_severity=event.severity.value,
        error_type=type(exc).__name__,
        error=str(exc),
    )


# Re-export for callers that want the rank function alongside the
# protocol.  Avoids forcing an extra import in user code.
__all__ += ["severity_rank"]
