"""Adapter: Phase 3 GAResult/Pareto-front to agent-consumable StrategySuggestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genetics.genome.parameters import GenomeParameter


@dataclass
class StrategySuggestion:
    """A decoded strategy from the GA Pareto front, readable by agents.

    Attributes:
        rank: Ranking position in the Pareto front (1-based).
        genome_params: Decoded parameter name-to-value mapping.
        fitness: 4-tuple (Sharpe, Sortino, Calmar, MaxDD).
        description: Human-readable summary of the strategy.
    """

    rank: int
    genome_params: dict[str, float | int | str]
    fitness: tuple[float, float, float, float]
    description: str = ""


class GAAdapter:
    """Converts Phase 3 GA output to agent-consumable format."""

    @staticmethod
    def pareto_to_suggestions(
        pareto_front: list[Any], param_defs: Sequence[GenomeParameter], max_suggestions: int = 5
    ) -> list[StrategySuggestion]:
        """Convert Pareto front DEAP individuals to ranked StrategySuggestions.

        Args:
            pareto_front: List of DEAP individuals from a multi-objective GA run.
            param_defs: Ordered parameter definitions used by the genome.
            max_suggestions: Maximum number of suggestions to return.

        Returns:
            Ranked list of StrategySuggestion objects.
        """
        import numpy as np

        from genetics.genome.signal import Genome, decode

        suggestions: list[StrategySuggestion] = []
        for rank, ind in enumerate(pareto_front[:max_suggestions]):
            # Extract fitness values (Sharpe, Sortino, Calmar, MaxDD)
            if hasattr(ind, "fitness") and ind.fitness.valid:
                fitness = tuple(ind.fitness.values)
            else:
                fitness = (0.0, 0.0, 0.0, 0.0)

            # Build a Genome from the DEAP individual's normalized vector
            genome = Genome(
                normalized_params=np.array(ind, dtype=np.float64), param_defs=param_defs
            )
            decoded = decode(genome)

            suggestions.append(
                StrategySuggestion(
                    rank=rank + 1,
                    genome_params=decoded,
                    fitness=fitness,
                    description=f"Pareto #{rank + 1}: Sharpe={fitness[0]:.3f}",
                )
            )
        return suggestions

    @staticmethod
    def filter_by_regime(
        suggestions: list[StrategySuggestion], _regime: str
    ) -> list[StrategySuggestion]:
        """Filter strategies appropriate for the current market regime.

        Pass-through in v1 — returns *suggestions* unchanged.  Regime-aware
        filtering will be added when strategies are tagged with per-regime
        performance metadata.
        """
        return suggestions
