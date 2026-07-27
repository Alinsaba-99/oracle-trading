"""OMS factory — create the right OMS implementation from settings.

Mirrors ``core.ledger_factory.create_ledger``.

Usage::

    from core.oms_factory import create_oms

    # Sync (InMemoryOMS, default)
    oms = create_oms()

    # Async (PostgresOMS) — requires running PostgreSQL
    oms = await create_oms(storage="postgres", dsn="postgresql://...", ledger=pg_ledger)
    await oms.close()
"""

from __future__ import annotations

from typing import Any, Literal

from core.config.settings import OracleSettings


def create_oms(
    storage: Literal["memory", "postgres"] = "memory",
    settings: OracleSettings | None = None,
    dsn: str | None = None,
    ledger: Any | None = None,
    idempotency_store: Any | None = None,
) -> Any:
    """Create an OMS instance.

    Args:
        storage: ``"memory"`` (default, InMemoryOMS) or ``"postgres"`` (PostgresOMS).
        settings: Optional OracleSettings. Reads ``settings.postgres.dsn``.
        dsn: PostgreSQL DSN override (only for ``storage="postgres"``).
        ledger: Optional Ledger instance (for P&L tracking on fills).
        idempotency_store: Optional durable idempotency store (InMemoryOMS only).

    Returns:
        An InMemoryOMS (sync) or a coroutine-producing PostgresOMS factory —
        actually returns ``PostgresOMS.create(...)`` coroutine for ``postgres``.

    Raises:
        ValueError: if ``storage="postgres"`` but no DSN is available.
    """
    if storage == "memory":
        from core.oms import InMemoryOMS

        return InMemoryOMS(ledger=ledger, idempotency_store=idempotency_store)

    if dsn is None and settings is not None:
        dsn = settings.postgres.dsn
    if dsn is None:
        raise ValueError(
            "PostgresOMS requires a DSN. Set ORACLE_POSTGRES__DSN or pass dsn= explicitly."
        )

    from core.oms_postgres import PostgresOMS

    # Caller must await this coroutine
    return PostgresOMS.create(ledger=ledger, dsn=dsn)


__all__ = ["create_oms"]
