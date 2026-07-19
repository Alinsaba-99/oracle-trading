"""Events exchanged with external intelligence runtimes such as ElizaOS."""

from pydantic import Field

from core.domain.events import Event
from core.domain.intelligence import OpportunityObservation

INTELLIGENCE_OBSERVATION_SUBJECT = "oracle.intelligence.observation.v1"
INTELLIGENCE_OUTCOME_SUBJECT = "oracle.intelligence.outcome.v1"


class IntelligenceObservationEvent(Event):
    """An external observation ready for validation by Oracle."""

    observation: OpportunityObservation


class IntelligenceOutcomeEvent(Event):
    """Outcome feedback used to evaluate an observation without granting execution access."""

    observation_id: str
    decision_id: str | None = None
    accepted: bool
    realized_return: float | None = None
    thesis_correct: bool | None = None
    execution_quality: float | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
