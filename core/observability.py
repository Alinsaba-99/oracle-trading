"""Global trace ID — end-to-end observability for every decision and trade.

Every decision, intent, order, fill, and ledger entry carries a trace_id
that allows reconstructing the full lifecycle of a trade.

Trace flow::

    data → decision (trace_id=abc) → intent (trace_id=abc)
    → order (trace_id=abc) → fill (trace_id=abc) → ledger (trace_id=abc)
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Any

import structlog

# ── Global trace context ────────────────────────────────────────────

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_span_id: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")


def generate_trace_id() -> str:
    """Generate a new trace ID (ULID-style: time-sortable)."""
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """Generate a new span ID."""
    return str(uuid.uuid4())[:8]


def get_trace_id() -> str:
    """Get the current trace ID from context."""
    return _trace_id.get()


def set_trace_id(trace_id: str | None = None) -> str:
    """Set the current trace ID. Generates one if not provided.

    Returns the trace ID (new or existing).
    """
    tid = trace_id or generate_trace_id()
    _trace_id.set(tid)
    return tid


def get_span_id() -> str:
    """Get the current span ID."""
    return _span_id.get()


def set_span_id(span_id: str | None = None) -> str:
    """Set the current span ID."""
    sid = span_id or generate_span_id()
    _span_id.set(sid)
    return sid


# ── Context manager ─────────────────────────────────────────────────


class TraceContext:
    """Context manager for trace propagation.

    Usage::

        with TraceContext() as tc:
            logger.info("Processing decision", trace_id=tc.trace_id)
            # All nested operations inherit the same trace_id
    """

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or generate_trace_id()
        self.span_id = generate_span_id()
        self._parent_trace = ""
        self._parent_span = ""

    def __enter__(self) -> TraceContext:
        self._parent_trace = get_trace_id()
        self._parent_span = get_span_id()
        _trace_id.set(self.trace_id)
        _span_id.set(self.span_id)
        return self

    def __exit__(self, *args: Any) -> None:
        _trace_id.set(self._parent_trace)
        _span_id.set(self._parent_span)


# ── Structured logging configuration ────────────────────────────────


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with trace context.

    Call once at application startup.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            _add_trace_context,
            structlog.dev.ConsoleRenderer() if level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for dependencies
    logging.basicConfig(level=getattr(logging, level))


def _add_trace_context(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Processor that injects trace_id/span_id into every log entry."""
    trace_id = get_trace_id()
    span_id = get_span_id()
    if trace_id:
        event_dict["trace_id"] = trace_id
    if span_id:
        event_dict["span_id"] = span_id
    return event_dict


# ── OpenTelemetry integration ───────────────────────────────────────


def init_opentelemetry(service_name: str = "oracle") -> bool:
    """Initialize OpenTelemetry tracing (no-op if OTLP endpoint not set).

    Returns True if tracing was enabled, False if no-op.
    """
    import os

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not otlp_endpoint:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return True
    except Exception as e:
        logging.warning(f"OpenTelemetry init failed: {e}")
        return False
