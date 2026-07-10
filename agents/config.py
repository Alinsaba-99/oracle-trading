"""Configuration for the Oracle MAS system."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MASConfig(BaseSettings):
    """Multi-Agent System configuration loaded from environment variables.

    All variables are prefixed with ``ORACLE_MAS_``.
    """

    model_config = SettingsConfigDict(env_prefix="ORACLE_MAS_")

    # LLM config
    primary_model: str = "gpt-4"
    fallback_model: str = "gpt-3.5-turbo"
    local_model: str = "ollama/llama3"
    llm_timeout_s: float = 30.0
    llm_temperature: float = 0.1

    # Agent config
    enabled_agents: list[str] = ["macro", "technical", "sentiment"]
    debate_rounds: int = 2

    # Risk config
    max_position_pct: float = 0.25
    max_leverage: float = 1.0
    var_confidence: float = 0.95

    # Runtime
    max_tokens_per_run: int = 10000
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_s: int = 300
