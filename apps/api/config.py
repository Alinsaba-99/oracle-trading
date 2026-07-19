"""API configuration from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API configuration."""

    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    checkpoint_dir: str = "checkpoints/"
    data_dir: str = "data/"

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

        Auth is enabled when a non-empty key is configured.  In
        production (debug=False) a missing key is a fatal setup error.
        """
        return bool(self.api_key)
