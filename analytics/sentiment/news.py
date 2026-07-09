"""News sentiment processor — fetch and score financial news.

Uses the AlphaAI API for news retrieval. Falls back to a mock/empty response
when the API is unavailable or unconfigured.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from analytics.sentiment.config import SentimentSettings
from analytics.sentiment.errors import SentimentError
from analytics.sentiment.finbert import FinBERTClassifier

logger = logging.getLogger(__name__)


class NewsSentimentProcessor:
    """Fetch news articles via AlphaAI and score them with FinBERT."""

    def __init__(
        self, classifier: FinBERTClassifier | None = None, settings: SentimentSettings | None = None
    ) -> None:
        self._classifier = classifier or FinBERTClassifier()
        self._settings = settings or SentimentSettings()
        self._api_key = self._settings.alphaai_api_key
        self._api_base = self._settings.news_api_base_url

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def fetch_news(self, instrument_id: str, max_articles: int = 20) -> list[dict[str, Any]]:
        """Fetch news articles for *instrument_id* from the AlphaAI API.

        Returns a list of raw article dicts with at most *max_articles*
        entries.  Each dict contains at minimum ``title``, ``description``,
        ``url``, and ``published_at`` keys.

        When the API key is empty or the request fails, returns an empty list
        with a logged warning.
        """
        if not self._api_key:
            logger.warning("AlphaAI API key not configured — returning empty news feed")
            return []

        try:
            response = httpx.get(
                self._api_base,
                params={
                    "symbol": instrument_id.upper(),
                    "limit": max_articles,
                    "api_key": self._api_key,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            msg = f"Failed to fetch news for {instrument_id}: {exc}"
            logger.warning(msg)
            raise SentimentError(msg) from exc

        # The API may wrap articles under a key; normalise to a list.
        raw = data.get("articles", data.get("data", data if isinstance(data, list) else []))
        articles: list[dict[str, Any]] = raw
        return articles[:max_articles]

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------

    def score_articles(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        """Run FinBERT over *articles* and return aggregate sentiment metrics.

        Returns a dict with::

            {
                "avg_sentiment": float,   # -1 (bearish) … +1 (bullish)
                "volume": int,            # number of articles scored
                "top_headlines": list[str],
            }

        When the classifier is unavailable the average defaults to 0.0.
        """
        if not articles:
            return {"avg_sentiment": 0.0, "volume": 0, "top_headlines": []}

        texts = [self._article_text(a) for a in articles]
        results = self._classifier.classify(texts)

        if results is None:
            return {"avg_sentiment": 0.0, "volume": len(articles), "top_headlines": []}

        # Convert label → numeric score
        label_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
        scores = [label_map.get(r["label"], 0.0) * r["score"] for r in results]

        top_headlines = [a.get("title", "") for a in articles[:5] if a.get("title")]

        return {
            "avg_sentiment": sum(scores) / len(scores) if scores else 0.0,
            "volume": len(scores),
            "top_headlines": top_headlines,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _article_text(article: dict[str, Any]) -> str:
        """Build a single text string from an article dict."""
        return f"{article.get('title', '')}. {article.get('description', '')}"
