"""Signal event models."""

from pydantic import Field

from core.domain.events import Event


class SignalGeneratedEvent(Event):
    instrument_id: str
    strategy_id: str = ""
    direction: str = "neutral"
    confidence: float = 0.0
    timeframe: str = "1d"
    reason: str = ""
    agents_involved: list[str] = Field(default_factory=list)


class SignalFilteredEvent(Event):
    instrument_id: str
    signal_id: str = ""
    filter: str = ""
    reason: str = ""
    action: str = "blocked"
