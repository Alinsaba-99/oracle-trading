"""Bridge between GeneticEngine (Phase 3) and Multi-Agent System (Phase 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import polars as pl

    from agents.genetic.adapter import StrategySuggestion
    from genetics.engine import GAConfig
    from genetics.genome.signal import GenomeConfig


class GeneticStrategist:
    """Bridge between GeneticEngine and analyst agents.

    Uses GA to evolve strategies and presents the Pareto front
    to analyst agents for consideration.
    """

    def __init__(
        self,
        genome_config: GenomeConfig,
        ga_config: GAConfig | None = None,
        backtest_config: Any | None = None,
    ) -> None:
        self._genome_config = genome_config
        self._ga_config = ga_config
        self._backtest_config = backtest_config
        self._last_result: Any = None

    async def suggest(
        self,
        _market_data: pl.DataFrame,
        _market_state: Any,  # MarketState
        _n_suggestions: int = 5,
    ) -> list[StrategySuggestion]:
        """Run GA (or load cached) and return regime-filtered suggestions.

        Currently returns an empty list by design.  Strategy suggestions
        are produced by the GA engine and consumed through
        :meth:`get_last_pareto` after a full run — this agent method is a
        pass-through stub awaiting Phase 4 integration with HPC dispatch.
        """
        return []

    def get_last_pareto(self) -> list[StrategySuggestion]:
        """Return last computed Pareto front."""
        return []
