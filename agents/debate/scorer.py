"""Debate quality scorer — evaluates argument coverage, evidence use,
contradiction detection, and consensus distance."""

from __future__ import annotations

from typing import Any

from agents.protocol import AgentVote, AnalystSignal

__all__ = ["DebateScorer"]


class DebateScorer:
    """Evaluates the quality of a multi-agent debate.

    Four dimensions, each scored 0.0-1.0, averaged to produce the final
    debate quality score:

    * Argument coverage: how many aspects of the market were discussed.
    * Evidence use: how many distinct indicators were cited.
    * Contradiction detection: how many weaknesses / incongruences found.
    * Consensus distance: how far apart the final votes were (lower is better
      when no consensus, higher when consensus reached).
    """

    def score(
        self,
        signals: list[AnalystSignal],
        round_1: dict[str, Any],
        round_2: dict[str, Any] | None = None,
        consensus: AgentVote | None = None,
    ) -> float:
        """Compute overall debate quality score.

        Parameters
        ----------
        signals:
            The original analyst signals that seeded the debate.
        round_1:
            The output of the first debate round.
        round_2:
            Optional second rebuttal round output.
        consensus:
            The final consensus vote, if one was reached.

        Returns
        -------
        float in [0.0, 1.0].
        """
        components: list[float] = [
            self._argument_coverage(round_1),
            self._evidence_use(round_1, round_2),
            self._contradiction_detection(round_1),
            self._consensus_distance(signals, consensus),
        ]
        return sum(components) / len(components)

    @staticmethod
    def _argument_coverage(round_1: dict[str, Any]) -> float:
        """Score (0-1) based on how many aspects the debate covered."""
        covered = 0
        if round_1.get("bull_thesis"):
            covered += 1
        if round_1.get("bear_critique"):
            covered += 1
        if round_1.get("da_blind_spots"):
            covered += 1
        if round_1.get("da_synthesis"):
            covered += 1
        return min(covered / 4.0, 1.0)

    @staticmethod
    def _evidence_use(round_1: dict[str, Any], round_2: dict[str, Any] | None) -> float:
        """Score (0-1) based on number of distinct indicators cited."""
        indicators: set[str] = set()

        bull_inds = round_1.get("bull_indicators", [])
        if isinstance(bull_inds, list):
            indicators.update(str(i) for i in bull_inds)

        bear_inds = round_1.get("bear_indicators", [])
        if isinstance(bear_inds, list):
            indicators.update(str(i) for i in bear_inds)

        if round_2:
            rebuttal_inds = round_2.get("rebuttal_indicators", [])
            if isinstance(rebuttal_inds, list):
                indicators.update(str(i) for i in rebuttal_inds)

        return min(len(indicators) / 6.0, 1.0)

    @staticmethod
    def _contradiction_detection(round_1: dict[str, Any]) -> float:
        """Score (0-1) based on contradictions identified."""
        weaknesses = round_1.get("bear_weaknesses", [])
        if isinstance(weaknesses, list) and weaknesses:
            return min(len(weaknesses) / 3.0, 1.0)
        return 0.0

    @staticmethod
    def _consensus_distance(signals: list[AnalystSignal], consensus: AgentVote | None) -> float:
        """Score (0-1): closer votes / reached consensus = higher score."""
        if not signals:
            return 0.0
        directions = {s.vote.direction for s in signals}
        unique_count = len(directions)

        if consensus is not None:
            # Consensus reached — reward
            return 0.7 if unique_count > 1 else 1.0

        # No consensus — penalise proportional to disagreement spread
        return 1.0 - (unique_count / 3.0)
