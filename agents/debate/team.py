"""DebateTeam — orchestrates a 2-round structured debate across Bull, Bear,
and Devil's Advocate roles, then scores the quality."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from agents.debate.prompts import BEAR_SYSTEM, BULL_SYSTEM, DEVIL_SYSTEM, REBUTTAL_SYSTEM
from agents.debate.scorer import DebateScorer
from agents.errors import DebateTimeoutError
from agents.protocol import AgentVote, AnalystSignal, DebateResult

if TYPE_CHECKING:
    pass

from core.logging import get_logger

logger = get_logger("oracle.debate")

__all__ = ["DebateTeam"]


# ── Internal response models for structured LLM output ──────────────────────


class _BullResponse(BaseModel, frozen=True):
    """Structured response from the Bull role."""

    thesis: str
    key_indicators: list[str]
    confidence: float  # 0.0-1.0
    direction: str  # buy / sell / hold


class _BearResponse(BaseModel, frozen=True):
    """Structured response from the Bear role."""

    counter_thesis: str
    weaknesses_found: list[str]
    counter_indicators: list[str]
    confidence: float  # 0.0-1.0
    direction: str  # buy / sell / hold


class _DAResponse(BaseModel, frozen=True):
    """Structured response from the Devil's Advocate role."""

    blind_spots: list[str]
    third_way: str | None = None
    synthesis: str


# ── DebateTeam ──────────────────────────────────────────────────────────────


class DebateTeam:
    """Orchestrates a multi-agent debate with Bull, Bear, and Devil's Advocate.

    Two-round structure:
      * Round 1 — Bull presents the bull thesis, Bear contests it, and the
        Devil's Advocate synthesises blind spots.
      * Round 2 (conditional) — if the initial signals diverge beyond a
        threshold, both sides deliver rebuttals.

    Parameters
    ----------
    llm_client:
        An object implementing the ``LLMClient`` protocol (``structured_call``,
        ``model_name``, ``count_tokens``).
    config:
        Optional configuration object (currently unused; reserved for future
        temperature / max-tokens overrides).
    """

    def __init__(self, llm_client: Any, config: Any | None = None) -> None:
        self._llm: Any = llm_client
        self._config = config
        self._scorer = DebateScorer()

    # ── Public API ──────────────────────────────────────────────────────────

    async def debate(
        self, signals: list[AnalystSignal], divergence_threshold: float = 0.3
    ) -> DebateResult:
        """Run a 2-round debate over the provided analyst signals.

        Parameters
        ----------
        signals:
            Signals emitted by analyst agents (macro, technical, sentiment).
        divergence_threshold:
            Minimum divergence value (0.0-1.0) above which a second rebuttal
            round is triggered. Default 0.3.

        Returns
        -------
        DebateResult with round transcripts, optional round 2, optional
        consensus vote, disagreement list, and debate quality score.
        """
        disagreements: list[str] = []

        # ── Round 1: Bull → Bear → Devil's Advocate ──────────────────────
        round_1: dict[str, Any] = {}

        try:
            # 1a. Bull thesis
            bull_prompt = self._extract_bull_signals(signals)
            bull: _BullResponse = await self._call_role(
                system=BULL_SYSTEM, user=bull_prompt, response_model=_BullResponse
            )
            round_1["bull_thesis"] = bull.thesis
            round_1["bull_indicators"] = bull.key_indicators
            round_1["bull_confidence"] = bull.confidence
            round_1["bull_direction"] = bull.direction

            # 1b. Bear contests the bull thesis
            bear_user = (
                f"Bull thesis: {bull.thesis}\n\n"
                f"Bull indicators: {', '.join(bull.key_indicators)}\n\n"
                f"Bear signals:\n{self._extract_bear_signals(signals)}"
            )
            bear: _BearResponse = await self._call_role(
                system=BEAR_SYSTEM, user=bear_user, response_model=_BearResponse
            )
            round_1["bear_critique"] = bear.counter_thesis
            round_1["bear_weaknesses"] = bear.weaknesses_found
            round_1["bear_indicators"] = bear.counter_indicators
            round_1["bear_confidence"] = bear.confidence
            round_1["bear_direction"] = bear.direction

            # 1c. Devil's Advocate synthesis
            da_user = (
                f"Bull thesis: {bull.thesis}\n"
                f"Bull confidence: {bull.confidence}\n\n"
                f"Bear critique: {bear.counter_thesis}\n"
                f"Bear weaknesses found: {', '.join(bear.weaknesses_found)}\n\n"
                f"Blind spots from analysts:\n{self._extract_blind_spots(signals)}"
            )
            da: _DAResponse = await self._call_role(
                system=DEVIL_SYSTEM, user=da_user, response_model=_DAResponse
            )
            round_1["da_blind_spots"] = da.blind_spots
            round_1["da_third_way"] = da.third_way
            round_1["da_synthesis"] = da.synthesis

        except Exception as exc:
            logger.error("debate_round_1_failed", error=str(exc))
            raise DebateTimeoutError(f"Debate round 1 failed: {exc}") from exc

        # ── Divergence check ────────────────────────────────────────────────
        divergence = self._compute_divergence(signals)
        round_2: dict[str, Any] | None = None

        if divergence > divergence_threshold:
            disagreements.append(
                f"High divergence ({divergence:.2f}) — agents disagree on direction."
            )
            # ── Round 2: rebuttals ─────────────────────────────────────────
            try:
                round_2 = await self._run_rebuttal_round(bull, bear)
            except Exception as exc:
                logger.error("debate_round_2_failed", error=str(exc))
                disagreements.append(f"Round 2 failed: {exc}")

        # ── Build consensus ─────────────────────────────────────────────────
        consensus = self._build_consensus(round_1, round_2)

        # ── Score quality ───────────────────────────────────────────────────
        quality = self._scorer.score(
            signals=signals, round_1=round_1, round_2=round_2, consensus=consensus
        )

        return DebateResult(
            round_1=round_1,
            round_2=round_2,
            consensus=consensus,
            disagreements=disagreements,
            debate_quality=quality,
        )

    # ── Internal helpers ───────────────────────────────────────────────────
    async def _call_role(self, system: str, user: str, response_model: type[BaseModel]) -> Any:
        """Execute a single structured LLM call for a debate role."""
        return await self._llm.structured_call(
            system=system, user=user, response_model=response_model, temperature=0.7
        )

    async def _run_rebuttal_round(self, bull: _BullResponse, bear: _BearResponse) -> dict[str, Any]:
        """Execute the second rebuttal round."""
        result: dict[str, Any] = {}

        # Bull rebuttal
        bull_rebuttal_user = (
            f"Your original thesis: {bull.thesis}\n\n"
            f"Criticisms received:\n{chr(10).join(f'- {w}' for w in bear.weaknesses_found)}\n\n"
            f"Respond to each objection and strengthen your case."
        )
        bull_rb: _BullResponse = await self._call_role(
            system=REBUTTAL_SYSTEM + "\n\n" + BULL_SYSTEM,
            user=bull_rebuttal_user,
            response_model=_BullResponse,
        )
        result["bull_rebuttal"] = bull_rb.thesis
        result["bull_rebuttal_confidence"] = bull_rb.confidence
        result["rebuttal_indicators"] = bull_rb.key_indicators

        # Bear counter-rebuttal
        bear_rebuttal_user = (
            f"Bull's rebuttal: {bull_rb.thesis}\n\n"
            f"Your original critique: {bear.counter_thesis}\n\n"
            f"Strengthen your counter-arguments."
        )
        bear_rb: _BearResponse = await self._call_role(
            system=REBUTTAL_SYSTEM + "\n\n" + BEAR_SYSTEM,
            user=bear_rebuttal_user,
            response_model=_BearResponse,
        )
        result["bear_counter"] = bear_rb.counter_thesis
        result["bear_counter_weaknesses"] = bear_rb.weaknesses_found

        return result

    @staticmethod
    def _extract_bull_signals(signals: list[AnalystSignal]) -> str:
        """Filter buy / positive signals into a formatted prompt fragment."""
        bull_signals = [s for s in signals if s.vote.direction == "buy"]
        if not bull_signals:
            return "Nessun segnale rialzista disponibile."
        lines: list[str] = []
        for s in bull_signals:
            lines.append(f"- [{s.source}] {s.vote.reasoning} (confidence: {s.vote.confidence:.2f})")
        return "\n".join(lines)

    @staticmethod
    def _extract_bear_signals(signals: list[AnalystSignal]) -> str:
        """Filter sell / negative signals into a formatted prompt fragment."""
        bear_signals = [s for s in signals if s.vote.direction in ("sell",)]
        if not bear_signals:
            return "Nessun segnale ribassista disponibile."
        lines: list[str] = []
        for s in bear_signals:
            lines.append(f"- [{s.source}] {s.vote.reasoning} (confidence: {s.vote.confidence:.2f})")
        return "\n".join(lines)

    @staticmethod
    def _extract_blind_spots(signals: list[AnalystSignal]) -> str:
        """Collect blind spots from all analyst signals."""
        if not signals:
            return "Nessun blind spot segnalato."
        lines: list[str] = []
        for s in signals:
            if s.blind_spot:
                lines.append(f"- [{s.source}] {s.blind_spot}")
        return "\n".join(lines) if lines else "Nessun blind spot segnalato."

    @staticmethod
    def _compute_divergence(signals: list[AnalystSignal]) -> float:
        """Compute disagreement level 0.0-1.0.

        0.0 = all signals share the same direction.
        1.0 = signals are evenly split across all three directions.
        """
        if not signals:
            return 0.0
        counts = Counter(s.vote.direction for s in signals)
        max_count = max(counts.values())
        return 1.0 - (max_count / len(signals))

    @staticmethod
    def _build_consensus(
        round_1: dict[str, Any],
        round_2: dict[str, Any] | None,  # noqa: ARG004
    ) -> AgentVote | None:
        """Build a unified AgentVote if consensus confidence > 0.5.

        If Bull and Bear agree on direction, their average confidence is used.
        Returns ``None`` when confidence is too low.
        """
        bull_dir = round_1.get("bull_direction", "hold")
        bear_dir = round_1.get("bear_direction", "hold")
        bull_conf = round_1.get("bull_confidence", 0.0)
        bear_conf = round_1.get("bear_confidence", 0.0)

        if bull_dir == bear_dir:
            avg_conf = (bull_conf + bear_conf) / 2.0
            if avg_conf > 0.5:
                return AgentVote(
                    direction=bull_dir,
                    confidence=avg_conf,
                    reasoning=(
                        f"Consensus: Bull ({bull_conf:.2f}) and Bear ({bear_conf:.2f}) "
                        f"agree on '{bull_dir}' after debate."
                    ),
                    risk_score=1.0 - avg_conf,
                )

        return None
