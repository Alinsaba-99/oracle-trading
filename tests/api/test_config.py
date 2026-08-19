"""Tests for the fail-closed API auth/bind guard (P0, C1/C2).

The guard must make the historical vulnerability unreachable: an API
with no ORACLE_API_KEY can never bind to a non-loopback interface
without an explicit opt-in, and production without a key never starts.
"""

from __future__ import annotations

import pytest

from apps.api.config import APISettings, verify_auth_bind_safety


class TestDefaultSettings:
    def test_default_host_is_loopback(self) -> None:
        """Default bind must be loopback, not 0.0.0.0 (the old default)."""
        settings = APISettings()
        assert settings.host == "127.0.0.1"
        assert settings.bind_is_loopback is True

    def test_default_auth_disabled_without_key(self) -> None:
        settings = APISettings()
        assert settings.auth_enabled is False


class TestVerifyAuthBindSafety:
    def test_production_without_key_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORACLE_DEBUG", "false")
        monkeypatch.delenv("ORACLE_API_KEY", raising=False)
        settings = APISettings()
        with pytest.raises(SystemExit, match="production"):
            verify_auth_bind_safety(settings)

    def test_no_key_open_bind_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Key-less API on a non-loopback interface refuses to start."""
        monkeypatch.setenv("ORACLE_HOST", "0.0.0.0")
        monkeypatch.delenv("ORACLE_API_KEY", raising=False)
        settings = APISettings()
        assert settings.bind_is_loopback is False
        with pytest.raises(SystemExit, match="ORACLE_ALLOW_OPEN_BIND"):
            verify_auth_bind_safety(settings)

    def test_no_key_loopback_is_allowed(self) -> None:
        """Development on loopback without a key stays allowed."""
        settings = APISettings()
        verify_auth_bind_safety(settings)  # must not raise

    def test_no_key_open_bind_with_explicit_opt_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORACLE_HOST", "0.0.0.0")
        monkeypatch.setenv("ORACLE_ALLOW_OPEN_BIND", "true")
        monkeypatch.delenv("ORACLE_API_KEY", raising=False)
        settings = APISettings()
        verify_auth_bind_safety(settings)  # explicit acknowledgement → allowed

    def test_key_set_allows_any_bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORACLE_HOST", "0.0.0.0")
        monkeypatch.setenv("ORACLE_API_KEY", "unit-test-key-value")
        settings = APISettings()
        assert settings.auth_enabled is True
        verify_auth_bind_safety(settings)  # must not raise

    def test_key_set_allows_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORACLE_DEBUG", "false")
        monkeypatch.setenv("ORACLE_API_KEY", "unit-test-key-value")
        settings = APISettings()
        verify_auth_bind_safety(settings)  # must not raise
