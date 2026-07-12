"""API configuration from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API configuration."""
    api_key: str = "oracle-dev-key"  # override via ORACLE_API_KEY env
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    checkpoint_dir: str = "checkpoints/"
    data_dir: str = "data/"

    model_config = {"env_prefix": "ORACLE_"}
