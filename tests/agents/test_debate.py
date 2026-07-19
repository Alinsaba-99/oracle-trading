"""Tests for DebateTeam — debate orchestration, divergence, consensus, and prompts."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, PropertyMock

import pytest
from pydantic import BaseModel

from agents.debate.prompts import BEAR_SYSTEM, BULL_SYSTEM, DEVIL_SYSTEM
from agents.debate.scorer import DebateScorer
from agents.debate.team import DebateTeam, _BearResponse, _BullResponse, _DAResponse
from agents.protocol import AgentVote, AnalystSignal, DebateResult

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def all_bull_signals() -> list[AnalystSignal]:
    """Signals where every agent votes 'buy' — divergence = 0.0."""
    return [
        AnalystSignal(
            source="macro",
            vote=AgentVote(
                direction="buy", confidence=0.7, reasoning="GDP growth above trend.", risk_score=0.2
            ),
            blind_spot="CPI data is lagging.",
            metadata={"gdp": 2.4},
        ),
        AnalystSignal(
            source="technical",
            vote=AgentVote(
                direction="buy",
                confidence=0.6,
                reasoning="Trend following signal triggered.",
                risk_score=0.3,
            ),
            blind_spot="Volume anomaly on breakout.",
            metadata={"rsi": 65},
        ),
    ]


@pytest.fixture
def mixed_signals() -> list[AnalystSignal]:
    """Signals with buy + sell mix — divergence > 0.3."""
    return [
        AnalystSignal(
            source="macro",
            vote=AgentVote(
                direction="buy", confidence=0.7, reasoning="GDP growth above trend.", risk_score=0.2
            ),
            blind_spot="CPI data is lagging.",
            metadata={"gdp": 2.4},
        ),
        AnalystSignal(
            source="technical",
            vote=AgentVote(
                direction="sell",
                confidence=0.6,
                reasoning="RSI overbought on daily chart.",
                risk_score=0.4,
            ),
            blind_spot="Strong trend can stay overbought.",
            metadata={"rsi": 78},
        ),
        AnalystSignal(
            source="sentiment",
            vote=AgentVote(
                direction="sell",
                confidence=0.5,
                reasoning="Fear & Greed index in extreme fear.",
                risk_score=0.5,
            ),
            blind_spot="Crowded trades may reverse.",
            metadata={"fear_greed": 18},
        ),
    ]


@pytest.fixture
def round_1_responses() -> list[BaseModel]:
    """Mock LLM responses for a full round 1 debate."""
    return [
        _BullResponse(
            thesis="Economic expansion supports higher equity prices.",
            key_indicators=["GDP growth", "PMI > 50", "Low unemployment"],
            confidence=0.80,
            direction="buy",
        ),
        _BearResponse(
            counter_thesis="Valuation multiples are stretched and earnings growth is decelerating.",
            weaknesses_found=[
                "High P/E ratios not justified by earnings",
                "Low volume on recent rally suggests weakness",
                "Central bank pivot risk",
            ],
            counter_indicators=["P/E ratio", "Volume profile", "Central bank stance"],
            confidence=0.65,
            direction="sell",
        ),
        _DAResponse(
            blind_spots=[
                "Both sides ignore geopolitical tail risk",
                "No analysis of currency impact",
                "Regulatory changes not considered",
            ],
            third_way=None,
            synthesis="Data is mixed; best to wait for next week's CPI print before committing.",
        ),
    ]


@pytest.fixture
def rebuttal_responses() -> list[BaseModel]:
    """Mock LLM responses for round 2 rebuttals."""
    return [
        _BullResponse(
            thesis="High P/E is justified by low interest rates; earnings will catch up.",
            key_indicators=["Real yield", "Forward P/E"],
            confidence=0.75,
            direction="buy",
        ),
        _BearResponse(
            counter_thesis="Low rates already priced in; any hawkish surprise triggers correction.",
            weaknesses_found=[
                "Earnings expectations still too optimistic",
                "Rate cut priced but may not materialise",
            ],
            counter_indicators=["Earnings revisions", "Rate path"],
            confidence=0.70,
            direction="sell",
        ),
    ]


@pytest.fixture
def llm_client_round1_only(round_1_responses: list[BaseModel]) -> AsyncMock:
    """Mock LLM client that returns round 1 responses (no round 2)."""
    client = AsyncMock()
    client.structured_call = AsyncMock(side_effect=round_1_responses)
    type(client).model_name = PropertyMock(return_value="mock-debate/v1")
    return client


@pytest.fixture
def llm_client_with_rebuttal(
    round_1_responses: list[BaseModel], rebuttal_responses: list[BaseModel]
) -> AsyncMock:
    """Mock LLM client that returns both round 1 and rebuttal responses."""
    client = AsyncMock()
    client.structured_call = AsyncMock(side_effect=[*round_1_responses, *rebuttal_responses])
    type(client).model_name = PropertyMock(return_value="mock-debate/v1")
    return client


@pytest.fixture
def team_round1_only(llm_client_round1_only: AsyncMock) -> DebateTeam:
    return DebateTeam(llm_client=llm_client_round1_only)


@pytest.fixture
def team_with_rebuttal(llm_client_with_rebuttal: AsyncMock) -> DebateTeam:
    return DebateTeam(llm_client=llm_client_with_rebuttal)


# ── Round 1 — basic structure ────────────────────────────────────────────────


class TestDebateRound1:
    """Verify round 1 is always populated correctly."""

    @pytest.mark.asyncio
    async def test_round_1_contains_all_roles(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_round1_only.debate(mixed_signals)
        assert isinstance(result, DebateResult)
        assert "bull_thesis" in result.round_1
        assert "bear_critique" in result.round_1
        assert "da_blind_spots" in result.round_1

    @pytest.mark.asyncio
    async def test_round_1_bull_fields(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_round1_only.debate(mixed_signals)
        assert result.round_1["bull_thesis"] == "Economic expansion supports higher equity prices."
        assert result.round_1["bull_direction"] == "buy"
        assert result.round_1["bull_confidence"] == 0.80

    @pytest.mark.asyncio
    async def test_round_1_bear_fields(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_round1_only.debate(mixed_signals)
        assert "stretched" in result.round_1["bear_critique"]
        assert len(result.round_1["bear_weaknesses"]) == 3
        assert result.round_1["bear_direction"] == "sell"

    @pytest.mark.asyncio
    async def test_round_1_da_fields(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_round1_only.debate(mixed_signals)
        assert len(result.round_1["da_blind_spots"]) == 3
        assert "CPI" in result.round_1["da_synthesis"]

    @pytest.mark.asyncio
    async def test_debate_result_type(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_round1_only.debate(mixed_signals)
        assert isinstance(result, DebateResult)
        assert isinstance(result.round_1, dict)
        assert result.round_2 is None
        assert isinstance(result.disagreements, list)


# ── Round 2 — conditional rebuttal ───────────────────────────────────────────


class TestDebateRound2:
    """Round 2 triggers only when divergence exceeds threshold."""

    @pytest.mark.asyncio
    async def test_round_2_triggers_when_divergence_high(
        self, team_with_rebuttal: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        """Mixed buy/sell signals produce divergence > 0.3, triggering round 2."""
        result = await team_with_rebuttal.debate(mixed_signals, divergence_threshold=0.3)
        assert result.round_2 is not None
        assert "bull_rebuttal" in result.round_2
        assert "bear_counter" in result.round_2

    @pytest.mark.asyncio
    async def test_round_2_skipped_when_divergence_low(
        self, team_round1_only: DebateTeam, all_bull_signals: list[AnalystSignal]
    ) -> None:
        """All-buy signals produce divergence 0.0, skipping round 2."""
        result = await team_round1_only.debate(all_bull_signals, divergence_threshold=0.3)
        assert result.round_2 is None

    @pytest.mark.asyncio
    async def test_round_2_not_triggered_with_low_threshold(
        self, team_round1_only: DebateTeam, all_bull_signals: list[AnalystSignal]
    ) -> None:
        """Even with threshold 0.0, zero divergence skips round 2."""
        result = await team_round1_only.debate(all_bull_signals, divergence_threshold=0.0)
        assert result.round_2 is None

    @pytest.mark.asyncio
    async def test_round_2_rebuttal_has_bull_and_bear(
        self, team_with_rebuttal: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        result = await team_with_rebuttal.debate(mixed_signals)
        assert result.round_2 is not None
        assert "bull_rebuttal" in result.round_2
        assert "bear_counter" in result.round_2
        assert result.round_2["bull_rebuttal_confidence"] == 0.75


# ── Consensus building ───────────────────────────────────────────────────────


class TestConsensus:
    """Consensus is built only when Bull and Bear agree with high confidence."""

    @pytest.mark.asyncio
    async def test_consensus_built_when_bull_and_bear_agree(
        self, llm_client_round1_only: AsyncMock, all_bull_signals: list[AnalystSignal]
    ) -> None:
        """Both agree on 'buy' with high confidence → consensus built."""
        llm_client_round1_only.structured_call = AsyncMock(
            side_effect=[
                _BullResponse(
                    thesis="Strong economy.",
                    key_indicators=["GDP"],
                    confidence=0.9,
                    direction="buy",
                ),
                _BearResponse(
                    counter_thesis="Risks exist but manageable.",
                    weaknesses_found=["Inflation watch"],
                    counter_indicators=["CPI"],
                    confidence=0.7,
                    direction="buy",
                ),
                _DAResponse(
                    blind_spots=["Geopolitical risk"],
                    third_way=None,
                    synthesis="Bull case stronger.",
                ),
            ]
        )
        team = DebateTeam(llm_client=llm_client_round1_only)
        result = await team.debate(all_bull_signals)
        assert result.consensus is not None
        assert result.consensus.direction == "buy"
        # avg confidence = (0.9 + 0.7) / 2 = 0.8 > 0.5
        assert result.consensus.confidence == pytest.approx(0.80)
        assert result.consensus.risk_score is not None

    @pytest.mark.asyncio
    async def test_no_consensus_when_directions_differ(
        self, team_round1_only: DebateTeam, mixed_signals: list[AnalystSignal]
    ) -> None:
        """Bull says buy, Bear says sell → no consensus."""
        result = await team_round1_only.debate(mixed_signals)
        assert result.consensus is None

    @pytest.mark.asyncio
    async def test_no_consensus_when_confidence_low(
        self, llm_client_round1_only: AsyncMock, all_bull_signals: list[AnalystSignal]
    ) -> None:
        """Same direction but low confidence → no consensus."""
        llm_client_round1_only.structured_call = AsyncMock(
            side_effect=[
                _BullResponse(
                    thesis="Weak signal.", key_indicators=["GDP"], confidence=0.3, direction="buy"
                ),
                _BearResponse(
                    counter_thesis="Also weak signal.",
                    weaknesses_found=["Uncertainty"],
                    counter_indicators=["Vix"],
                    confidence=0.2,
                    direction="buy",
                ),
                _DAResponse(
                    blind_spots=["Everything unclear"], third_way="Wait", synthesis="Too uncertain."
                ),
            ]
        )
        team = DebateTeam(llm_client=llm_client_round1_only)
        result = await team.debate(all_bull_signals)
        # avg confidence = (0.3 + 0.2) / 2 = 0.25 <= 0.5
        assert result.consensus is None


# ── Prompt verification ──────────────────────────────────────────────────────


class TestPrompts:
    """Each debate role receives the correct system prompt."""

    @pytest.mark.asyncio
    async def test_bull_prompt_used(
        self,
        llm_client_round1_only: AsyncMock,
        team_round1_only: DebateTeam,
        mixed_signals: list[AnalystSignal],
    ) -> None:
        await team_round1_only.debate(mixed_signals)
        call_0 = llm_client_round1_only.structured_call.call_args_list[0]
        system = call_0.kwargs.get("system_prompt", call_0.args[0] if call_0.args else "")
        assert "BULL" in system.upper()
        assert system == BULL_SYSTEM

    @pytest.mark.asyncio
    async def test_bear_prompt_used(
        self,
        llm_client_round1_only: AsyncMock,
        team_round1_only: DebateTeam,
        mixed_signals: list[AnalystSignal],
    ) -> None:
        await team_round1_only.debate(mixed_signals)
        call_1 = llm_client_round1_only.structured_call.call_args_list[1]
        system = call_1.kwargs.get("system_prompt", call_1.args[0] if call_1.args else "")
        assert "BEAR" in system.upper()
        assert system == BEAR_SYSTEM

    @pytest.mark.asyncio
    async def test_devil_advocate_prompt_used(
        self,
        llm_client_round1_only: AsyncMock,
        team_round1_only: DebateTeam,
        mixed_signals: list[AnalystSignal],
    ) -> None:
        await team_round1_only.debate(mixed_signals)
        call_2 = llm_client_round1_only.structured_call.call_args_list[2]
        system = call_2.kwargs.get("system_prompt", call_2.args[0] if call_2.args else "")
        assert "DEVIL" in system.upper() or "ADVOCATE" in system.upper()
        assert system == DEVIL_SYSTEM

    @pytest.mark.asyncio
    async def test_rebuttal_prompt_used_in_round_two(
        self,
        llm_client_with_rebuttal: AsyncMock,
        team_with_rebuttal: DebateTeam,
        mixed_signals: list[AnalystSignal],
    ) -> None:
        await team_with_rebuttal.debate(mixed_signals)
        # Call indices 3 and 4 are round 2 rebuttals
        call_3 = llm_client_with_rebuttal.structured_call.call_args_list[3]
        system_3 = call_3.kwargs.get("system_prompt", call_3.args[0] if call_3.args else "")
        assert "Round 2" in system_3


# ── Signal extraction ────────────────────────────────────────────────────────


class TestSignalExtraction:
    """_extract_bull_signals and _extract_bear_signals filter correctly."""

    def test_extract_bull_signals_only_buy(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.8, reasoning="Good"),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="technical",
                vote=AgentVote(direction="sell", confidence=0.6, reasoning="Bad"),
                blind_spot="",
                metadata={},
            ),
        ]
        result = DebateTeam._extract_bull_signals(signals)
        assert "macro" in result
        assert "technical" not in result
        assert "Good" in result

    def test_extract_bull_signals_empty(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="sell", confidence=0.8, reasoning=""),
                blind_spot="",
                metadata={},
            )
        ]
        result = DebateTeam._extract_bull_signals(signals)
        assert "Nessun segnale rialzista" in result

    def test_extract_bear_signals_only_sell(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.8, reasoning="Good"),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="technical",
                vote=AgentVote(direction="sell", confidence=0.6, reasoning="Bad"),
                blind_spot="",
                metadata={},
            ),
        ]
        result = DebateTeam._extract_bear_signals(signals)
        assert "technical" in result
        assert "macro" not in result
        assert "Bad" in result

    def test_extract_bear_signals_empty(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.8, reasoning=""),
                blind_spot="",
                metadata={},
            )
        ]
        result = DebateTeam._extract_bear_signals(signals)
        assert "Nessun segnale ribassista" in result


# ── Divergence computation ────────────────────────────────────────────────────


class TestDivergence:
    """Divergence is computed correctly for various signal mixes."""

    def test_all_same_direction_zero_divergence(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="technical",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="sentiment",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
        ]
        assert DebateTeam._compute_divergence(signals) == 0.0

    def test_two_against_one(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="technical",
                vote=AgentVote(direction="sell", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="sentiment",
                vote=AgentVote(direction="sell", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
        ]
        # max_count = 2, n = 3 → divergence = 1 - 2/3 ≈ 0.333
        assert DebateTeam._compute_divergence(signals) == pytest.approx(1.0 - 2.0 / 3.0)

    def test_even_split(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="technical",
                vote=AgentVote(direction="sell", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
            AnalystSignal(
                source="sentiment",
                vote=AgentVote(direction="hold", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            ),
        ]
        # max_count = 1, n = 3 → divergence = 1 - 1/3 = 0.667
        assert DebateTeam._compute_divergence(signals) == pytest.approx(2.0 / 3.0)

    def test_empty_signals_zero_divergence(self) -> None:
        assert DebateTeam._compute_divergence([]) == 0.0


# ── DebateScorer ─────────────────────────────────────────────────────────────


class TestDebateScorer:
    """DebateScorer produces correct quality scores."""

    def test_score_components_averaged(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            )
        ]
        round_1 = {
            "bull_thesis": "Markets up",
            "bear_critique": "Markets down",
            "da_blind_spots": ["Risk A"],
            "da_synthesis": "Mixed",
            "bull_indicators": ["GDP"],
            "bear_indicators": ["CPI"],
            "bear_weaknesses": ["W1"],
        }
        consensus = AgentVote(
            direction="hold", confidence=0.6, reasoning="Uncertain", risk_score=0.4
        )
        scorer = DebateScorer()
        score = scorer.score(signals=signals, round_1=round_1, consensus=consensus)
        # Each component is in [0,1], average should be in [0,1]
        assert 0.0 <= score <= 1.0

    def test_score_empty_signals(self) -> None:
        """No signals → score still uses argument coverage."""
        round_1: dict[str, Any] = {}
        scorer = DebateScorer()
        score = scorer.score(signals=[], round_1=round_1)
        # Argument coverage = 0, evidence = 0, contradiction = 0, consensus_distance = 0
        # Average = 0
        assert score == 0.0

    def test_score_perfect_debate(self) -> None:
        signals = [
            AnalystSignal(
                source="macro",
                vote=AgentVote(direction="buy", confidence=0.5, reasoning=""),
                blind_spot="",
                metadata={},
            )
        ]
        round_1 = {
            "bull_thesis": "x",
            "bear_critique": "y",
            "da_blind_spots": ["z"],
            "da_synthesis": "w",
            "bull_indicators": ["A", "B", "C", "D", "E", "F"],
            "bear_indicators": ["G"],
            "bear_weaknesses": ["W1", "W2", "W3"],
        }
        consensus = AgentVote(direction="buy", confidence=0.9, reasoning="Strong", risk_score=0.1)
        scorer = DebateScorer()
        score = scorer.score(signals=signals, round_1=round_1, consensus=consensus)
        # 1 signal, unique direction = 1, consensus reached → consensus_distance = 1.0
        # Full coverage
        assert score > 0.0
