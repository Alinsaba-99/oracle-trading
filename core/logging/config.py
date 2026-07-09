"""Logging configuration — structlog with stdlib bridging."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(
    environment: str = "development",
    log_level: str = "INFO",
    json_output: bool | None = None,
    _service_name: str = "oracle",
) -> None:
    """Configure structlog with stdlib bridging and optional JSON output.

    In production mode (environment="production"), automatically outputs JSON.
    In development, outputs pretty console by default.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    if json_output is None:
        json_output = environment == "production"

    renderer = (
        structlog.dev.ConsoleRenderer() if not json_output else structlog.processors.JSONRenderer()
    )

    # Shared pre-processors applied before formatting (for both structlog and stdlib)
    pre_chain: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *pre_chain,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Use wrap_for_formatter so ProcessorFormatter handles final rendering
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter handles both structlog-native and stdlib log records
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = structlog.stdlib.ProcessorFormatter(processor=renderer, foreign_pre_chain=pre_chain)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    logging.captureWarnings(True)
