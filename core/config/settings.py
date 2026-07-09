"""OracleSettings — hierarchical pydantic-settings configuration."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NATSSettings(BaseModel):
    url: str = Field(default="nats://localhost:4222")
    timeout: float = Field(default=5.0, ge=0)
    max_reconnect: int = Field(default=10, ge=0)


class RedisSettings(BaseModel):
    url: str = Field(default="redis://localhost:6379")
    timeout: float = Field(default=5.0, ge=0)
    max_connections: int = Field(default=10, ge=1)


class QuestDBSettings(BaseModel):
    host: str = "localhost"
    port: int = Field(default=9000, ge=1, le=65535)
    database: str = "oracle"


class PostgresSettings(BaseModel):
    dsn: str = Field(default="postgresql://oracle:oracle@localhost:5432/oracle")
    pool_size: int = Field(default=10, ge=1)
    timeout: float = Field(default=5.0, ge=0)


class PluginSettings(BaseModel):
    enabled: bool = True
    paths: list[str] = Field(default=["plugins"])
    auto_discover: bool = True


class AnalyticsSettings(BaseModel):
    """Configuration for analytics subsystem."""

    enabled: bool = True
    feature_store_path: str = "data/features"
    cache_size: int = Field(default=1000, ge=1)
    cache_ttl_seconds: int = Field(default=300, ge=1)
    backpressure_max_queue: int = Field(default=1000, ge=1)
    backpressure_drop_policy: str = Field(default="oldest", pattern="^(oldest|newest|drop)$")


class BacktestSettings(BaseModel):
    """Configuration for backtesting engine."""

    default_engine: str = "vectorized"
    default_slippage_bps: float = 5.0
    default_commission_pct: float = 0.001
    default_initial_capital: Decimal = Decimal("100000")
    feat_store_path: str = "data/features"


class OracleSettings(BaseSettings):
    """Root settings. Loaded from defaults -> YAML -> env vars."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="ORACLE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_json: bool = False

    nats: NATSSettings = NATSSettings()
    redis: RedisSettings = RedisSettings()
    questdb: QuestDBSettings = QuestDBSettings()
    postgres: PostgresSettings = PostgresSettings()
    plugins: PluginSettings = PluginSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    backtest: BacktestSettings = BacktestSettings()
