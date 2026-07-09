"""Tests for the event bus client, envelope builder, and subscription manager."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from core.config.settings import NATSSettings
from core.errors.nats_errors import NATSConnectionError
from core.events.client import EventBusClient
from core.events.envelope import build_envelope
from core.events.subscription import SubscriptionManager
from core.events.system import (
    SYSTEM_HEALTH,
    SYSTEM_PLUGIN_REGISTERED,
    HealthEventPayload,
    PluginRegisteredPayload,
    SystemEventPayload,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def settings() -> NATSSettings:
    return NATSSettings(url="nats://localhost:4222", timeout=1.0, max_reconnect=1)


@pytest.fixture
def client(settings: NATSSettings) -> EventBusClient:
    return EventBusClient(settings)


# ── build_envelope ────────────────────────────────────────────────


class TestBuildEnvelope:
    """Coverage for the envelope builder."""

    def test_basic_envelope(self) -> None:
        envelope = build_envelope("test.subject", {"key": "value"}, "test-svc")
        assert envelope["subject"] == "test.subject"
        assert envelope["version"] == 1
        assert isinstance(envelope["timestamp"], str)
        assert envelope["source"] == "test-svc"
        assert isinstance(envelope["trace_id"], str)
        assert envelope["data"] == {"key": "value"}

    def test_default_version(self) -> None:
        envelope = build_envelope("s", {}, "src")
        assert envelope["version"] == 1

    def test_custom_version(self) -> None:
        envelope = build_envelope("s", {}, "src", version=3)
        assert envelope["version"] == 3

    def test_trace_id_generated_when_none(self) -> None:
        envelope = build_envelope("s", {}, "src")
        tid = envelope["trace_id"]
        assert isinstance(tid, str)
        assert len(tid) == 36  # UUID4
        assert tid.count("-") == 4

    def test_trace_id_preserved_when_provided(self) -> None:
        envelope = build_envelope("s", {}, "src", trace_id="my-trace")
        assert envelope["trace_id"] == "my-trace"

    def test_timestamp_is_iso8601_utc(self) -> None:
        envelope = build_envelope("s", {}, "src")
        ts = envelope["timestamp"]
        assert ts.endswith("+00:00") or ts.endswith("Z")
        # Round-trip to verify parseable
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_envelope_schema_matches_evends(self) -> None:
        """Verifies the envelope contains all expected top-level keys."""
        envelope = build_envelope("system.health", {}, "oracle")
        expected_keys = {"subject", "version", "timestamp", "source", "trace_id", "data"}
        assert set(envelope.keys()) == expected_keys
        # All string/metadata values are non-empty
        assert envelope["subject"]
        assert envelope["source"]
        assert envelope["trace_id"]

    def test_empty_data(self) -> None:
        envelope = build_envelope("s", {}, "src")
        assert envelope["data"] == {}


# ── EventBusClient ───────────────────────────────────────────────


class TestEventBusClient:
    """Coverage for the NATS event bus client."""

    # -- connect / close -------------------------------------------

    @patch("core.events.client.NATS")
    async def test_connect_creates_connection_and_publishes_health(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()
        mock_nats_class.return_value = mock_nc

        await client.connect()

        assert client._nc is not None
        assert client._js is not None
        mock_nc.connect.assert_awaited_once()
        mock_nc.publish.assert_awaited_once()

        subject = mock_nc.publish.await_args[0][0]
        assert subject == SYSTEM_HEALTH

    @patch("core.events.client.NATS")
    async def test_connect_raises_on_failure(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.connect.side_effect = Exception("Connection refused")
        mock_nats_class.return_value = mock_nc

        with pytest.raises(NATSConnectionError, match="Failed to connect to NATS"):
            await client.connect()

        assert client._nc is None
        assert client._js is None

    @patch("core.events.client.NATS")
    async def test_close_disconnects(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()
        mock_nats_class.return_value = mock_nc
        await client.connect()

        await client.close()

        mock_nc.close.assert_awaited_once()
        assert client._nc is None
        assert client._js is None

    # -- publish ---------------------------------------------------

    async def test_publish_before_connect_raises_nats_connection_error(
        self, client: EventBusClient
    ) -> None:
        """None-guard: must raise NATSConnectionError, not AttributeError."""
        with pytest.raises(NATSConnectionError, match="Not connected"):
            await client.publish("test", {})

    @patch("core.events.client.NATS")
    async def test_publish_calls_nats_publish_with_encoded_envelope(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()
        mock_nats_class.return_value = mock_nc
        await client.connect()

        await client.publish("test.subject", {"key": "value"}, source="my-svc")

        # connect() already called publish once (system.health), so expect 2
        assert mock_nc.publish.await_count == 2
        subject = mock_nc.publish.await_args_list[-1][0][0]
        payload = mock_nc.publish.await_args_list[-1][0][1]
        assert subject == "test.subject"
        assert isinstance(payload, bytes)
        assert b"test.subject" in payload
        assert b"my-svc" in payload

    @patch("core.events.client.NATS")
    async def test_subscribe_calls_nats_subscribe(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()
        mock_nats_class.return_value = mock_nc
        await client.connect()

        handler = AsyncMock()
        await client.subscribe("test.subject", handler, queue="workers")

        mock_nc.subscribe.assert_awaited_once_with("test.subject", queue="workers", cb=handler)

    @patch("core.events.client.NATS")
    async def test_subscribe_no_queue(
        self, mock_nats_class: MagicMock, client: EventBusClient
    ) -> None:
        mock_nc = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()
        mock_nats_class.return_value = mock_nc
        await client.connect()

        handler = AsyncMock()
        await client.subscribe("test.subject", handler)

        mock_nc.subscribe.assert_awaited_once()
        call_kwargs = mock_nc.subscribe.await_args[1]
        assert call_kwargs["queue"] == ""

    async def test_subscribe_before_connect_raises_nats_connection_error(
        self, client: EventBusClient
    ) -> None:
        with pytest.raises(NATSConnectionError, match="Not connected"):
            await client.subscribe("s", AsyncMock())


# ── SubscriptionManager ──────────────────────────────────────────


class TestSubscriptionManager:
    """Coverage for SubscriptionManager."""

    def test_add_and_list(self) -> None:
        mgr = SubscriptionManager()
        h = MagicMock()
        mgr.add("system.health", h)
        assert mgr.list() == ["system.health"]

    def test_add_with_queue(self) -> None:
        mgr = SubscriptionManager()
        h = MagicMock()
        mgr.add("system.health", h, queue="workers")
        assert mgr.list() == ["system.health"]

    def test_add_multiple_handlers_same_subject(self) -> None:
        mgr = SubscriptionManager()
        h1 = MagicMock()
        h2 = MagicMock()
        mgr.add("system.health", h1)
        mgr.add("system.health", h2)
        assert len(mgr._subscriptions["system.health"]) == 2

    def test_remove(self) -> None:
        mgr = SubscriptionManager()
        h = MagicMock()
        mgr.add("system.health", h)
        mgr.remove("system.health", h)
        assert mgr.list() == []

    def test_remove_one_of_many(self) -> None:
        mgr = SubscriptionManager()
        h1 = MagicMock()
        h2 = MagicMock()
        mgr.add("system.health", h1)
        mgr.add("system.health", h2)
        mgr.remove("system.health", h1)
        assert mgr.list() == ["system.health"]

    def test_remove_nonexistent_subject(self) -> None:
        mgr = SubscriptionManager()
        mgr.remove("nonexistent", MagicMock())  # should not raise

    def test_remove_nonexistent_handler(self) -> None:
        mgr = SubscriptionManager()
        h = MagicMock()
        mgr.add("system.health", h)
        mgr.remove("system.health", MagicMock())  # should not raise
        assert mgr.list() == ["system.health"]

    def test_empty_list(self) -> None:
        mgr = SubscriptionManager()
        assert mgr.list() == []

    def test_add_removes_subject_when_last_handler_removed(self) -> None:
        mgr = SubscriptionManager()
        h = MagicMock()
        mgr.add("test", h)
        mgr.remove("test", h)
        assert mgr.list() == []
        # Subject key should be deleted from internal dict
        assert "test" not in mgr._subscriptions


# ── System events schema ─────────────────────────────────────────


class TestSystemEventSchemas:
    """System events have correct schema."""

    def test_system_health_subject(self) -> None:
        assert SYSTEM_HEALTH == "system.health"

    def test_system_plugin_registered_subject(self) -> None:
        assert SYSTEM_PLUGIN_REGISTERED == "system.plugin.registered"

    def test_system_event_payload_defaults(self) -> None:
        payload = SystemEventPayload()
        assert payload.service == "oracle"
        assert isinstance(payload.timestamp, datetime)

    def test_health_event_payload_valid(self) -> None:
        payload = HealthEventPayload(status="healthy", components={"nats": "connected"})
        assert payload.status == "healthy"
        assert payload.components == {"nats": "connected"}
        assert payload.service == "oracle"

    def test_health_event_payload_all_status_values(self) -> None:
        for status in ("healthy", "degraded", "unhealthy"):
            payload = HealthEventPayload(status=status, components={})
            assert payload.status == status

    def test_health_event_payload_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            HealthEventPayload(status="unknown", components={})

    def test_plugin_registered_payload(self) -> None:
        payload = PluginRegisteredPayload(plugin_name="test-plugin", plugin_version="1.0.0")
        assert payload.plugin_name == "test-plugin"
        assert payload.plugin_version == "1.0.0"
        assert payload.service == "oracle"
