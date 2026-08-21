"""BL-060 — resolve the durable-storage default from the environment.

Any CLI that persists economic state (``--storage memory|postgres``)
must default to PostgreSQL when a DSN is configured, so a restart or a
crash never silently loses the ledger.  Falling back to in-memory
storage is allowed but must be loud.

Resolution order (first non-empty wins):
1. ``DATABASE_URL`` (conventional name in .env)
2. ``ORACLE_POSTGRES__DSN`` (pydantic-settings name for
   ``OracleSettings().postgres.dsn``)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

#: Env vars that carry a PostgreSQL DSN, in priority order.
DSN_ENV_VARS: tuple[str, ...] = ("DATABASE_URL", "ORACLE_POSTGRES__DSN")


def _read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parse of a dotenv file (no interpolation)."""
    values: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    return values


def find_dsn(
    env: Mapping[str, str] | None = None, env_file: str | Path | None = ".env"
) -> str | None:
    """Return the first configured DSN, or ``None`` if none is set.

    Checks the process environment first (real env vars win over the
    dotenv file, matching pydantic-settings precedence), then the
    ``.env`` file — BL-060's AC is "postgres default when DATABASE_URL
    is present in .env".  When an explicit ``env`` mapping is passed
    (tests), the dotenv lookup is skipped so results stay hermetic.
    """
    source = env if env is not None else os.environ
    for key in DSN_ENV_VARS:
        value = source.get(key, "").strip()
        if value:
            return value
    if env is None and env_file is not None:
        dotenv = _read_env_file(Path(env_file))
        for key in DSN_ENV_VARS:
            value = dotenv.get(key, "").strip()
            if value:
                return value
    return None


def resolve_storage_default(
    explicit: str | None, env: Mapping[str, str] | None = None
) -> tuple[str, str | None]:
    """Resolve the effective ``--storage`` value.

    Args:
        explicit: the user's explicit ``--storage`` choice (``None`` =
            not passed).  An explicit choice always wins.
        env: environment mapping (defaults to ``os.environ``).

    Returns:
        ``(storage, dsn)`` — ``postgres`` + resolved DSN when a DSN is
        configured, else ``("memory", None)``.  Callers MUST warn when
        the resolved storage is ``memory``: in-memory state does not
        survive a restart (the warning is the AC of BL-060).
    """
    if explicit is not None:
        if explicit == "postgres":
            return "postgres", find_dsn(env)
        return explicit, None
    dsn = find_dsn(env)
    if dsn is not None:
        return "postgres", dsn
    return "memory", None


__all__ = ["DSN_ENV_VARS", "find_dsn", "resolve_storage_default"]
