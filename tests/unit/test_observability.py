"""Tests for observability — trace ID, audit trail, logging."""

from __future__ import annotations

from core.audit import AuditTrail
from core.observability import TraceContext, generate_trace_id, get_trace_id, set_trace_id


class TestTraceContext:
    """Trace ID propagation."""

    def test_generate_unique_ids(self) -> None:
        t1 = generate_trace_id()
        t2 = generate_trace_id()
        assert t1 != t2
        assert len(t1) == 36  # UUID4

    def test_set_and_get(self) -> None:
        set_trace_id("test-123")
        assert get_trace_id() == "test-123"
        # Reset for other tests
        set_trace_id("")

    def test_context_manager(self) -> None:
        with TraceContext() as tc:
            assert get_trace_id() == tc.trace_id
        # After exit, context is restored to previous value (if any)

    def test_nested_context(self) -> None:
        with TraceContext() as outer:
            with TraceContext() as inner:
                assert get_trace_id() == inner.trace_id
            assert get_trace_id() == outer.trace_id

    def test_auto_generates(self) -> None:
        with TraceContext() as tc:
            assert tc.trace_id is not None
            assert len(tc.trace_id) == 36


class TestAuditTrail:
    """Immutable audit chain."""

    def test_empty_trail(self) -> None:
        audit = AuditTrail()
        assert audit.count == 0
        assert audit.verify_chain()

    def test_record_entry(self) -> None:
        audit = AuditTrail()
        entry = audit.record("order.created", {"order_id": "123"})
        assert entry.event_type == "order.created"
        assert entry.payload["order_id"] == "123"
        assert entry.hash is not None
        assert audit.count == 1

    def test_chain_integrity(self) -> None:
        audit = AuditTrail()
        audit.record("order.created", {"id": "1"})
        audit.record("order.submitted", {"id": "1"})
        audit.record("order.filled", {"id": "1"})
        assert audit.verify_chain()

    def test_tamper_detected(self) -> None:
        audit = AuditTrail()
        audit.record("order.created", {"id": "1"})
        audit.record("order.filled", {"id": "1"})

        # Tamper with the first entry
        audit._entries[0].payload["id"] = "999"
        assert not audit.verify_chain()

    def test_entries_linked(self) -> None:
        audit = AuditTrail()
        e1 = audit.record("event1", {})
        e2 = audit.record("event2", {})
        assert e2.previous_hash == e1.hash

    def test_find_by_trace_id(self) -> None:
        audit = AuditTrail()
        with TraceContext() as tc:
            audit.record("event1", {}, trace_id=tc.trace_id)
            audit.record("event2", {}, trace_id=tc.trace_id)

        results = audit.find_by_trace_id(tc.trace_id)
        assert len(results) == 2

    def test_find_by_event_type(self) -> None:
        audit = AuditTrail()
        audit.record("order.created", {"id": "1"})
        audit.record("order.filled", {"id": "1"})
        audit.record("order.created", {"id": "2"})

        created = audit.find_by_event_type("order.created")
        assert len(created) == 2

    def test_export_json(self, tmp_path) -> None:
        audit = AuditTrail()
        audit.record("test", {"key": "value"})

        path = tmp_path / "audit.json"
        audit.export_json(str(path))
        assert path.exists()
        assert path.read_text() != ""

    def test_verify_single_entry(self) -> None:
        audit = AuditTrail()
        entry = audit.record("test", {})
        assert entry.verify()
        # Modify after recording
        entry.payload["extra"] = "data"
        assert not entry.verify()
