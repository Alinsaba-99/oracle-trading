"""Sentiment aggregator — merge multiple sentiment sources and publish results.

Combines sentiment signals from news, social media, earnings calls (or any
source conforming to the same dict shape) into a single composite score,
then optionally publishes the result as a ``feature.updated`` NATS event.
"""

from __future__ import annotations

import logging
from typing import Any

from analytics.sentiment.config import SentimentSettings
from core.events.envelope import build_envelope
from core.events.feature import FeatureUpdatedEvent

logger = logging.getLogger(__name__)

# Default weights when no source-specific override is provided.
_WEIGHTS: dict[str, float] = {"news": 0.5, "social": 0.2, "earnings": 0.3}


class SentimentAggregator:
    """Merge sentiment results from multiple sources into a composite score.

    Each source dict should have at least::

        {"source": "news", "avg_sentiment": 0.42, "volume": 15}

    The composite score is a weighted average across sources present.
    Confidence reflects agreement (inverse variance) among the sources.
    """

    def __init__(
        self, weights: dict[str, float] | None = None, settings: SentimentSettings | None = None
    ) -> None:
        self._weights = {**_WEIGHTS, **(weights or {})}
        self._settings = settings or SentimentSettings()

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge_sentiment(self, sources: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine multiple sentiment sources into a single result.

        Args:
            sources: List of source dicts, each with ``source``, ``avg_sentiment``,
                     and optionally ``volume``.

        Returns:
            A dict with::

                {
                    "composite_score": float,   # weighted average (-1 … +1)
                    "source_count": int,
                    "confidence": float,        # 0 (low) … 1 (high)
                    "details": {source_name: source_dict, …},
                }
        """
        if not sources:
            return {"composite_score": 0.0, "source_count": 0, "confidence": 0.0, "details": {}}

        weighted_sum = 0.0
        total_weight = 0.0
        details: dict[str, dict[str, Any]] = {}
        sentiments: list[float] = []

        for source in sources:
            src_name = source.get("source", "unknown")
            sentiment = float(source.get("avg_sentiment", 0.0))
            weight = self._weights.get(src_name, 1.0)

            weighted_sum += sentiment * weight
            total_weight += weight
            sentiments.append(sentiment)
            details[src_name] = dict(source)

        composite_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Confidence: 1 - variance (clipped to [0, 1]).  High variance = low
        # agreement = low confidence.  A single source yields 0.5 confidence
        # (middling — we can't gauge agreement).
        if len(sentiments) <= 1:
            confidence = 0.5
        else:
            mean = sum(sentiments) / len(sentiments)
            variance = sum((s - mean) ** 2 for s in sentiments) / len(sentiments)
            confidence = max(0.0, min(1.0, 1.0 - variance))

        return {
            "composite_score": round(composite_score, 4),
            "source_count": len(sources),
            "confidence": round(confidence, 4),
            "details": details,
        }

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish_updated(
        self, instrument_id: str, merged: dict[str, Any], publish_fn: Any = None
    ) -> None:
        """Build and send a ``feature.updated`` event over NATS.

        Args:
            instrument_id: The instrument the sentiment belongs to.
            merged: The dict returned by :meth:`merge_sentiment`.
            publish_fn: An async callable ``(subject, data) -> None``.
                Typically ``EventBusClient.publish``.  When ``None`` the
                event is only logged without being dispatched.
        """
        features = {
            "sentiment_composite": merged["composite_score"],
            "sentiment_confidence": merged["confidence"],
            "sentiment_source_count": merged["source_count"],
        }

        if publish_fn is None:
            logger.info(
                "Sentiment feature.updated (not published — no publish_fn provided): %s %s",
                instrument_id,
                features,
            )
            return

        subject = "feature.updated"
        envelope = build_envelope(
            subject=subject,
            data=FeatureUpdatedEvent(
                instrument_id=instrument_id, feature_set="sentiment", features=features
            ).model_dump(),
            source="analytics.sentiment.aggregator",
        )

        try:
            await publish_fn(subject, envelope)
            logger.info("Published sentiment feature.updated for %s", instrument_id)
        except Exception as exc:
            msg = f"Failed to publish sentiment feature.updated for {instrument_id}: {exc}"
            logger.warning(msg)
