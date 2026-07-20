"""Shared test fixtures and mock helpers."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_oracle_environment() -> None:
    """Keep tests independent from ambient and leaked Oracle settings."""
    original = {key: value for key, value in os.environ.items() if key.startswith("ORACLE_")}

    for key in original:
        os.environ.pop(key, None)

    yield

    for key in tuple(os.environ):
        if key.startswith("ORACLE_"):
            os.environ.pop(key, None)
    os.environ.update(original)


class _FakeConnection:
    """Async context manager that wraps an AsyncMock connection.

    Simulates asyncpg connection: ``await pool.acquire()`` returns
    this, and ``async with conn:`` works via ``__aenter__``.
    """

    def __init__(self) -> None:
        self._mock = AsyncMock()
        self.execute = AsyncMock(return_value=None)
        self.fetch = AsyncMock(return_value=[])
        self.fetchrow = AsyncMock(return_value=None)
        # For stateful mock tests, override after fixture creation
        self._row_data: dict[str, dict] = {}

    async def __aenter__(self) -> _FakeConnection:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    def __await__(self):
        # Make awaitable: await conn → conn
        return self._await_impl().__await__()

    async def _await_impl(self):
        return self


class _FakePool:
    """Mock asyncpg pool.

    Usage::

        pool = _FakePool()
        conn = await pool.acquire()   # → _FakeConnection
        async with conn: ...          # works
    """

    def __init__(self) -> None:
        self._conn = _FakeConnection()

    def acquire(self) -> _FakeConnection:
        """Return a connection that works with ``async with``.

        asyncpg's pool.acquire() returns a PoolAcquireContext that is
        both awaitable AND an async context manager.  Our mock returns
        the connection directly (which IS an async context manager).
        """
        return self._conn

    async def release(self, conn: object = None) -> None:
        pass

    async def close(self) -> None:
        pass

    @property
    def conn(self) -> _FakeConnection:
        return self._conn


@pytest.fixture
def fake_pool() -> _FakePool:
    """Fixture: returns a mock asyncpg pool with async context support."""
    return _FakePool()


@pytest.fixture
def fake_pg(fake_pool: _FakePool, request: pytest.FixtureRequest) -> _FakePool:
    """Fixture: patches asyncpg.create_pool to return fake_pool."""
    import asyncio

    async def _fake_create_pool(**kwargs: object) -> _FakePool:
        return fake_pool

    from unittest.mock import patch

    patcher = patch("asyncpg.create_pool", side_effect=_fake_create_pool)
    patcher.start()
    request.addfinalizer(patcher.stop)
    return fake_pool
