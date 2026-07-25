"""Ledger factory — create the right ledger implementation from settings.

Usage::

    from core.ledger_factory import create_ledger

    # Sync (InMemoryLedger, default)
    ledger = create_ledger()

    # Async (PostgresLedger) — requires running PostgreSQL
    ledger = await create_ledger(storage="postgres", dsn="postgresql://...")
    # ... use ledger ...
    await ledger.close()
"""

from __future__ import annotations

from typing import Literal

from core.config.settings import OracleSettings


def create_ledger(
    storage: Literal["memory", "postgres"] = "memory",
    settings: OracleSettings | None = None,
    dsn: str | None = None,
) -> object:
    """Create a Ledger instance.

    Args:
        storage: ``"memory"`` (default, InMemoryLedger) or ``"postgres"`` (PostgresLedger).
        settings: Optional OracleSettings. If provided, ``dsn`` is read from
                  ``settings.postgres.dsn``.
        dsn: PostgreSQL DSN override (only for ``storage="postgres"``).

    Returns:
        An InMemoryLedger (sync) or a PostgresLedger (async — requires ``await`` on
        ``create_account`` and ``record_fill``).

    Raises:
        ValueError: if ``storage="postgres"`` but no DSN is available.
    """
    if storage == "memory":
        from core.ledger import InMemoryLedger

        return InMemoryLedger()

    # Resolve DSN
    if dsn is None and settings is not None:
        dsn = settings.postgres.dsn
    if dsn is None:
        raise ValueError(
            "PostgresLedger requires a DSN. Set ORACLE_POSTGRES__DSN or pass dsn= explicitly."
        )

    from core.ledger_postgres import PostgresLedger

    return PostgresLedger.create(dsn=dsn)


__all__ = ["create_ledger"]
