"""Macro-economic analyst agent.

Analyses GDP, CPI, interest rates, unemployment and other macro indicators
provided via :attr:`AnalystInput.agent_specific_data` and produces a structured
trading signal through an LLM call.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from agents.analysts.base import BaseAnalyst
from agents.protocol import AgentVote, AnalystSignal
from core.logging import get_logger

if TYPE_CHECKING:
    from agents.protocol import AnalystInput

logger = get_logger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Sei un macro economista specializzato in mercati finanziari.\n"
    "Analizza i seguenti indicatori macroeconomici e produci un segnale di trading.\n\n"
    "Regole:\n"
    "- Non fare previsioni a lungo termine\n"
    "- Considera solo trend in atto, non scenari speculativi\n"
    "- Output JSON valido con: direction, confidence, reasoning, risk_score\n"
    '- direction: "buy" = rialzo atteso, "sell" = ribasso atteso, "hold" = neutrale\n'
    "- confidence: 0.0-1.0\n"
    "- reasoning: massimo 4 frasi\n"
    "- risk_score: 0 (sicuro) - 1 (rischioso)\n"
    "- Blind spot dell'analista macro: ignora price action e volumi"
)

REQUIRED_INDICATORS: tuple[str, ...] = ("gdp", "cpi", "interest_rate", "unemployment")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_user_prompt(instrument: str, data: dict[str, Any]) -> str:
    """Format macro indicators into the user-facing prompt."""
    lines: list[str] = [f"Analisi Macroeconomica per {instrument}:\n"]

    for key in REQUIRED_INDICATORS:
        val = data.get(key)
        if val is not None:
            lines.append(f"- {key.replace('_', ' ').title()}: {val}")
        else:
            lines.append(f"- {key.replace('_', ' ').title()}: N/D")

    extra_keys = [k for k in data if k not in REQUIRED_INDICATORS]
    if extra_keys:
        lines.append("")
        lines.append("Altri indicatori:")
        for key in extra_keys:
            lines.append(f"- {key.replace('_', ' ').title()}: {data[key]}")

    lines.append(
        "\nFornisci la tua analisi in formato JSON con: direction, confidence, "
        "reasoning, risk_score."
    )
    return "\n".join(lines)


def _compute_prompt_hash(prompt: str) -> str:
    """Deterministic short hash of the prompt text."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


# ── Analyst Implementation ────────────────────────────────────────────────────


class MacroAnalyst(BaseAnalyst):
    """Macro-economic trend analyst.

    Examines fundamental macro indicators (GDP, CPI, rates, employment)
    provided in ``data.agent_specific_data`` and produces a directional
    trading signal.
    """

    @property
    def blind_spot(self) -> str:
        return "Ignora price action e volumi — si concentra solo su trend macro"

    @property
    def name(self) -> str:
        return "macro"

    async def analyze(self, data: AnalystInput) -> AnalystSignal:
        """Analyse macro indicators and return a structured signal.

        Parameters
        ----------
        data : AnalystInput
            Input containing instrument, market state and agent-specific data.

        Returns
        -------
        AnalystSignal
            Structured signal with vote, metadata and provenance info.

        Raises
        ------
        AgentError
            On unrecoverable LLM failures.
        """
        user_prompt = _build_user_prompt(data.instrument, data.agent_specific_data)

        try:
            result = await self._llm.structured_call(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=AgentVote,
                temperature=self._config.llm_temperature,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            logger.exception("LLM structured call failed for macro analyst")
            # Return a safe neutral signal on LLM failure.
            return AnalystSignal(
                source="macro",
                vote=AgentVote(
                    direction="hold",
                    confidence=0.0,
                    reasoning="LLM call failed — unable to produce macro analysis",
                    risk_score=1.0,
                ),
                metadata={"error": "llm_call_failed", "indicators": dict(data.agent_specific_data)},
                blind_spot=self.blind_spot,
                model=self._llm.model_name,
            )

        vote = result if isinstance(result, AgentVote) else AgentVote.model_validate(result)

        metadata = {
            "indicators_used": list(data.agent_specific_data.keys()),
            "indicators": dict(data.agent_specific_data),
        }
        prompt_hash = _compute_prompt_hash(user_prompt)

        return AnalystSignal(
            source="macro",
            vote=vote,
            metadata=metadata,
            blind_spot=self.blind_spot,
            prompt_hash=prompt_hash,
            model=self._llm.model_name,
            tokens_used=0,
        )
