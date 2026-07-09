"""Tests for the error hierarchy."""

from core.errors import (
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    EventError,
    EventPublishError,
    EventSubscribeError,
    LoggingConfigurationError,
    NATSConnectionError,
    NATSDisconnectedError,
    NATSTimeoutError,
    OracleError,
    OracleFatalError,
    PluginDependencyError,
    PluginError,
    PluginFatalError,
    PluginNotFoundError,
    PluginRegistrationError,
)


class TestOracleErrorBase:
    def test_is_exception(self):
        assert issubclass(OracleError, Exception)

    def test_default_code(self):
        err = OracleError("test")
        assert err.code == "UNKNOWN"

    def test_custom_code(self):
        err = OracleError("test", code="CFG001")
        assert err.code == "CFG001"
        assert "CFG001" in str(err)

    def test_details(self):
        err = OracleError("test", details={"file": "config.yaml"})
        assert err.details["file"] == "config.yaml"

    def test_str_includes_code(self):
        err = OracleError("something broke", code="GEN001")
        assert "[GEN001]" in str(err)

    def test_fatal_is_not_oracle_error(self):
        assert not issubclass(OracleFatalError, OracleError)

    def test_fatal_is_exception(self):
        assert issubclass(OracleFatalError, Exception)


class TestConfigErrors:
    def test_config_error_is_oracle_error(self):
        assert issubclass(ConfigError, OracleError)

    def test_not_found(self):
        err = ConfigNotFoundError("not found", code="CFG404")
        assert err.code == "CFG404"

    def test_validation_error(self):
        assert issubclass(ConfigValidationError, ConfigError)


class TestPluginErrors:
    def test_plugin_error_is_oracle_error(self):
        assert issubclass(PluginError, OracleError)

    def test_not_found(self):
        assert issubclass(PluginNotFoundError, PluginError)

    def test_registration_error(self):
        assert issubclass(PluginRegistrationError, PluginError)

    def test_dependency_error(self):
        assert issubclass(PluginDependencyError, PluginError)

    def test_fatal_is_not_oracle_error(self):
        assert not issubclass(PluginFatalError, OracleError)
        assert issubclass(PluginFatalError, OracleFatalError)


class TestEventErrors:
    def test_event_error_is_oracle_error(self):
        assert issubclass(EventError, OracleError)

    def test_publish_error(self):
        assert issubclass(EventPublishError, EventError)

    def test_subscribe_error(self):
        assert issubclass(EventSubscribeError, EventError)


class TestNATSErrors:
    def test_nats_error_is_oracle_error(self):
        assert issubclass(NATSConnectionError, OracleError)

    def test_disconnected(self):
        assert issubclass(NATSDisconnectedError, NATSConnectionError)

    def test_timeout(self):
        assert issubclass(NATSTimeoutError, NATSConnectionError)


class TestLoggingErrors:
    def test_logging_error_is_oracle_error(self):
        assert issubclass(LoggingConfigurationError, OracleError)
