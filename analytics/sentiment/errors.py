"""Sentiment analysis error hierarchy."""

from analytics.common.errors import AnalyticsError


class SentimentError(AnalyticsError):
    """Base for all sentiment analysis errors."""
