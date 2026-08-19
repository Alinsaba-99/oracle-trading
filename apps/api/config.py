"""API configuration from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"}


class APISettings(BaseSettings):
    """API configuration."""

    api_key: str = ""
    # Fail-closed default (P0, C1): bind to loopback.  Reaching the API from
    # other interfaces requires an explicit host override AND either an
    # API key or ORACLE_ALLOW_OPEN_BIND.
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    checkpoint_dir: str = "checkpoints/"
    data_dir: str = "data/"
    # Explicit opt-in for running WITHOUT an API key on a non-loopback
    # interface (e.g. a container whose published port is already bound to
    # 127.0.0.1 on the host).  Intentionally ugly so it is never left on
    # by accident.
    allow_open_bind: bool = False

    model_config = {"env_prefix": "ORACLE_"}

    @property
    def is_production(self) -> bool:
        """Return True if this is a production deployment.

        Currently detected by ``debug`` being ``False``.  In the future
        this should check a dedicated ``ORACLE_ENV`` or ``ORACLE_MODE``
        variable once environments (replay/paper/shadow/evaluation/funded)
        are formalised per G1.
        """
        return not self.debug

    @property
    def auth_enabled(self) -> bool:
        """Return True when API key authentication is active.

        Auth is enabled when a non-empty key is configured.
        """
        return bool(self.api_key)

    @property
    def bind_is_loopback(self) -> bool:
        """Return True when the configured bind host is loopback-only."""
        return self.host.lower() in _LOOPBACK_HOSTS


def verify_auth_bind_safety(settings: APISettings) -> None:
    """Fail-closed startup guard (P0, closes security-failopen-report C1/C2).

    Rules, in priority order:

    1. Production (``debug=False``) without an API key → fatal, always.
    2. No API key on a non-loopback interface → fatal unless the operator
       explicitly sets ``ORACLE_ALLOW_OPEN_BIND=true``.
    3. No API key on loopback → allowed (development), caller should warn.

    The historical behaviour was to start the API with zero authentication
    on ``0.0.0.0`` whenever ``ORACLE_API_KEY`` was empty — this function
    makes that state unreachable.
    """
    if settings.is_production and not settings.auth_enabled:
        msg = (
            "FATAL: ORACLE_API_KEY is required in production mode. "
            "Set the environment variable or run with debug=true for development."
        )
        raise SystemExit(msg)

    if not settings.auth_enabled and not settings.bind_is_loopback and not settings.allow_open_bind:
        msg = (
            f"FATAL: ORACLE_API_KEY is not set and the API would bind to a "
            f"non-loopback interface ({settings.host!r}) without authentication. "
            "Set ORACLE_API_KEY (recommended), bind to 127.0.0.1, or explicitly "
            "set ORACLE_ALLOW_OPEN_BIND=true to acknowledge an open dev endpoint."
        )
        raise SystemExit(msg)
