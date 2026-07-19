"""Technical analyst — price-action and volume-based trading signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, Field

from agents.analysts.base import BaseAnalyst
from agents.protocol import AgentVote, AnalystSignal
from core.logging import get_logger

logger = get_logger("oracle.agents.technical")

if TYPE_CHECKING:
    from agents.protocol import AnalystInput

SYSTEM_PROMPT = """Sei un analista tecnico specializzato in price action e volumi.
Analizzi i seguenti indicatori per generare segnali di trading:

- RSI(14): identifica ipertato (>70) e ipervenduto (<30)
- MACD: crossover rialzista (linea MACD > segnale) o ribassista (MACD < segnale)
- Bollinger Bands: prezzo vicino banda superiore (ipercomprato) o inferiore (ipervenduto)
- SMA(50), SMA(200): trend primario (SMA50 > SMA200 = uptrend, SMA50 < SMA200 = downtrend)
- Volume: volume relativo alto conferma il movimento, basso suggerisce debolezza

Produci un verdetto strutturato con direzione (buy/sell/hold),
confidence (0.0-1.0), reasoning dettagliato e risk_score opzionale."""


class TechnicalResponse(BaseModel):
    """Structured response from the technical LLM call."""

    direction: Literal["buy", "sell", "hold"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)


class TechnicalAnalyst(BaseAnalyst):
    """Analyst that evaluates technical indicators and produces trading signals."""

    @property
    def blind_spot(self) -> str:
        return "Ignora fondamentali e macro — analizza solo prezzo e volumi"

    @property
    def name(self) -> str:
        return "technical"

    async def analyze(self, data: AnalystInput) -> AnalystSignal:
        """Analyze technical indicators and return a structured signal."""
        try:
            return await self._analyze_impl(data)
        except Exception as exc:
            logger.warning("TechnicalAnalyst LLM error", exc_info=exc)
            return AnalystSignal(
                source="technical",
                vote=AgentVote(direction="hold", confidence=0.0, reasoning=f"LLM error: {exc}"),
                metadata={},
                blind_spot=self.blind_spot,
            )

    async def _analyze_impl(self, data: AnalystInput) -> AnalystSignal:
        indicators: dict[str, Any] = data.agent_specific_data
        prompt = self._build_prompt(data.instrument, indicators)
        response = cast(
            TechnicalResponse,
            await self._llm.structured_call(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                response_model=TechnicalResponse,
                temperature=self._config.llm_temperature,
                timeout_s=self._config.llm_timeout_s,
            ),
        )

        return AnalystSignal(
            source="technical",
            vote=AgentVote(
                direction=response.direction,
                confidence=response.confidence,
                reasoning=response.reasoning,
                risk_score=response.risk_score,
            ),
            metadata={"indicators": indicators},
            blind_spot=self.blind_spot,
        )

    def _build_prompt(self, instrument: str, indicators: dict[str, Any]) -> str:
        """Format indicator values into an analysis prompt."""

        lines: list[str] = [f"Analisi tecnica per {instrument}:", ""]

        rsi = indicators.get("rsi", "N/D")
        lines.append(f"RSI(14): {rsi}")
        if isinstance(rsi, (int, float)):
            if rsi > 70:
                lines.append("  -> Ipercomprato (possibile inversione ribassista)")
            elif rsi < 30:
                lines.append("  -> Ipervenduto (possibile inversione rialzista)")
            else:
                lines.append("  -> Neutro")

        macd = indicators.get("macd", {})
        if isinstance(macd, dict):
            macd_line = macd.get("macd", "N/D")
            signal = macd.get("signal", "N/D")
            histogram = macd.get("histogram", "N/D")
            lines.append(f"MACD linea: {macd_line}")
            lines.append(f"MACD segnale: {signal}")
            lines.append(f"MACD istogramma: {histogram}")
            if isinstance(macd_line, (int, float)) and isinstance(signal, (int, float)):
                if macd_line > signal:
                    lines.append("  -> Crossover rialzista (bullish)")
                else:
                    lines.append("  -> Crossover ribassista (bearish)")

        bb = indicators.get("bollinger_bands", {})
        if isinstance(bb, dict):
            upper = bb.get("upper", "N/D")
            middle = bb.get("middle", "N/D")
            lower = bb.get("lower", "N/D")
            lines.append(f"Bollinger Banda Superiore: {upper}")
            lines.append(f"Bollinger Banda Media: {middle}")
            lines.append(f"Bollinger Banda Inferiore: {lower}")
            price = indicators.get("price", "N/D")
            if (
                isinstance(price, (int, float))
                and isinstance(upper, (int, float))
                and isinstance(lower, (int, float))
            ):
                if price >= upper:
                    lines.append("  -> Prezzo vicino banda superiore")
                elif price <= lower:
                    lines.append("  -> Prezzo vicino banda inferiore")
                else:
                    lines.append("  -> Prezzo all'interno delle bande")

        sma50 = indicators.get("sma_50", "N/D")
        sma200 = indicators.get("sma_200", "N/D")
        lines.append(f"SMA(50): {sma50}")
        lines.append(f"SMA(200): {sma200}")
        if isinstance(sma50, (int, float)) and isinstance(sma200, (int, float)):
            if sma50 > sma200:
                lines.append("  -> Trend rialzista (SMA50 > SMA200)")
            else:
                lines.append("  -> Trend ribassista (SMA50 < SMA200)")

        volume = indicators.get("volume", {})
        if isinstance(volume, dict):
            relative = volume.get("relative", "N/D")
            lines.append(f"Volume relativo: {relative}")
            if isinstance(relative, (int, float)):
                if relative > 1.5:
                    lines.append("  -> Volume alto — conferma il movimento")
                elif relative < 0.5:
                    lines.append("  -> Volume basso — movimento debole")
                else:
                    lines.append("  -> Volume normale")

        lines.append("")
        lines.append("Produce una valutazione tecnica completa.")

        return "\n".join(lines)
