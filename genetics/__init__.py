"""Genetic algorithm optimisation framework."""

from genetics.engine import GAConfig, GAResult, GeneticEngine
from genetics.islands import (
    HallOfFameWrapper,
    Island,
    IslandManager,
    MigrationPolicy,
    PopulationStats,
    compute_diversity,
    compute_stats,
    ring_migration,
)
from genetics.serialize import (
    config_to_dict,
    dict_to_genome,
    genome_to_dict,
    pop_snapshot,
    population_from_dict,
    population_to_dict,
    result_to_dict,
)

__all__ = [
    "GAConfig",
    "GAResult",
    "GeneticEngine",
    "HallOfFameWrapper",
    "Island",
    "IslandManager",
    "MigrationPolicy",
    "PopulationStats",
    "compute_diversity",
    "compute_stats",
    "config_to_dict",
    "dict_to_genome",
    "genome_to_dict",
    "pop_snapshot",
    "population_from_dict",
    "population_to_dict",
    "result_to_dict",
    "ring_migration",
]
