"""Base analyst abstraction for all analyst agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.config import MASConfig
    from agents.llm import LLMClient
    from agents.protocol import AnalystInput, AnalystSignal


class BaseAnalyst(ABC):
    """Abstract base for all analyst types in the MAS system."""

    def __init__(self, llm_client: LLMClient, config: MASConfig) -> None:
        self._llm = llm_client
        self._config = config

    @abstractmethod
    async def analyze(self, data: AnalystInput) -> AnalystSignal: ...

    @property
    @abstractmethod
    def blind_spot(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
