"""GA genetic operators — selection, crossover, mutation, and DEAP toolbox factory.

Provides wrappers around DEAP's built-in operators that are compatible with
the oracle framework's normalised-genome representation, plus a factory
(:func:`create_toolbox`) that wires a complete DEAP :class:`~deap.base.Toolbox`.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from deap import base, creator, tools

from genetics.operators.crossover import crossover_with_validation, sbx_crossover
from genetics.operators.mutation import (
    categorical_mutation,
    mutation_with_validation,
    polynomial_mutation,
)
from genetics.operators.selection import (
    environmental_selection,
    nsga2_selection,
    tournament_selection,
)

if TYPE_CHECKING:
    from genetics.genome.signal import GenomeConfig

__all__ = [
    "categorical_mutation",
    "create_toolbox",
    "crossover_with_validation",
    "environmental_selection",
    "mutation_with_validation",
    "nsga2_selection",
    "polynomial_mutation",
    "sbx_crossover",
    "tournament_selection",
]


def create_toolbox(genome_config: GenomeConfig, *, use_validation: bool = False) -> base.Toolbox:
    r"""Build a pre-configured DEAP :class:`~deap.base.Toolbox` for the GA engine.

    Registered aliases:

    * ``individual`` — random normalised genome in *[0, 1]*\ :sup:`n`
    * ``population`` — list of individuals
    * ``mate`` — :func:`sbx_crossover` (or :func:`crossover_with_validation`)
    * ``mutate`` — :func:`polynomial_mutation` (or :func:`mutation_with_validation`)
    * ``select`` — :func:`tournament_selection`
    * ``select_dcd`` — :func:`nsga2_selection`
    * ``select_nsga2`` — :func:`environmental_selection`

    Args:
        genome_config: Genome definition (determines parameter count and defs).
        use_validation: If ``True``, register validated crossover/mutation
            variants that retry on invalid offspring.

    Returns:
        A fully configured DEAP :class:`~deap.base.Toolbox`.
    """
    if not hasattr(creator, "FitnessMulti"):
        creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMulti)

    toolbox = base.Toolbox()
    n = genome_config.n_params

    # -- Individual / population generators (spawn-safe) -------------------
    toolbox.register("attr_float", random.random)
    toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_float, n)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # -- Variation operators ------------------------------------------------
    if use_validation:
        toolbox.register("mate", crossover_with_validation, genome_config=genome_config, eta=15.0)
        toolbox.register(
            "mutate", mutation_with_validation, genome_config=genome_config, eta=20.0, indpb=0.15
        )
    else:
        toolbox.register("mate", sbx_crossover, eta=15.0, low=0.0, up=1.0)
        toolbox.register("mutate", polynomial_mutation, eta=20.0, indpb=0.15, low=0.0, up=1.0)

    # -- Selection operators ------------------------------------------------
    toolbox.register("select", tournament_selection, tournsize=3)
    toolbox.register("select_dcd", nsga2_selection)
    toolbox.register("select_nsga2", environmental_selection)

    return toolbox
