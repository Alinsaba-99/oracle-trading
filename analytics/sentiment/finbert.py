"""FinBERT classifier for financial sentiment analysis.

Uses the ProsusAI/finbert model (distilled BERT fine-tuned on financial news).
Lazy-loads the transformers pipeline on the first call and degrades gracefully
when the model is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from analytics.sentiment.errors import SentimentError

logger = logging.getLogger(__name__)


class FinBERTClassifier:
    """Financial news sentiment classifier built on ProsusAI/finbert.

    The underlying HuggingFace pipeline is created on the first call to
    :meth:`classify` rather than at construction time so that importing the
    module is cheap and the model weights are only loaded when needed.

    If the model or its dependencies cannot be resolved a warning is logged
    and ``None`` is returned from :meth:`classify` -- the caller decides how
    to treat an unavailable classifier.
    """

    LABELS: ClassVar[set[str]] = {"positive", "negative", "neutral"}

    def __init__(self, model_name: str = "ProsusAI/finbert", max_length: int = 512) -> None:
        self._model_name = model_name
        self._max_length = max_length
        self._pipeline: Any = None  # transformers pipeline

    # ------------------------------------------------------------------
    # Lazy-load the pipeline
    # ------------------------------------------------------------------

    def _load_pipeline(self) -> Any:
        """Return the transformers pipeline, creating it on first access."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification",
                model=self._model_name,
                tokenizer=self._model_name,
                max_length=self._max_length,
                truncation=True,
                top_k=None,
            )
        except Exception as exc:
            msg = f"Failed to load FinBERT model '{self._model_name}': {exc}"
            logger.warning(msg)
            raise SentimentError(msg) from exc

        return self._pipeline

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, texts: list[str]) -> list[dict[str, Any]] | None:
        """Classify texts and return per-text sentiment results.

        For each input text the returned dict carries the top predicted
        ``label`` (one of ``positive``, ``negative``, ``neutral``) and its
        ``score`` (0-1 confidence)::

            [{"label": "positive", "score": 0.98}, ...]

        Returns ``None`` when the model could not be loaded (a warning has
        already been logged).
        """
        try:
            pipe = self._load_pipeline()
        except SentimentError:
            return None

        try:
            results: list[list[dict[str, Any]]] = pipe(texts)
        except Exception as exc:
            msg = f"FinBERT inference failed: {exc}"
            logger.warning(msg)
            return None

        # pipeline(..., top_k=None) returns a list-of-lists; pick the top label per text.
        return [max(item, key=lambda x: x["score"]) for item in results]
