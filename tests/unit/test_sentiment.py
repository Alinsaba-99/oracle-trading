"""Tests for M7 Sentiment NLP — FinBERT, news processor, and aggregator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from analytics.sentiment.aggregator import SentimentAggregator
from analytics.sentiment.config import SentimentSettings
from analytics.sentiment.errors import SentimentError
from analytics.sentiment.finbert import FinBERTClassifier
from analytics.sentiment.news import NewsSentimentProcessor

# ======================================================================
# Helpers
# ======================================================================


def _make_pipeline(return_value: list) -> MagicMock:
    """Build a mock transformers pipeline that returns *return_value*."""
    pipe = MagicMock()
    pipe.return_value = return_value
    return pipe


# ======================================================================
# FinBERTClassifier
# ======================================================================


class TestFinBERTClassifier:
    """Coverage for FinBERT lazy-loading, inference, and graceful degradation."""

    def test_lazy_load_no_pipeline_before_first_call(self) -> None:
        """Model is NOT loaded at construction time."""
        clf = FinBERTClassifier()
        assert clf._pipeline is None

    def test_classify_returns_top_label(self) -> None:
        """classify() returns the highest-confidence label per text."""
        pipe = _make_pipeline(
            [
                [
                    {"label": "positive", "score": 0.90},
                    {"label": "neutral", "score": 0.07},
                    {"label": "negative", "score": 0.03},
                ],
                [
                    {"label": "negative", "score": 0.85},
                    {"label": "neutral", "score": 0.10},
                    {"label": "positive", "score": 0.05},
                ],
            ]
        )
        clf = FinBERTClassifier()
        clf._pipeline = pipe  # skip _load_pipeline

        results = clf.classify(["Great earnings report!", "Profit warning issued."])

        assert results is not None
        assert len(results) == 2
        assert results[0]["label"] == "positive"
        assert results[0]["score"] == 0.90
        assert results[1]["label"] == "negative"
        assert results[1]["score"] == 0.85

    def test_classify_handles_empty_list(self) -> None:
        """Empty input list returns empty result list."""
        pipe = _make_pipeline([])
        clf = FinBERTClassifier()
        clf._pipeline = pipe
        results = clf.classify([])
        assert results is not None
        assert results == []

    def test_classify_neutral_scores(self) -> None:
        """Neutral texts produce neutral label."""
        pipe = _make_pipeline(
            [
                [
                    {"label": "neutral", "score": 0.88},
                    {"label": "positive", "score": 0.07},
                    {"label": "negative", "score": 0.05},
                ]
            ]
        )
        clf = FinBERTClassifier()
        clf._pipeline = pipe
        results = clf.classify(["The company released its quarterly report."])
        assert results is not None
        assert results[0]["label"] == "neutral"

    def test_classify_returns_none_on_load_error(self) -> None:
        """Graceful degradation when model loading fails."""
        clf = FinBERTClassifier()
        with patch.object(clf, "_load_pipeline", side_effect=SentimentError("no model")):
            results = clf.classify(["test"])
            assert results is None

    def test_classify_returns_none_on_inference_error(self) -> None:
        """Graceful degradation when inference raises."""
        pipe = MagicMock()
        pipe.side_effect = RuntimeError("GPU OOM")
        clf = FinBERTClassifier()
        clf._pipeline = pipe
        results = clf.classify(["crash"])
        assert results is None


# ======================================================================
# NewsSentimentProcessor
# ======================================================================


class TestNewsSentimentProcessor:
    """Coverage for news fetching and scoring."""

    # -- fetch_news ---------------------------------------------------

    def test_fetch_news_returns_empty_when_no_api_key(self) -> None:
        """No configured API key returns empty list with no HTTP call."""
        settings = SentimentSettings(alphaai_api_key="")
        proc = NewsSentimentProcessor(settings=settings)
        articles = proc.fetch_news("AAPL")
        assert articles == []

    @patch("analytics.sentiment.news.httpx.get")
    def test_fetch_news_parses_response(self, mock_get: MagicMock) -> None:
        """API response is correctly parsed into article dicts."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "Apple hits record high",
                    "description": "...",
                    "url": "...",
                    "published_at": "2025-01-01",
                },
                {
                    "title": "Apple supply chain concerns",
                    "description": "...",
                    "url": "...",
                    "published_at": "2025-01-02",
                },
            ]
        }
        mock_get.return_value = mock_response

        settings = SentimentSettings(alphaai_api_key="test-key")
        proc = NewsSentimentProcessor(settings=settings)
        articles = proc.fetch_news("AAPL", max_articles=5)

        assert len(articles) == 2
        assert articles[0]["title"] == "Apple hits record high"
        assert articles[1]["title"] == "Apple supply chain concerns"

    @patch("analytics.sentiment.news.httpx.get")
    def test_fetch_news_raises_on_http_error(self, mock_get: MagicMock) -> None:
        """HTTP errors propagate as SentimentError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        settings = SentimentSettings(alphaai_api_key="bad-key")
        proc = NewsSentimentProcessor(settings=settings)

        with pytest.raises(SentimentError, match="Failed to fetch news for AAPL"):
            proc.fetch_news("AAPL")

    @patch("analytics.sentiment.news.httpx.get")
    def test_fetch_news_respects_max_articles(self, mock_get: MagicMock) -> None:
        """max_articles limits the returned article count."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [{"title": f"Article {i}"} for i in range(50)]
        }
        mock_get.return_value = mock_response

        settings = SentimentSettings(alphaai_api_key="key")
        proc = NewsSentimentProcessor(settings=settings)
        articles = proc.fetch_news("MSFT", max_articles=10)
        assert len(articles) == 10

    # -- score_articles -----------------------------------------------

    def test_score_articles_empty_returns_zeroes(self) -> None:
        """Empty article list yields neutral metrics."""
        proc = NewsSentimentProcessor()
        result = proc.score_articles([])
        assert result == {"avg_sentiment": 0.0, "volume": 0, "top_headlines": []}

    def test_score_articles_positive_sentiment(self) -> None:
        """Positive articles produce positive avg_sentiment."""
        classifier = FinBERTClassifier()
        with patch.object(
            classifier,
            "classify",
            return_value=[
                {"label": "positive", "score": 0.95},
                {"label": "positive", "score": 0.80},
            ],
        ):
            proc = NewsSentimentProcessor(classifier=classifier)
            articles = [
                {"title": "Record revenue", "description": "Company beats estimates"},
                {"title": "Strong guidance", "description": "Outlook improved"},
            ]
            result = proc.score_articles(articles)
            assert result["avg_sentiment"] > 0.0
            assert result["volume"] == 2
            assert "Record revenue" in result["top_headlines"]

    def test_score_articles_negative_sentiment(self) -> None:
        """Negative articles produce negative avg_sentiment."""
        classifier = FinBERTClassifier()
        with patch.object(
            classifier,
            "classify",
            return_value=[
                {"label": "negative", "score": 0.92},
                {"label": "negative", "score": 0.87},
            ],
        ):
            proc = NewsSentimentProcessor(classifier=classifier)
            articles = [
                {"title": "Profit warning", "description": "EPS misses consensus"},
                {"title": "Downgrade", "description": "Analyst cuts target"},
            ]
            result = proc.score_articles(articles)
            assert result["avg_sentiment"] < 0.0
            assert result["volume"] == 2

    def test_score_articles_mixed_sentiment(self) -> None:
        """Mixed articles produce intermediate avg_sentiment."""
        classifier = FinBERTClassifier()
        with patch.object(
            classifier,
            "classify",
            return_value=[
                {"label": "positive", "score": 0.90},
                {"label": "negative", "score": 0.85},
            ],
        ):
            proc = NewsSentimentProcessor(classifier=classifier)
            articles = [
                {"title": "Good news", "description": "Bullish signal"},
                {"title": "Bad news", "description": "Bearish signal"},
            ]
            result = proc.score_articles(articles)
            # 1.0*0.9 + (-1.0)*0.85 = 0.05 → close to neutral
            assert -0.1 <= result["avg_sentiment"] <= 0.1
            assert result["volume"] == 2

    def test_score_articles_classifier_none_fallback(self) -> None:
        """When classifier returns None the fallback is neutral."""
        classifier = FinBERTClassifier()
        with patch.object(classifier, "classify", return_value=None):
            proc = NewsSentimentProcessor(classifier=classifier)
            articles = [{"title": "Something", "description": "happened"}]
            result = proc.score_articles(articles)
            assert result["avg_sentiment"] == 0.0
            assert result["volume"] == 1  # still counted


# ======================================================================
# SentimentAggregator
# ======================================================================


class TestSentimentAggregator:
    """Coverage for sentiment merging, confidence, and publishing."""

    def test_merge_empty_sources(self) -> None:
        """Empty source list returns neutral/zero values."""
        agg = SentimentAggregator()
        result = agg.merge_sentiment([])
        assert result["composite_score"] == 0.0
        assert result["source_count"] == 0
        assert result["confidence"] == 0.0
        assert result["details"] == {}

    def test_merge_single_source(self) -> None:
        """Single source returns its score as-is, confidence 0.5."""
        agg = SentimentAggregator()
        sources = [{"source": "news", "avg_sentiment": 0.42, "volume": 10}]
        result = agg.merge_sentiment(sources)
        assert result["composite_score"] == 0.42
        assert result["source_count"] == 1
        assert result["confidence"] == 0.5
        assert "news" in result["details"]

    def test_merge_two_sources(self) -> None:
        """Two sources produce weighted composite."""
        agg = SentimentAggregator()
        sources = [
            {"source": "news", "avg_sentiment": 0.8, "volume": 10},
            {"source": "social", "avg_sentiment": 0.2, "volume": 50},
        ]
        result = agg.merge_sentiment(sources)
        # Expected: (0.8 * 0.5) + (0.2 * 0.2) / (0.5 + 0.2) = (0.4 + 0.04) / 0.7 ≈ 0.6286
        expected = (0.8 * 0.5 + 0.2 * 0.2) / 0.7
        assert abs(result["composite_score"] - expected) < 0.001
        assert result["source_count"] == 2

    def test_merge_three_sources_with_earnings(self) -> None:
        """Three sources including earnings produce correct weighted score."""
        agg = SentimentAggregator()
        sources = [
            {"source": "news", "avg_sentiment": 0.5, "volume": 20},
            {"source": "social", "avg_sentiment": -0.3, "volume": 100},
            {"source": "earnings", "avg_sentiment": 0.9, "volume": 1},
        ]
        result = agg.merge_sentiment(sources)
        # (0.5*0.5) + (-0.3*0.2) + (0.9*0.3) / (0.5+0.2+0.3)
        expected = (0.5 * 0.5 + (-0.3) * 0.2 + 0.9 * 0.3) / 1.0
        assert abs(result["composite_score"] - expected) < 0.001
        assert result["source_count"] == 3

    def test_merge_confidence_two_sources_agree(self) -> None:
        """Two sources with same sentiment → high confidence."""
        agg = SentimentAggregator()
        sources = [
            {"source": "news", "avg_sentiment": 0.5, "volume": 10},
            {"source": "social", "avg_sentiment": 0.5, "volume": 20},
        ]
        result = agg.merge_sentiment(sources)
        # Zero variance → confidence = 1.0
        assert result["confidence"] == 1.0

    def test_merge_confidence_two_sources_disagree(self) -> None:
        """Two sources with opposite sentiment → low confidence."""
        agg = SentimentAggregator()
        sources = [
            {"source": "news", "avg_sentiment": 1.0, "volume": 10},
            {"source": "social", "avg_sentiment": -1.0, "volume": 20},
        ]
        result = agg.merge_sentiment(sources)
        # Variance = ((1 - 0)^2 + (-1 - 0)^2) / 2 = 1.0 → confidence = 0.0
        assert result["confidence"] == 0.0

    def test_merge_custom_weights(self) -> None:
        """Custom weight overrides are respected."""
        agg = SentimentAggregator(weights={"news": 0.8, "social": 0.2})
        sources = [
            {"source": "news", "avg_sentiment": 1.0, "volume": 5},
            {"source": "social", "avg_sentiment": 0.0, "volume": 5},
        ]
        result = agg.merge_sentiment(sources)
        expected = (1.0 * 0.8 + 0.0 * 0.2) / 1.0  # 0.8
        assert abs(result["composite_score"] - expected) < 0.001

    def test_merge_unknown_source_uses_weight_one(self) -> None:
        """Unknown source names are assigned weight 1.0."""
        agg = SentimentAggregator()
        sources = [{"source": "custom_llm", "avg_sentiment": 0.5, "volume": 3}]
        result = agg.merge_sentiment(sources)
        assert result["composite_score"] == 0.5
        assert result["source_count"] == 1

    # -- publish_updated ----------------------------------------------

    async def test_publish_noop_when_no_fn(self) -> None:
        """publish_updated logs but does not raise when publish_fn is None."""
        agg = SentimentAggregator()
        merged = {"composite_score": 0.42, "source_count": 2, "confidence": 0.8, "details": {}}
        # Should complete without error
        await agg.publish_updated("AAPL", merged, publish_fn=None)

    async def test_publish_calls_fn_with_correct_subject(self) -> None:
        """publish_updated invokes publish_fn with 'feature.updated' subject."""
        calls: list[tuple[str, object]] = []

        async def fake_publish(subject: str, data: object) -> None:
            calls.append((subject, data))

        agg = SentimentAggregator()
        merged = {"composite_score": -0.15, "source_count": 1, "confidence": 0.5, "details": {}}
        await agg.publish_updated("MSFT", merged, publish_fn=fake_publish)

        assert len(calls) == 1
        subject, envelope = calls[0]
        assert subject == "feature.updated"
        assert envelope["subject"] == "feature.updated"
        assert envelope["source"] == "analytics.sentiment.aggregator"
        data = envelope["data"]
        assert data["instrument_id"] == "MSFT"
        assert data["feature_set"] == "sentiment"
        assert data["features"]["sentiment_composite"] == -0.15
        assert data["features"]["sentiment_confidence"] == 0.5
