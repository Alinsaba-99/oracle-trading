"""Settings model for the sentiment analytics module."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentimentSettings(BaseSettings):
    """Configuration for sentiment analysis.

    Loaded from environment variables with ``ORACLE_`` prefix, e.g.
    ``ORACLE_ALPHA_AI_API_KEY``, ``ORACLE_FINBERT_MODEL``.
    """

    model_config = SettingsConfigDict(
        env_prefix="ORACLE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # FinBERT
    finbert_model: str = "ProsusAI/finbert"
    finbert_max_length: int = 512

    # News
    news_max_articles: int = 20
    news_api_base_url: str = "https://api.alphaai.dev/v1/news"

    # AlphaAI API key — loaded from env
    alphaai_api_key: str = ""

    # Aggregation
    confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    weight_news: float = Field(default=0.5, ge=0.0, le=1.0)
    weight_social: float = Field(default=0.2, ge=0.0, le=1.0)
    weight_earnings: float = Field(default=0.3, ge=0.0, le=1.0)
