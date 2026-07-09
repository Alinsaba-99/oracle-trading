"""M7 Sentiment NLP — FinBERT news classifier, news processor, and aggregator."""

from analytics.sentiment.aggregator import SentimentAggregator
from analytics.sentiment.config import SentimentSettings
from analytics.sentiment.errors import SentimentError
from analytics.sentiment.finbert import FinBERTClassifier
from analytics.sentiment.news import NewsSentimentProcessor

__all__ = [
    "FinBERTClassifier",
    "NewsSentimentProcessor",
    "SentimentAggregator",
    "SentimentError",
    "SentimentSettings",
]
