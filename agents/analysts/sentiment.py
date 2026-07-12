"""Sentiment analyst — evaluates market mood from news and social signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, Field

from agents.analysts.base import BaseAnalyst
from agents.protocol import AgentVote, AnalystSignal

if TYPE_CHECKING:
    from agents.protocol import AnalystInput

SENTIMENT_SYSTEM_PROMPT = """Sei un analista specializzato in sentiment di mercato.
Valuti l'umore del mercato basandoti su dati di sentiment da news e social media.

Analizza:
1. Il sentiment complessivo (molto negativo → molto positivo)
2. La divergenza tra sentiment delle news e sentiment social
3. Eventuali shift improvvisi di sentiment (possibili capovolgimenti)
4. Il tono del mercato: paura, avidità, incertezza, euforia

Produci un segnale di trading con direzione e confidenza.
"""


class SentimentResponse(BaseModel):
    """Structured response from the sentiment LLM call."""

    direction: str = Field(..., pattern=r"^(buy|sell|hold)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)


class SentimentAnalyst(BaseAnalyst):
    """Analyst that evaluates market sentiment from news and social signals."""

    @property
    def blind_spot(self) -> str:
        return "Ignora prezzi e fondamentali — si basa solo su sentiment e news"

    @property
    def name(self) -> str:
        return "sentiment"

    async def analyze(self, data: AnalystInput) -> AnalystSignal:
        scores: dict[str, Any] = data.agent_specific_data.get("sentiment", {})

        news = scores.get("news", 0.0)
        social = scores.get("social", 0.0)
        overall = scores.get("overall", (news + social) / 2 if news or social else 0.0)
        fear_greed = scores.get("fear_greed", 50)

        user_prompt = (
            f"Strumento: {data.instrument}\n\n"
            f"Dati di sentiment:\n"
            f"- Sentiment news: {news:.2f} (-1.0 negativo, +1.0 positivo)\n"
            f"- Sentiment social: {social:.2f}\n"
            f"- Sentiment complessivo: {overall:.2f}\n"
            f"- Indice Fear & Greed: {fear_greed}/100\n\n"
            f"Indica la tua direzione (buy/sell/hold), "
            f"confidenza (0.0-1.0) e reasoning dettagliato."
        )

        raw = await self._llm.structured_call(
            system_prompt=SENTIMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SentimentResponse,
            temperature=self._config.llm_temperature,
            timeout_s=self._config.llm_timeout_s,
        )
        resp = cast(SentimentResponse, raw)

        metadata: dict[str, Any] = {
            "news_sentiment": news,
            "social_sentiment": social,
            "overall_sentiment": overall,
            "fear_greed_index": fear_greed,
            "sentiment_score": resp.sentiment_score,
        }

        direction: Literal["buy", "sell", "hold"] = resp.direction  # type: ignore[assignment]
        return AnalystSignal(
            source="sentiment",
            vote=AgentVote(
                direction=direction, confidence=resp.confidence, reasoning=resp.reasoning
            ),
            metadata=metadata,
            blind_spot=self.blind_spot,
        )
