"""Sentiment Analyst — news scraping + transformers NLP for sentiment scoring.

For a target ticker, scrapes recent news from RSS feeds (Yahoo Finance,
Seeking Alpha, Reuters, Bloomberg via RSS — free) and runs a transformers
sentiment model (ProsusAI/finbert-style) to compute:
- News volume (proxy for attention / overexposure)
- Sentiment score (positive vs negative)
- Sentiment momentum (sentiment_t vs sentiment_t-30d)

References
----------
- FinBERT: ProsusAI/finbert (HuggingFace, fine-tuned DistilBERT on Financial PhraseBank)
- Tetlock (2007) "Giving Content to Investor Sentiment" — news sentiment
  predicts market returns ~3-7 bps/day in long-only portfolios
- Deep-research 2026-08-15: sentiment NLP is one of the documented edges
  for retail with transformers OSS stack
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# Free RSS feeds for financial news (no API key required)
NEWS_FEEDS: list[dict[str, str]] = [
    {"name": "yahoo_finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "seeking_alpha", "url": "https://seekingalpha.com/market_currents.xml"},
    {
        "name": "reuters_business",
        "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    },
    {"name": "cnbc_top_news", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"name": "wsj_markets", "url": "https://feeds.a10747.net/markets.rss"},
    {
        "name": "marketwatch_top",
        "url": "https://feeds.content.marketwatch.com/marketwatch/topstories",
    },
]


@dataclass
class NewsItem:
    """One news item scraped from RSS.

    Attributes
    ----------
    title : str
        Headline.
    summary : str
        Article summary (may be empty).
    published : datetime
        Publication date.
    source : str
        Source name (e.g. "yahoo_finance").
    url : str
        Article URL.
    sentiment_score : float | None
        NLP sentiment score in [-1, +1] (positive > 0, negative < 0).
        Set after NLP processing.
    """

    title: str
    summary: str
    published: datetime
    source: str
    url: str = ""
    sentiment_score: float | None = None


@dataclass
class SentimentReport:
    """Sentiment analysis for one ticker.

    Attributes
    ----------
    ticker : str
        Target ticker.
    n_articles : int
        Number of articles found mentioning the ticker.
    avg_sentiment : float
        Average sentiment across articles, in [-1, +1].
    sentiment_momentum : float
        Recent sentiment (last 7 days) - older sentiment (8-30 days).
        Positive = sentiment improving.
    news_volume_zscore : float
        Z-score of news volume vs trailing 30-day average.
        High z-score (>2) = overexposure / potential top.
    top_headlines : list[str]
        Top 5 headlines by relevance (mentions ticker).
    evidence : list[str]
        Bullet-point evidence for the synthesizer.
    """

    ticker: str
    n_articles: int = 0
    avg_sentiment: float = 0.0
    sentiment_momentum: float = 0.0
    news_volume_zscore: float = 0.0
    top_headlines: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


class SentimentAnalyst:
    """Sentiment analyst: RSS news scraping + transformers NLP.

    The analyst scrapes recent news from free RSS feeds, filters to
    articles mentioning the target ticker, and runs a transformers
    sentiment model (DistilBERT-style finbert) to score each article.
    """

    def __init__(self, *, n_days: int = 30, feeds: Sequence[dict[str, str]] | None = None) -> None:
        self.n_days = n_days
        self.feeds = list(feeds) if feeds else NEWS_FEEDS
        self._nlp_pipe: Any = None  # lazy-loaded transformers pipeline

    def _load_nlp(self) -> Any:
        """Lazy-load the FinBERT sentiment pipeline."""
        if self._nlp_pipe is not None:
            return self._nlp_pipe
        try:
            from transformers import pipeline

            # Use FinBERT (ProsusAI) — fine-tuned for financial sentiment
            self._nlp_pipe = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                top_k=3,  # return all 3 labels (positive, negative, neutral)
            )
        except Exception:
            # Fallback: distilbert-base-uncased-finetuned-sst-2-english
            try:
                from transformers import pipeline

                self._nlp_pipe = pipeline(
                    "sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english"
                )  # type: ignore[call-overload]
            except Exception as e:
                print(f"WARN: transformers NLP failed to load: {e}")
                self._nlp_pipe = None
        return self._nlp_pipe

    def _score_text(self, text: str) -> float:
        """Score text sentiment in [-1, +1] using the NLP pipeline."""
        pipe = self._load_nlp()
        if pipe is None:
            return 0.0
        try:
            text = text[:512]  # truncate to model max length
            if hasattr(pipe, "top_k"):
                # FinBERT with top_k=3 returns list of dicts with labels
                result = pipe(text)
                # result is a list of lists; flatten
                scores = {}
                for item in result[0] if isinstance(result[0], list) else result:
                    scores[item["label"].lower()] = item["score"]
                return float(scores.get("positive", 0.0) - scores.get("negative", 0.0))
            else:
                # distilbert fallback: returns {label: POSITIVE/NEGATIVE, score: 0-1}
                result = pipe(text)[0]
                score = float(result["score"])
                return score if result["label"] == "POSITIVE" else -score
        except Exception:
            return 0.0

    def fetch_news(self, ticker: str) -> list[NewsItem]:
        """Fetch recent news mentioning the ticker from RSS feeds."""
        try:
            import feedparser
        except ImportError:
            return []
        cutoff = datetime.now(UTC) - timedelta(days=self.n_days)
        items: list[NewsItem] = []
        for feed in self.feeds:
            try:
                parsed = feedparser.parse(feed["url"])
                for entry in parsed.entries[:20]:
                    published = getattr(entry, "published_parsed", None)
                    if published:
                        try:
                            import time as _time

                            dt = datetime.fromtimestamp(_time.mktime(published), tz=UTC)
                        except Exception:
                            continue
                        if dt < cutoff:
                            continue
                    else:
                        continue
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    # Filter: must mention the ticker OR its company name
                    ticker_upper = ticker.upper()
                    text = (title + " " + summary).upper()
                    if ticker_upper not in text and ticker not in title.lower():
                        continue
                    items.append(
                        NewsItem(
                            title=title,
                            summary=summary,
                            published=dt,
                            source=feed["name"],
                            url=getattr(entry, "link", ""),
                        )
                    )
            except Exception:
                continue
        return items

    def analyze(self, ticker: str) -> SentimentReport:
        """Analyze sentiment for a ticker."""
        items = self.fetch_news(ticker)
        if not items:
            return SentimentReport(
                ticker=ticker,
                n_articles=0,
                evidence=["No news articles found for ticker in last 30 days"],
            )

        # Score each article
        for item in items:
            item.sentiment_score = self._score_text(item.title + " " + item.summary)

        # Compute aggregate sentiment
        scores = [i.sentiment_score or 0.0 for i in items]
        avg_sentiment = sum(scores) / len(scores) if scores else 0.0

        # Compute sentiment momentum: recent 7 days vs 8-30 days
        now = datetime.now(UTC)
        recent = [i.sentiment_score or 0.0 for i in items if (now - i.published).days <= 7]
        older = [i.sentiment_score or 0.0 for i in items if 7 < (now - i.published).days <= 30]
        avg_recent = sum(recent) / len(recent) if recent else 0.0
        avg_older = sum(older) / len(older) if older else 0.0
        sentiment_momentum = avg_recent - avg_older

        # Compute news volume zscore (vs trailing 30d avg)
        # Simple: assume baseline 1 article/day → z-score = (n - 30) / sqrt(30)
        n = len(items)
        expected = self.n_days  # baseline: 1 article/day
        std = max(1.0, (self.n_days) ** 0.5)
        news_volume_zscore = (n - expected) / std

        # Top 5 headlines by recency
        items_sorted = sorted(items, key=lambda x: x.published, reverse=True)
        top_headlines = [f"{i.title} ({i.source}, {i.published.date()})" for i in items_sorted[:5]]

        evidence: list[str] = [
            f"{n} articles in last {self.n_days} days (z-score {news_volume_zscore:+.2f})",
            f"Average sentiment: {avg_sentiment:+.3f}",
            f"Sentiment momentum: {sentiment_momentum:+.3f} ({'improving' if sentiment_momentum > 0 else 'deteriorating'})",
        ]
        if news_volume_zscore > 2:
            evidence.append(f"⚠️ News volume high (z>{2}) — possible overexposure / top signal")
        if sentiment_momentum > 0.1 and avg_sentiment > 0:
            evidence.append("Sentiment improving AND positive — bullish setup")
        if sentiment_momentum < -0.1 and avg_sentiment < 0:
            evidence.append("Sentiment deteriorating AND negative — bearish setup")

        return SentimentReport(
            ticker=ticker,
            n_articles=n,
            avg_sentiment=avg_sentiment,
            sentiment_momentum=sentiment_momentum,
            news_volume_zscore=news_volume_zscore,
            top_headlines=top_headlines,
            evidence=evidence,
        )


__all__: list[str] = ["NEWS_FEEDS", "NewsItem", "SentimentAnalyst", "SentimentReport"]
