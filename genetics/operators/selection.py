"""Selection operators for the GA engine.

Provides tournament selection, NSGA-II crowded tournament selection,
and NSGA-II environmental selection, all wrapping DEAP's built-in
tools for compatibility with the broader oracle framework.
"""

from __future__ import annotations

from deap import tools

__all__ = ["environmental_selection", "nsga2_selection", "tournament_selection"]


def tournament_selection(
    population: list[list[float]], k: int, tournsize: int = 3
) -> list[list[float]]:
    """Select *k* individuals using tournament selection.

    Runs a classic tournament of size *tournsize* on random subsets of the
    population and picks the winner (best fitness) from each.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.
        k: Number of individuals to select.
        tournsize: Number of candidates per tournament.

    Returns:
        Selected individuals (length *k*).
    """
    return tools.selTournament(population, k, tournsize=tournsize)  # type: ignore[no-any-return]


def nsga2_selection(population: list[list[float]], k: int) -> list[list[float]]:
    """Select *k* individuals using NSGA-II crowded-comparison tournament.

    Individuals MUST have ``fitness.crowding_dist`` already set (e.g. via
    :func:`deap.tools.emo.assignCrowdingDist`); otherwise :func:`selTournamentDCD`
    will raise :class:`AttributeError`.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.
        k: Number of individuals to select.

    Returns:
        Selected individuals (length *k*).
    """
    return tools.selTournamentDCD(population, k)  # type: ignore[no-any-return]


def environmental_selection(population: list[list[float]], k: int) -> list[list[float]]:
    """Apply NSGA-II environmental selection (non-dominated sorting + crowding distance).

    Retains *k* individuals from *population* using Pareto-rank and crowding
    distance, the standard survival operator of NSGA-II.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.
        k: Number of individuals to retain.

    Returns:
        Selected individuals (length *k*).
    """
    return tools.selNSGA2(population, k)  # type: ignore[no-any-return]
