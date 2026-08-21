"""BL-060 — storage default resolution: postgres when a DSN is configured.

Economic state must not silently live in memory; any runner/CLI with a
``--storage`` flag defaults to PostgreSQL the moment a DSN exists, and
falls back to memory only with a loud, documented warning.
"""

from __future__ import annotations

import pytest

from core.config.storage import DSN_ENV_VARS, find_dsn, resolve_storage_default

_DSN = "postgresql://oracle:oracle@localhost:5432/oracle"


class TestFindDsn:
    def test_no_env_returns_none(self) -> None:
        assert find_dsn(env={}) is None

    def test_database_url_wins(self) -> None:
        assert find_dsn(env={"DATABASE_URL": _DSN}) == _DSN

    def test_oracle_postgres_dsn_fallback(self) -> None:
        assert find_dsn(env={"ORACLE_POSTGRES__DSN": _DSN}) == _DSN

    def test_database_url_takes_precedence_over_nested(self) -> None:
        env = {"DATABASE_URL": "postgresql://a", "ORACLE_POSTGRES__DSN": "postgresql://b"}
        assert find_dsn(env=env) == "postgresql://a"

    def test_blank_values_are_ignored(self) -> None:
        assert find_dsn(env={"DATABASE_URL": "   ", "ORACLE_POSTGRES__DSN": ""}) is None

    def test_priority_order_is_documented(self) -> None:
        assert DSN_ENV_VARS[0] == "DATABASE_URL"


class TestResolveStorageDefault:
    def test_explicit_memory_wins_even_with_dsn(self) -> None:
        storage, dsn = resolve_storage_default("memory", env={"DATABASE_URL": _DSN})
        assert storage == "memory"
        assert dsn is None

    def test_explicit_postgres_resolves_dsn(self) -> None:
        storage, dsn = resolve_storage_default("postgres", env={"DATABASE_URL": _DSN})
        assert storage == "postgres"
        assert dsn == _DSN

    def test_default_postgres_when_dsn_configured(self) -> None:
        storage, dsn = resolve_storage_default(None, env={"DATABASE_URL": _DSN})
        assert (storage, dsn) == ("postgres", _DSN)

    def test_default_memory_when_no_dsn(self) -> None:
        storage, dsn = resolve_storage_default(None, env={})
        assert (storage, dsn) == ("memory", None)

    def test_explicit_postgres_without_dsn_has_none(self) -> None:
        # The DSN lookup still returns None; callers that require a
        # durable backend must fail loudly (see _resolve_dsn in the CLI).
        storage, dsn = resolve_storage_default("postgres", env={})
        assert storage == "postgres"
        assert dsn is None


class TestResolveDsnCliHelper:
    def test_missing_dsn_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.cli.trade_commands import _resolve_dsn

        for key in DSN_ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        with pytest.raises(ValueError, match="no DSN configured"):
            _resolve_dsn(None)

    def test_env_dsn_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.cli.trade_commands import _resolve_dsn

        monkeypatch.setenv("DATABASE_URL", _DSN)
        assert _resolve_dsn(None) == _DSN

    def test_explicit_dsn_wins(self) -> None:
        from apps.cli.trade_commands import _resolve_dsn

        assert _resolve_dsn("postgresql://x") == "postgresql://x"
