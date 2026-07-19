"""Temporal-integrity tests for external intelligence observations."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from core.domain.intelligence import EvidenceReference, OpportunityDirection, OpportunityObservation


def _evidence() -> EvidenceReference:
    observed = datetime(2026, 7, 18, 12, tzinfo=UTC)
    return EvidenceReference(
        source="official-feed",
        source_url="https://example.invalid/event",
        observed_at=observed,
        available_at=observed + timedelta(seconds=1),
        content_hash="abc123",
        credibility=0.9,
    )


def test_directional_observation_requires_auditable_evidence() -> None:
    event_time = datetime(2026, 7, 18, 12, tzinfo=UTC)
    with pytest.raises(ValidationError, match="require evidence"):
        OpportunityObservation(
            observation_id="obs-1",
            agent_id="eliza-onchain-scout",
            event_time=event_time,
            available_at=event_time,
            instruments=["BTC"],
            observation_type="exchange_inflow",
            direction=OpportunityDirection.BEARISH,
            confidence=0.8,
            novelty=0.7,
            time_horizon="4h",
            summary="large exchange inflow",
        )


def test_observation_preserves_point_in_time_availability() -> None:
    evidence = _evidence()
    observation = OpportunityObservation(
        observation_id="obs-1",
        agent_id="eliza-onchain-scout",
        event_time=evidence.observed_at,
        available_at=evidence.available_at,
        instruments=["BTC", "MSTR"],
        observation_type="exchange_inflow",
        direction=OpportunityDirection.BEARISH,
        confidence=0.8,
        novelty=0.7,
        time_horizon="4h",
        summary="large exchange inflow",
        evidence=[evidence],
    )

    assert observation.evidence[0].content_hash == "abc123"


def test_evidence_cannot_be_available_before_it_was_observed() -> None:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)
    with pytest.raises(ValidationError, match="cannot precede"):
        EvidenceReference(
            source="invalid",
            observed_at=now,
            available_at=now - timedelta(seconds=1),
            content_hash="invalid",
            credibility=0.5,
        )
