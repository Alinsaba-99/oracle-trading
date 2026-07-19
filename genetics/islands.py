"""Island-model GA engine — parallel sub-populations with migration.

Provides :class:`Island` (single sub-population evolutionary loop),
:class:`IslandManager` (multi-island orchestration), and supporting
types for migration, statistics, and hall-of-fame tracking.
"""

from __future__ import annotations

import copy
import os
import random as _random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from deap import creator

from genetics.genome.signal import Genome, GenomeConfig
from genetics.operators import create_toolbox
from genetics.population import (
    HallOfFameWrapper,
    MigrationPolicy,
    PopulationStats,
    compute_diversity,
    compute_stats,
)
from genetics.serialize import population_from_dict, population_to_dict

if TYPE_CHECKING:
    import polars as pl

    from genetics.fitness.evaluator import FitnessEvaluator

__all__ = [
    "HallOfFameWrapper",
    "Island",
    "IslandManager",
    "MigrationPolicy",
    "PopulationStats",
    "compute_diversity",
    "compute_stats",
    "ring_migration",
]


# ---------------------------------------------------------------------------
# Migration topology helpers
# ---------------------------------------------------------------------------


def ring_migration(
    islands: list[Island], _migration_size: int = 3, _rng: _random.Random | None = None
) -> list[list[int]]:
    """Ring-migration plan: each island sends *migration_size* individuals to the next.

    Args:
        islands: All active islands.
        migration_size: Number of emigrants per island.
        _rng: Unused — retained for API compatibility.

    Returns:
        A list of ``(src_idx, dst_idx)`` pairs defining the transfer edges.
    """
    n = len(islands)
    if n < 2:
        return []
    edges: list[list[int]] = []
    for i in range(n):
        dst = (i + 1) % n
        edges.append([i, dst])
    return edges


# ---------------------------------------------------------------------------
# Island
# ---------------------------------------------------------------------------


@dataclass
class Island:
    """A single sub-population in the island model.

    Each island has its own DEAP toolbox and population, and evolves
    independently except for periodic migrations coordinated by the
    :class:`IslandManager`.

    Each island maintains its own ``random.Random`` instance (``_rng``)
    seeded with ``_seed``.  This ensures that parallel islands produce
    deterministic results independently — unlike the global
    ``random.seed()`` approach which would race when islands run
    concurrently via ``asyncio.to_thread``.

    Attributes:
        id: Island identifier (0-indexed).
        population: DEAP individuals forming this island's gene pool.
        toolbox: DEAP toolbox with registered genetic operators.
        generation: Current generation counter.
        checkpoint_path: Path for persisting this island's state.
    """

    id: int = 0
    population: list[Any] = field(default_factory=list)
    toolbox: Any = None
    generation: int = 0
    checkpoint_path: str = ""

    # Internal: genome config for reconstructing Genome objects
    _genome_config: GenomeConfig | None = field(default=None, repr=False)

    # Internal: seed for deterministic RNG for this island
    _seed: int = field(default=0, repr=False)

    # Internal: island-specific RNG (not the global random module)
    _rng: _random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Create an island-specific RNG for reproducibility."""
        self._rng = _random.Random(self._seed)

    def evaluate_next_gen(
        self,
        evaluator: FitnessEvaluator,
        data: pl.DataFrame,
        cxpb: float = 0.8,
        mutpb: float = 0.2,
        executor: Any = None,
    ) -> PopulationStats:
        """Run one generation of evolution on this island.

        Implements the standard NSGA-II loop:
        selection → crossover → mutation → evaluate → environmental selection.

        Args:
            evaluator: Fitness evaluator that scores individual genomes.
            data: Market data passed to the evaluator.
            cxpb: Crossover probability.
            mutpb: Mutation probability.
            executor: Optional ``concurrent.futures.Executor`` for parallel
                fitness evaluation across individuals (e.g.,``ThreadPoolExecutor``).

        Returns:
            Population statistics for this generation.
        """
        toolbox = self.toolbox
        pop = self.population

        # --- Evaluate any pre-existing invalid individuals (initial population) ---
        pop_invalid = [ind for ind in pop if not ind.fitness.valid]
        if pop_invalid:
            genomes = [self._to_genome(ind) for ind in pop_invalid]
            if executor is not None:
                data_repeated = [data] * len(genomes)
                eval_repeated = [evaluator] * len(genomes)
                fitnesses = list(executor.map(_eval_one, genomes, data_repeated, eval_repeated))
            else:
                fitnesses = [evaluator.evaluate(g, data) for g in genomes]
            for ind, fit in zip(pop_invalid, fitnesses, strict=True):
                ind.fitness.values = fit

        # --- Selection ---
        offspring = toolbox.select(pop, len(pop))
        offspring = [toolbox.clone(ind) for ind in offspring]

        # --- Crossover ---
        for i in range(1, len(offspring), 2):
            if self._rng.random() < cxpb:
                toolbox.mate(offspring[i - 1], offspring[i])
                del offspring[i - 1].fitness.values
                del offspring[i].fitness.values

        # --- Mutation ---
        for i in range(len(offspring)):
            if self._rng.random() < mutpb:
                toolbox.mutate(offspring[i])
                del offspring[i].fitness.values

        # --- Evaluate invalid individuals in offspring ---
        invalid = [ind for ind in offspring if not ind.fitness.valid]

        if invalid:
            genomes = [self._to_genome(ind) for ind in invalid]
            if executor is not None:
                data_repeated = [data] * len(genomes)
                eval_repeated = [evaluator] * len(genomes)
                fitnesses = list(executor.map(_eval_one, genomes, data_repeated, eval_repeated))
            else:
                fitnesses = [evaluator.evaluate(g, data) for g in genomes]

            for ind, fit in zip(invalid, fitnesses, strict=True):
                ind.fitness.values = fit

        # --- Environmental selection (NSGA-II) ---
        self.population = list(toolbox.select_nsga2(pop + offspring, len(pop)))
        self.generation += 1

        return compute_stats(self.population, self.generation)

    def _to_genome(self, ind: list[Any]) -> Genome:
        """Convert a DEAP individual to a :class:`Genome` for evaluation."""
        assert self._genome_config is not None
        return Genome(
            normalized_params=np.array(list(ind), dtype=np.float64),
            param_defs=self._genome_config.param_defs,
        )


def _eval_one(genome: Genome, data: Any, evaluator: FitnessEvaluator) -> tuple[float, ...]:
    """Picklable wrapper for :meth:`FitnessEvaluator.evaluate`."""
    return evaluator.evaluate(genome, data)


# ---------------------------------------------------------------------------
# IslandManager
# ---------------------------------------------------------------------------


class IslandManager:
    """Manages *N* islands with parallel asyncio execution.

    Each island gets its own DEAP toolbox with an independent RNG seed
    derived from a master seed + island index.
    """

    def __init__(
        self,
        genome_config: GenomeConfig,
        n_islands: int = 4,
        pop_size_per_island: int = 25,
        seed: int = 42,
        migration_policy: MigrationPolicy | None = None,
        checkpoint_dir: str = "checkpoints/",
        seed_genomes: list[list[float]] | None = None,
    ) -> None:
        self.genome_config = genome_config
        self.n_islands = n_islands
        self.pop_size_per_island = pop_size_per_island
        self.seed = seed
        self.seed_genomes = seed_genomes
        self.migration_policy = migration_policy or MigrationPolicy()
        self.checkpoint_dir = checkpoint_dir
        self.islands: list[Island] = []
        self._signal_type: str = "genome"

        self._init_populations()

    def _init_populations(self) -> None:
        """Create and seed each island's population."""
        self.islands.clear()
        for i in range(self.n_islands):
            island_seed = self.seed + i * 1000
            toolbox = create_toolbox(self.genome_config)
            _random.seed(island_seed)

            # Create population with seed genomes injected first
            pop: list[Any] = []
            if self.seed_genomes:
                for vec in self.seed_genomes:
                    if len(vec) >= self.genome_config.n_params:
                        ind = creator.Individual(vec[: self.genome_config.n_params])
                        ind.fitness = creator.FitnessMulti()
                        pop.append(ind)
            # Fill remaining with random individuals
            remaining = max(0, self.pop_size_per_island - len(pop))
            for _ in range(remaining):
                ind = toolbox.individual()
                ind.fitness = creator.FitnessMulti()
                pop.append(ind)

            island = Island(
                id=i,
                population=pop,
                toolbox=toolbox,
                generation=0,
                checkpoint_path=os.path.join(self.checkpoint_dir, f"island_{i}.json"),
                _genome_config=self.genome_config,
                _seed=island_seed,
            )
            self.islands.append(island)

    async def run_generation(
        self,
        generation: int,  # noqa: ARG002
        evaluator: FitnessEvaluator,
        data: pl.DataFrame,
        cxpb: float = 0.8,
        mutpb: float = 0.2,
        executor: Any = None,
    ) -> list[PopulationStats]:
        """Run one generation of evolution across all islands in parallel.

        Each island's :meth:`Island.evaluate_next_gen` runs in a thread
        (via ``asyncio.to_thread``).  If *executor* is provided, it is
        forwarded to each island for per-individual parallel fitness
        evaluation.

        Returns:
            Population statistics per island.
        """
        import asyncio

        async def _run_island(island: Island) -> PopulationStats:
            return await asyncio.to_thread(
                island.evaluate_next_gen, evaluator, data, cxpb, mutpb, executor
            )

        tasks = [_run_island(isl) for isl in self.islands]
        results: list[PopulationStats] = await asyncio.gather(*tasks)
        return results

    def migrate(self) -> None:
        """Apply the migration policy between islands.

        Uses ring migration by default: each island sends its best
        individuals to the next island in the ring.
        """
        if self.n_islands < 2:
            return
        policy = self.migration_policy
        if self.generation % policy.interval != 0:
            return

        edges = ring_migration(self.islands, policy.size)
        if not edges:
            return

        for src_idx, dst_idx in edges:
            src = self.islands[src_idx]
            dst = self.islands[dst_idx]

            # Select best individuals from src (tournament selection)
            emigrants = src.toolbox.select(src.population, policy.size)

            if policy.replacement:
                # Sort dst by fitness (worst first) and replace
                sorted_dst = sorted(
                    dst.population,
                    key=lambda ind: ind.fitness.wvalues[0] if ind.fitness.valid else float("-inf"),
                )
                for i, emigrant in enumerate(emigrants):
                    if i < len(sorted_dst):
                        idx = dst.population.index(sorted_dst[i])
                        dst.population[idx] = copy.deepcopy(emigrant)
                        dst.population[idx].fitness.values = emigrant.fitness.values
            else:
                dst.population.extend(copy.deepcopy(em) for em in emigrants)

    @property
    def generation(self) -> int:
        """Current generation (minimum across islands)."""
        if not self.islands:
            return 0
        return min(is_.generation for is_ in self.islands)

    def merge_pareto_fronts(self) -> list[Any]:
        """Combine all islands' Pareto-optimal individuals into the global front.

        Uses NSGA-II non-dominated sorting on the union of all island
        populations, returning only the first (Pareto-optimal) front.

        Returns:
            Global Pareto-optimal individuals.
        """
        from deap import tools as deap_tools

        if not self.islands:
            return []

        # Union of all individuals with valid fitness
        all_individuals = [
            ind for is_ in self.islands for ind in is_.population if ind.fitness.valid
        ]
        if not all_individuals:
            return []

        front = deap_tools.sortNondominated(
            all_individuals, len(all_individuals), first_front_only=True
        )[0]
        return list(front)

    def save_checkpoint(self, path: str) -> None:
        """Save the full island-manager state to a JSON checkpoint file.

        The checkpoint includes schema version, generation count,
        per-island state, and configuration.
        """
        import json

        data = self._checkpoint_dict()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _checkpoint_dict(self) -> dict[str, Any]:
        """Build the checkpoint dictionary for serialization."""
        from genetics.serialize import config_to_dict

        return {
            "schema_version": 1,
            "generation": self.generation,
            "n_islands": self.n_islands,
            "pop_size_per_island": self.pop_size_per_island,
            "seed": self.seed,
            "islands": [
                {
                    "id": is_.id,
                    "generation": is_.generation,
                    "population": population_to_dict(is_.population),
                }
                for is_ in self.islands
            ],
            "migration_policy": {
                "interval": self.migration_policy.interval,
                "size": self.migration_policy.size,
                "replacement": self.migration_policy.replacement,
            },
            "config": config_to_dict(self.genome_config),
            "signal_type": getattr(self, "_signal_type", "genome"),
        }

    @staticmethod
    def load_checkpoint(path: str, genome_config: GenomeConfig) -> IslandManager:
        """Load an :class:`IslandManager` from a JSON checkpoint file.

        Args:
            path: Path to the checkpoint JSON file.
            genome_config: Genome configuration to rebuild populations.

        Returns:
            Restored :class:`IslandManager` ready to resume evolution.

        Raises:
            ValueError: If the checkpoint schema version is unsupported.
            FileNotFoundError: If the checkpoint file does not exist.
        """
        import json

        with open(path) as f:
            data = json.load(f)

        schema_version = data.get("schema_version", 0)
        if schema_version != 1:
            msg = f"Unsupported checkpoint schema version: {schema_version}"
            raise ValueError(msg)

        manager = IslandManager(
            genome_config=genome_config,
            n_islands=data["n_islands"],
            pop_size_per_island=data["pop_size_per_island"],
            seed=data["seed"],
        )

        for island_data in data["islands"]:
            island_id = island_data["id"]
            if island_id < len(manager.islands):
                island = manager.islands[island_id]
                island.generation = island_data["generation"]
                island.population = population_from_dict(island_data["population"], island.toolbox)

        # Restore migration policy if present
        if "migration_policy" in data:
            mp = data["migration_policy"]
            manager.migration_policy = MigrationPolicy(
                interval=mp.get("interval", 5),
                size=mp.get("size", 3),
                replacement=mp.get("replacement", True),
            )

        return manager
