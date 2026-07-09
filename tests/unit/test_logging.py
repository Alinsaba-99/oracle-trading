"""Tests for logging infrastructure."""

import json
import logging

import pytest
import structlog

from core.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog config before each test."""
    structlog.reset_defaults()
    # Also reset stdlib logging
    logging.root.handlers.clear()
    yield


class TestConfigureLogging:
    def test_dev_mode_console(self):
        configure_logging(environment="development")
        log = get_logger("test")
        # Should not raise
        log.info("hello dev")

    def test_production_mode_json(self, capsys):
        configure_logging(environment="production")
        log = get_logger("test_json")
        log.info("hello prod", extra_field=42)

        out = capsys.readouterr().err
        parsed = json.loads(out.strip())
        assert parsed["event"] == "hello prod"
        assert parsed["extra_field"] == 42
        assert "logger" in parsed
        assert "timestamp" in parsed

    def test_log_level_filtering(self, capsys):
        configure_logging(environment="production", log_level="WARNING")
        log = get_logger("filter_test")
        log.info("should be silent")
        log.warning("should appear")

        out = capsys.readouterr().err
        assert "should be silent" not in out
        assert "should appear" in out

    def test_stdlib_bridging(self, capsys):
        """stdlib logging through structlog."""
        configure_logging(environment="production")
        stdlib_logger = logging.getLogger("stdlib_test")
        stdlib_logger.warning("from stdlib")

        out = capsys.readouterr().err
        parsed = json.loads(out.strip())
        assert parsed["event"] == "from stdlib"
        assert parsed["logger"] == "stdlib_test"

    def test_bound_context(self, capsys):
        configure_logging(environment="production")
        log = get_logger("ctx_test").bind(user_id=42)
        log.info("bound context")

        out = capsys.readouterr().err
        parsed = json.loads(out.strip())
        assert parsed["user_id"] == 42
