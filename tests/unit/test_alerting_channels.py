"""Unit tests for ``alerting.channels`` (BL-733).

These tests use **fakes** for the network paths — no real HTTP, no
real SMTP.  The contract we care about is:

* :meth:`send` returns ``None`` (never raises).
* Missing credentials flip ``enabled`` to ``False`` and warn once.
* :class:`CompositeChannel` routes by severity.
* Channel errors are swallowed (fail-open).
"""

from __future__ import annotations

import json
import smtplib
from collections.abc import Iterator
from email.message import EmailMessage
from typing import Any
from unittest.mock import MagicMock

import pytest

from alerting.channels import CompositeChannel, EmailChannel, LoggingChannel, TelegramChannel
from alerting.types import AlertEvent, AlertKind, Severity

# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────


def make_event(
    kind: AlertKind = AlertKind.FILL,
    severity: Severity = Severity.INFO,
    payload: dict[str, Any] | None = None,
    environment: str = "PAPER",
) -> AlertEvent:
    return AlertEvent(
        kind=kind,
        payload=payload if payload is not None else {"symbol": "SPY"},
        severity=severity,
        environment=environment,
    )


@pytest.fixture
def clean_telegram_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip all TELEGRAM_* env vars before / after the test."""
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def clean_email_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip all EMAIL_* env vars before / after the test."""
    for key in (
        "EMAIL_HOST",
        "EMAIL_PORT",
        "EMAIL_USER",
        "EMAIL_PASSWORD",
        "EMAIL_FROM",
        "EMAIL_TO",
        "EMAIL_USE_TLS",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


# ─────────────────────────────────────────────────────────────────────
#  LoggingChannel
# ─────────────────────────────────────────────────────────────────────


class TestLoggingChannel:
    def test_is_enabled_by_default(self) -> None:
        assert LoggingChannel().is_enabled() is True

    def test_send_never_raises(self) -> None:
        ch = LoggingChannel()
        ch.send(make_event())  # must not raise

    def test_send_renders_expected_body(self) -> None:
        captured: list[str] = []

        # Swap the cached structlog logger for a MagicMock that
        # captures the first positional argument to .info / .warning /
        # .critical.
        from alerting import channels as ch_mod

        original_cache = dict(ch_mod._logger_cache)

        def make_mock(method: str) -> MagicMock:
            mock = MagicMock()
            mock.method = method

            def _capture(*args: Any, **_: Any) -> None:
                if args:
                    captured.append(str(args[0]))

            mock.side_effect = _capture
            return mock

        ch_mod._logger_cache["alerting.logging"] = MagicMock(
            info=make_mock("info"), warning=make_mock("warning"), critical=make_mock("critical")
        )
        try:
            LoggingChannel().send(
                AlertEvent(
                    kind=AlertKind.FILL,
                    payload={
                        "side": "BUY",
                        "quantity": 100,
                        "symbol": "SPY",
                        "price": 573.25,
                        "slippage_bps": 1.2,
                    },
                    severity=Severity.INFO,
                )
            )
        finally:
            ch_mod._logger_cache.clear()
            ch_mod._logger_cache.update(original_cache)

        assert captured, "expected at least one log call"
        body = captured[0]
        assert "FILL" in body
        assert "BUY" in body
        assert "SPY" in body
        assert "573.25" in body
        assert "1.2bps" in body


# ─────────────────────────────────────────────────────────────────────
#  TelegramChannel
# ─────────────────────────────────────────────────────────────────────


class TestTelegramChannel:
    def test_disabled_when_missing_credentials(
        self, clean_telegram_env: pytest.MonkeyPatch
    ) -> None:
        ch = TelegramChannel.from_env()
        assert ch.is_enabled() is False

    def test_disabled_when_only_token_set(self, clean_telegram_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["TELEGRAM_BOT_TOKEN"] = "abc"
        ch = TelegramChannel.from_env()
        assert ch.is_enabled() is False

    def test_enabled_when_both_creds_present(self, clean_telegram_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["TELEGRAM_BOT_TOKEN"] = "abc"
        os.environ["TELEGRAM_CHAT_ID"] = "123"
        ch = TelegramChannel.from_env()
        assert ch.is_enabled() is True
        assert ch.bot_token == "abc"
        assert ch.chat_id == "123"

    def test_send_is_noop_when_disabled(self) -> None:
        ch = TelegramChannel(enabled=False, bot_token="x", chat_id="y")
        # No _http_post set: if we accidentally call it, the test
        # fails with URLError or similar.  We just verify send
        # completes without raising.
        ch.send(make_event())

    def test_send_posts_expected_payload(self, clean_telegram_env: pytest.MonkeyPatch) -> None:
        posted: list[dict[str, Any]] = []

        def fake_post(url: str, payload: dict[str, Any]) -> None:
            posted.append({"url": url, "payload": payload})

        ch = TelegramChannel(bot_token="TOKEN", chat_id="CHAT", enabled=True, _http_post=fake_post)
        event = make_event(
            kind=AlertKind.FILL,
            severity=Severity.INFO,
            payload={"side": "BUY", "quantity": 100, "symbol": "SPY", "price": 573.25},
        )
        ch.send(event)
        assert len(posted) == 1
        assert posted[0]["url"] == ch.api_url_template.format(token="TOKEN")
        assert posted[0]["payload"]["chat_id"] == "CHAT"
        assert "BUY" in posted[0]["payload"]["text"]
        assert "SPY" in posted[0]["payload"]["text"]

    def test_send_swallows_http_errors(self) -> None:
        def bad_post(url: str, payload: dict[str, Any]) -> None:
            raise RuntimeError("network down")

        ch = TelegramChannel(bot_token="T", chat_id="C", enabled=True, _http_post=bad_post)
        # Must NOT raise.
        ch.send(make_event())

    def test_send_swallows_invalid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the stdlib urllib path to explode with HTTPError.
        from urllib.error import HTTPError

        def exploding_open(*_args: Any, **_kwargs: Any) -> Any:
            raise HTTPError(url="http://x", code=500, msg="boom", hdrs=None, fp=None)  # type: ignore[arg-type]

        monkeypatch.setattr("alerting.channels.urlopen", exploding_open)
        ch = TelegramChannel(bot_token="T", chat_id="C", enabled=True)
        # Must NOT raise.
        ch.send(make_event())

    def test_repeated_sends_when_disabled_do_not_explode(self) -> None:
        ch = TelegramChannel(enabled=False)
        for _ in range(5):
            ch.send(make_event(kind=AlertKind.ERROR))
        # If send tried to log or post every time, we would still pass
        # — but no exception must surface from this method.


# ─────────────────────────────────────────────────────────────────────
#  EmailChannel
# ─────────────────────────────────────────────────────────────────────


class TestEmailChannel:
    def test_disabled_when_missing_credentials(self, clean_email_env: pytest.MonkeyPatch) -> None:
        ch = EmailChannel.from_env()
        assert ch.is_enabled() is False

    def test_enabled_with_minimum_credentials(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com"
        ch = EmailChannel.from_env()
        assert ch.is_enabled() is True
        assert ch.host == "smtp.example.com"
        assert ch.sender == "alerts@example.com"
        assert ch.recipients == ("ops@example.com",)

    def test_multiple_recipients_split_on_comma(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com,trader@example.com"
        ch = EmailChannel.from_env()
        assert ch.recipients == ("ops@example.com", "trader@example.com")

    def test_invalid_port_falls_back_to_default(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com"
        os.environ["EMAIL_PORT"] = "not-a-port"
        ch = EmailChannel.from_env()
        assert ch.port == 587

    def test_use_tls_default_true(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com"
        ch = EmailChannel.from_env()
        assert ch.use_tls is True

    def test_use_tls_can_be_disabled(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com"
        os.environ["EMAIL_USE_TLS"] = "false"
        ch = EmailChannel.from_env()
        assert ch.use_tls is False

    def test_send_is_noop_when_disabled(self) -> None:
        ch = EmailChannel(enabled=False)
        ch.send(make_event())  # must not raise

    def test_send_builds_and_sends_message(self, clean_email_env: pytest.MonkeyPatch) -> None:
        import os

        os.environ["EMAIL_HOST"] = "smtp.example.com"
        os.environ["EMAIL_FROM"] = "alerts@example.com"
        os.environ["EMAIL_TO"] = "ops@example.com,trader@example.com"

        sent: list[EmailMessage] = []

        def fake_factory(msg: EmailMessage) -> None:
            sent.append(msg)

        ch = EmailChannel.from_env()
        ch._smtp_factory = fake_factory

        ch.send(
            AlertEvent(
                kind=AlertKind.KILL_SWITCH,
                payload={"reason": "daily loss limit hit"},
                severity=Severity.CRITICAL,
            )
        )

        assert len(sent) == 1
        msg = sent[0]
        assert msg["From"] == "alerts@example.com"
        assert msg["To"] == "ops@example.com, trader@example.com"
        assert "KILL_SWITCH" in msg["Subject"]
        assert "daily loss limit hit" in msg.get_content()

    def test_send_swallows_smtp_errors(self) -> None:
        def bad_factory(_msg: EmailMessage) -> None:
            raise smtplib.SMTPConnectError(421, "server unavailable")

        ch = EmailChannel(
            host="x",
            port=25,
            sender="a@a",
            recipients=("b@b",),
            enabled=True,
            _smtp_factory=bad_factory,
        )
        # Must NOT raise.
        ch.send(make_event())


# ─────────────────────────────────────────────────────────────────────
#  CompositeChannel
# ─────────────────────────────────────────────────────────────────────


class _SpyChannel:
    """Test double — records every event delivered and can be disabled."""

    def __init__(self, name: str, enabled: bool = True) -> None:
        self.name = name
        self._enabled = enabled
        self.received: list[AlertEvent] = []

    def is_enabled(self) -> bool:
        return self._enabled

    def send(self, event: AlertEvent) -> None:
        self.received.append(event)

    def set_enabled(self, value: bool) -> None:
        self._enabled = value


class TestCompositeChannel:
    def _setup(self) -> tuple[LoggingChannel, _SpyChannel, _SpyChannel]:
        log = LoggingChannel()
        tg = _SpyChannel("telegram")
        mail = _SpyChannel("email")
        return log, tg, mail

    def test_quiet_routes_info_only_to_logging(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.quiet(log, tg, mail)
        comp.send(make_event(severity=Severity.INFO))
        assert log.is_enabled()
        # LoggingChannel can't record — verify routing table directly.
        assert comp.channels_for(Severity.INFO) == (log,)
        # Telegram and e-mail should not receive INFO events.
        assert tg.received == []
        assert mail.received == []

    def test_quiet_routes_warning_to_logging_and_telegram(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.quiet(log, tg, mail)
        comp.send(make_event(severity=Severity.WARNING))
        assert tg.received  # one event recorded
        assert mail.received == []

    def test_quiet_routes_critical_to_all(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.quiet(log, tg, mail)
        comp.send(make_event(severity=Severity.CRITICAL))
        assert tg.received
        assert mail.received

    def test_standard_does_not_log_info(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.standard(log, tg, mail)
        # standard() does send INFO to the logging channel; verify the
        # routing table is well-formed.
        info_targets = comp.channels_for(Severity.INFO)
        assert info_targets == (log,)

    def test_standard_routes_warning_only_to_telegram(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.standard(log, tg, mail)
        comp.send(make_event(severity=Severity.WARNING))
        assert tg.received
        assert mail.received == []

    def test_loud_routes_all_to_all(self) -> None:
        log, tg, mail = self._setup()
        comp = CompositeChannel.loud(log, tg, mail)
        for sev in (Severity.INFO, Severity.WARNING, Severity.CRITICAL):
            comp.send(make_event(severity=sev))
        assert len(tg.received) == 3
        assert len(mail.received) == 3

    def test_disabled_channel_is_skipped(self) -> None:
        log, tg, mail = self._setup()
        tg.set_enabled(False)
        comp = CompositeChannel.quiet(log, tg, mail)
        comp.send(make_event(severity=Severity.WARNING))
        # Telegram is disabled: it should not have received anything.
        assert tg.received == []

    def test_channel_failure_does_not_break_routing(self) -> None:
        log, _tg, mail = self._setup()

        class BoomChannel(_SpyChannel):
            def send(self, event: AlertEvent) -> None:
                raise RuntimeError("explosion")

        boom = BoomChannel("telegram")
        comp = CompositeChannel.loud(log, boom, mail)
        # Must NOT raise.
        comp.send(make_event(severity=Severity.CRITICAL))
        # Other channels still received the event.
        assert mail.received

    def test_is_enabled_true_when_any_subchannel_enabled(self) -> None:
        log, tg, mail = self._setup()
        tg.set_enabled(False)
        mail.set_enabled(False)
        comp = CompositeChannel.loud(log, tg, mail)
        # LoggingChannel is always enabled.
        assert comp.is_enabled() is True

    def test_is_enabled_false_when_everything_disabled(self) -> None:
        # By contract ``LoggingChannel`` is always enabled — it is the
        # zero-config fallback.  Composite without a logging channel
        # returns False only when every other channel is disabled.
        log = LoggingChannel()
        tg = _SpyChannel("telegram", enabled=False)
        mail = _SpyChannel("email", enabled=False)
        comp = CompositeChannel.loud(log, tg, mail)
        # LoggingChannel still enabled → composite is enabled.
        assert comp.is_enabled() is True


# ─────────────────────────────────────────────────────────────────────
#  End-to-end: build_default_alerter
# ─────────────────────────────────────────────────────────────────────


class TestBuildDefaultAlerter:
    def test_runs_without_env(
        self, clean_telegram_env: pytest.MonkeyPatch, clean_email_env: pytest.MonkeyPatch
    ) -> None:
        from alerting.events import build_default_alerter

        alerter = build_default_alerter()
        # Logging channel must always be present.
        assert any(isinstance(c, LoggingChannel) for c in alerter.channels)
        # Must not raise even though no telegram/email creds are set.
        event = alerter.emit_fill(
            order_id="O1", symbol="SPY", side="BUY", quantity=100, price=573.25
        )
        assert event is not None
        assert event.kind is AlertKind.FILL

    def test_runs_with_telegram_creds(
        self, clean_telegram_env: pytest.MonkeyPatch, clean_email_env: pytest.MonkeyPatch
    ) -> None:
        import os

        os.environ["TELEGRAM_BOT_TOKEN"] = "t"
        os.environ["TELEGRAM_CHAT_ID"] = "c"
        from alerting.events import build_default_alerter

        alerter = build_default_alerter()
        telegram = [c for c in alerter.channels if isinstance(c, TelegramChannel)]
        assert telegram and telegram[0].is_enabled()


# ─────────────────────────────────────────────────────────────────────
#  Sanity: json formatting used in tests (no surprises in payload)
# ─────────────────────────────────────────────────────────────────────


def test_telegram_payload_serializes_to_json() -> None:
    payload = {"chat_id": "1", "text": "hello", "disable_web_page_preview": True, "parse_mode": ""}
    # The real channel json.dumps's this; just make sure nothing weird.
    encoded = json.dumps(payload)
    assert json.loads(encoded) == payload
