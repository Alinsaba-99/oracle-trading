"""Debate module — multi-agent structured debate with scoring."""

from __future__ import annotations

from agents.debate.scorer import DebateScorer
from agents.debate.team import DebateTeam
from agents.protocol import DebateResult

__all__ = ["DebateResult", "DebateScorer", "DebateTeam"]
