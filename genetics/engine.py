"""Top-level genetic algorithm engine with checkpoint/restart.

Provides :class:`GAConfig` (configuration), :class:`GAResult` (output),
and :class:`GeneticEngine` (orchestrator) that manages the full
evolutionary run across multiple islands with periodic checkpointing.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from analytics.backtest.config import BacktestConfig
from genetics.genome.signal import GenomeConfig
from genetics.islands import IslandManager, PopulationStats

if TYPE_CHECKING:
    import polars as pl

    from core.domain.experiment import ExperimentRegistry
    from genetics.fitness.evaluator import WalkForwardConfig

__all__ = [
    "GAConfig",
    "GAResult",
    "GeneticEngine",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class GAConfig:
    """Top-level GA configuration.

    Attributes:
        genome_config: Genome definition (parameters and bounds).
        pop_size: Total population size across all islands.
        generations: Number of generations to evolve.
        n_islands: Number of parallel island sub-populations.
        crossover_prob: Crossover probability.
        mutation_prob: Mutation probability.
        seed: Random seed for reproducibility.
        checkpoint_interval: Save checkpoint every *N* generations.
        resume_from: Path to a checkpoint file to resume from.
        n_jobs: Number of parallel worker processes (``None`` → CPU count).
        signal_type: Which signal implementation to use (``"genome"``,
            ``"alpha"``, or ``"knn"``).
        checkpoint_dir: Directory for checkpoint files.
    """

    genome_config: GenomeConfig
    pop_size: int = 100
    generations: int = 50
    n_islands: int = 4
    crossover_prob: float = 0.8
    mutation_prob: float = 0.2
    seed: int = 42
    checkpoint_interval: int = 5
    resume_from: str | None = None
    n_jobs: int | None = None
    signal_type: str = "genome"
    checkpoint_dir: str = "checkpoints/"
    min_trades: int = 0
    seed_genomes: list[dict[str, float | int | str]] | None = None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class GAResult:
    """Result of a complete GA run.

    Attributes:
        config: The :class:`GAConfig` used for this run.
        pareto_front: Pareto-optimal individuals from the final population.
        hall_of_fame: All-time best individuals.
        generations_log: Per-generation statistics.
        timing: Wall-clock time in seconds.
        checkpoint_paths: Paths to all checkpoints saved during the run.
        n_fitness_evaluations: Total number of fitness evaluations performed.
    """

    config: GAConfig
    pareto_front: list[Any] = field(default_factory=list)
    hall_of_fame: list[Any] = field(default_factory=list)
    generations_log: list[dict[str, Any]] = field(default_factory=list)
    timing: float = 0.0
    checkpoint_paths: list[str] = field(default_factory=list)
    n_fitness_evaluations: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GeneticEngine:
    """Top-level genetic algorithm engine with checkpoint/restart.

    Uses an island model with parallel sub-populations, periodic
    checkpointing, and graceful shutdown on SIGTERM/SIGINT.
    """

    def __init__(self, config: GAConfig) -> None:
        self.config = config
        self._island_manager: IslandManager | None = None
        self._generations_log: list[dict[str, Any]] = []
        self._checkpoint_paths: list[str] = []
        self._n_evaluations: int = 0
        self._start_generation: int = 0
        self._interrupted: bool = False
        self._signal_received: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        data: pl.DataFrame,
        backtest_config: BacktestConfig | None = None,
        walk_forward_config: WalkForwardConfig | None = None,
        registry: ExperimentRegistry | None = None,
    ) -> GAResult:
        """Execute the full GA optimisation run.

        Creates an :class:`IslandManager` (or resumes from a checkpoint),
        then iterates through generations — each generation evaluates all
        islands in parallel, applies migration, and optionally checkpoints.

        Args:
            data: Market data for fitness evaluation.
            backtest_config: Backtest configuration.
            walk_forward_config: Walk-forward validation configuration.
            registry: Optional experiment registry for tracking.

        Returns:
            A :class:`GAResult` with the final Pareto front and run stats.
        """
        start_time = time.monotonic()

        # ── Set up signal handlers for graceful shutdown ──────────────
        self._interrupted = False
        self._signal_received = None
        original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)

        try:
            # ── Create / restore island manager ───────────────────────
            if self.config.resume_from and os.path.exists(self.config.resume_from):
                self._island_manager = IslandManager.load_checkpoint(
                    self.config.resume_from,
                    self.config.genome_config,
                )
                self._start_generation = self._island_manager.generation
            else:
                pop_per_island = self.config.pop_size // self.config.n_islands
                # Encode seed genomes from GAConfig into normalized float vectors
                encoded_seeds: list[list[float]] | None = None
                if self.config.seed_genomes:
                    from genetics.genome.signal import encode
                    encoded_seeds = []
                    for raw in self.config.seed_genomes:
                        try:
                            g = encode(raw, self.config.genome_config.param_defs)
                            encoded_seeds.append(list(g.normalized_params))
                        except Exception:
                            continue
                self._island_manager = IslandManager(
                    genome_config=self.config.genome_config,
                    n_islands=self.config.n_islands,
                    pop_size_per_island=pop_per_island,
                    seed=self.config.seed,
                    checkpoint_dir=self.config.checkpoint_dir,
                    seed_genomes=encoded_seeds,
                )
                self._start_generation = 0

            # Tag checkpoint data with signal_type for restore
            self._island_manager._signal_type = self.config.signal_type

            # ── Create evaluator ──────────────────────────────────────
            from genetics.fitness.evaluator import FitnessEvaluator

            bt_config = backtest_config or BacktestConfig()

            # Map signal_type to factory callable
            signal_factory: Callable[..., Any] | None = None
            if self.config.signal_type == "alpha":
                from genetics.genome.signal import AlphaGenomeToSignal
                signal_factory = AlphaGenomeToSignal
            elif self.config.signal_type == "knn":
                from genetics.genome.knn_signal import KNNGenomeToSignal
                signal_factory = KNNGenomeToSignal
            elif self.config.signal_type == "hybrid":
                from genetics.genome.hybrid_signal import HybridGenomeToSignal
                signal_factory = HybridGenomeToSignal
            elif self.config.signal_type != "genome":
                msg = f"Unknown signal_type: {self.config.signal_type!r}"
                raise ValueError(msg)

            evaluator = FitnessEvaluator(
                backtest_config=bt_config,
                walk_forward_config=walk_forward_config,
                registry=registry,
                signal_factory=signal_factory,
                min_trades=self.config.min_trades,
            )

            # ── Process pool for parallel island execution ────────────
            n_jobs = self.config.n_jobs or multiprocessing.cpu_count()
            individual_executor = ThreadPoolExecutor(
                max_workers=max(1, n_jobs // self.config.n_islands),
            )

            # ── Hall of Fame (wraps DEAP's) ────────────────────────────
            from deap import tools as deap_tools

            hof = deap_tools.HallOfFame(maxsize=20)

            # ── Main evolution loop ───────────────────────────────────
            for gen in range(self._start_generation, self.config.generations):
                if self._interrupted:
                    self._signal_received = "interrupted"
                    break

                # Run all islands in parallel
                island_stats: list[PopulationStats] = await self._island_manager.run_generation(
                    generation=gen,
                    evaluator=evaluator,
                    data=data,
                    cxpb=self.config.crossover_prob,
                    mutpb=self.config.mutation_prob,
                    executor=individual_executor,
                )

                # Apply migration if due
                self._island_manager.migrate()

                # Update hall of fame with all island individuals
                for island in self._island_manager.islands:
                    hof.update(island.population)

                # Aggregate statistics
                gen_stats = self._aggregate_stats(gen, island_stats)
                self._generations_log.append(gen_stats)
                self._n_evaluations += sum(ps.n_evaluated for ps in island_stats)

                # Checkpoint
                if (gen + 1) % self.config.checkpoint_interval == 0:
                    ckpt_path = os.path.join(
                        self.config.checkpoint_dir,
                        f"gen_{gen + 1:04d}.json",
                    )
                    self._island_manager.save_checkpoint(ckpt_path)
                    self._checkpoint_paths.append(ckpt_path)

        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

        # ── Save final checkpoint ─────────────────────────────────────
        final_checkpoint = os.path.join(
            self.config.checkpoint_dir,
            "final.json",
        )
        if self._island_manager is not None:
            self._island_manager.save_checkpoint(final_checkpoint)
            self._checkpoint_paths.append(final_checkpoint)

        # ── Merge Pareto fronts ───────────────────────────────────────
        pareto_front: list[Any] = []
        if self._island_manager is not None:
            pareto_front = self._island_manager.merge_pareto_fronts()

        elapsed = time.monotonic() - start_time

        return GAResult(
            config=self.config,
            pareto_front=pareto_front,
            hall_of_fame=list(hof),
            generations_log=self._generations_log,
            timing=elapsed,
            checkpoint_paths=self._checkpoint_paths,
            n_fitness_evaluations=self._n_evaluations,
        )

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        """Gracefully interrupt the GA run, allowing checkpoint save."""
        self._interrupted = True
        sig_name = signal.Signals(signum).name
        self._signal_received = sig_name

    # ------------------------------------------------------------------
    # Checkpoint / restore
    # ------------------------------------------------------------------

    @staticmethod
    def restore(checkpoint_path: str, genome_config: GenomeConfig) -> GeneticEngine:
        """Restore a :class:`GeneticEngine` from a checkpoint file.

        Loads the checkpoint and returns an engine configured to resume
        from the saved generation.

        Args:
            checkpoint_path: Path to a checkpoint JSON file (as saved by
                :meth:`IslandManager.save_checkpoint`).
            genome_config: Genome configuration.

        Returns:
            A :class:`GeneticEngine` ready to call :meth:`run` — it will
            skip already-completed generations automatically.

        Raises:
            FileNotFoundError: If the checkpoint does not exist.
            ValueError: If the checkpoint format is invalid.
        """
        if not os.path.exists(checkpoint_path):
            msg = f"Checkpoint not found: {checkpoint_path}"
            raise FileNotFoundError(msg)

        with open(checkpoint_path) as f:
            data: dict[str, Any] = json.load(f)

        # Validate schema
        schema_version = data.get("schema_version", 0)
        if schema_version != 1:
            msg = f"Unsupported checkpoint schema version: {schema_version}"
            raise ValueError(msg)

        pop_size = data.get("pop_size_per_island", 25) * data.get("n_islands", 4)
        config = GAConfig(
            genome_config=genome_config,
            pop_size=pop_size,
            n_islands=data.get("n_islands", 4),
            seed=data.get("seed", 42),
            signal_type=data.get("signal_type", "genome"),
            resume_from=checkpoint_path,
        )

        engine = GeneticEngine(config)
        engine._island_manager = IslandManager.load_checkpoint(
            checkpoint_path,
            genome_config,
        )
        engine._start_generation = data.get("generation", 0)

        return engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _aggregate_stats(
        self,
        generation: int,
        island_stats: list[PopulationStats],
    ) -> dict[str, Any]:
        """Combine per-island stats into a single generation log entry."""
        n_pareto = sum(ps.n_pareto for ps in island_stats)
        diversity = (
            sum(ps.diversity for ps in island_stats) / len(island_stats)
            if island_stats
            else 0.0
        )
        n_evaluated = sum(ps.n_evaluated for ps in island_stats)
        return {
            "generation": generation,
            "n_islands": len(island_stats),
            "n_pareto": n_pareto,
            "diversity": round(diversity, 6),
            "n_evaluated": n_evaluated,
        }

    @property
    def island_manager(self) -> IslandManager | None:
        """The underlying :class:`IslandManager` (``None`` before :meth:`run`)."""
        return self._island_manager
