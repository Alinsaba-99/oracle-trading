"""Sentiment data sources — news, social media, macro events.

Integrates:
- AlphaAI: relevance-scored financial news (free tier: 20 req/min, 100/day)
  Source: https://alphai.io/developers
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("oracle.data.sentiment")

ALPHAI_BASE = "https://api.alphai.io/v1"


class SentimentFetcher:
    """Fetch news and sentiment data from multiple sources."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def alphai_news(self, ticker: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch relevance-scored financial news for a ticker via AlphaAI.

        Args:
            ticker: Stock/futures ticker (e.g. ES, AAPL, BTC).
            limit: Max articles to return.

        Returns:
            List of dicts with: title, url, relevance_score, category,
            published_at, sentiment.
        """
        import httpx

        params: dict[str, Any] = {"ticker": ticker, "limit": limit}
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            resp = httpx.get(f"{ALPHAI_BASE}/news", params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            articles: list[dict[str, Any]] = data.get("articles", data.get("data", []))
            logger.info("AlphaAI news fetched", ticker=ticker, count=len(articles))
            return articles
        except Exception as e:
            logger.warning("AlphaAI news fetch failed", error=str(e))
            return []

    def alphai_sentiment(self, ticker: str) -> dict[str, Any]:
        """Fetch aggregate sentiment score for a ticker.

        Returns:
            Dict with: score (-1 to 1), buzz_rank, article_count, source_breakdown.
        """
        import httpx

        params: dict[str, Any] = {"ticker": ticker}
        try:
            resp = httpx.get(f"{ALPHAI_BASE}/sentiment", params=params, timeout=10)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
        except Exception as e:
            logger.warning("AlphaAI sentiment fetch failed", error=str(e))
            return {"score": 0, "buzz_rank": 0, "article_count": 0}
