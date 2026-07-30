"""GA Strategy Evolution — genetic algorithm for factor weight optimization.

Implements the full evolution loop:
  1. Population initialization (random DNA)
  2. Walk-forward fitness evaluation
  3. Tournament selection
  4. Uniform crossover
  5. Gaussian mutation
  6. Elitism replacement

Each DNA is a vector of weights for a pool of signal factors.
Fitness = Sharpe * Calmar / Turnover (multi-objective).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DNA:
    """Genome of a single strategy candidate.

    Attributes:
        factor_weights: Weight for each factor in the pool [0..1].
        risk_params: Dict of risk parameters (stop_loss, take_profit, sizing).
        fitness: Computed fitness score (higher = better).
        sharpe: Walk-forward Sharpe (for reporting).
        calmar: Calmar ratio (for reporting).
        turnover: Trade turnover (for reporting).
    """

    factor_weights: np.ndarray
    risk_params: dict[str, float] = field(
        default_factory=lambda: {"stop_loss_pct": 2.0, "take_profit_pct": 6.0, "sizing_pct": 1.0}
    )
    fitness: float = 0.0
    sharpe: float = 0.0
    calmar: float = 0.0
    turnover: float = 0.0

    @classmethod
    def random(cls, n_factors: int) -> DNA:
        """Create a random DNA with normalized weights."""
        weights = np.random.dirichlet(np.ones(n_factors) * 0.5)
        return cls(factor_weights=weights)

    def mutate(self, mutation_rate: float = 0.1, noise: float = 0.05) -> None:
        """Apply Gaussian mutation to factor weights."""
        mask = np.random.random(len(self.factor_weights)) < mutation_rate
        self.factor_weights[mask] += np.random.randn(mask.sum()) * noise
        self.factor_weights = np.clip(self.factor_weights, 0, 1)
        # Re-normalize
        total = self.factor_weights.sum()
        if total > 0:
            self.factor_weights /= total

    @staticmethod
    def crossover(parent_a: DNA, parent_b: DNA) -> tuple[DNA, DNA]:
        """Uniform crossover between two parents."""
        mask = np.random.random(len(parent_a.factor_weights)) < 0.5
        child1_w = np.where(mask, parent_a.factor_weights, parent_b.factor_weights)
        child2_w = np.where(mask, parent_b.factor_weights, parent_a.factor_weights)
        child1 = DNA(factor_weights=child1_w)
        child2 = DNA(factor_weights=child2_w)
        return child1, child2


class StrategyEvolution:
    """Genetic algorithm for evolving optimal factor weights.

    Args:
        n_factors: Number of signal factors in the pool.
        population_size: Number of DNA per generation.
        n_generations: Maximum generations to evolve.
        mutation_rate: Probability of weight mutation.
        elitism_keep: Number of top DNA to preserve unchanged.
        tournament_size: Tournament selection size.
    """

    def __init__(
        self,
        n_factors: int,
        population_size: int = 100,
        n_generations: int = 50,
        mutation_rate: float = 0.1,
        elitism_keep: int = 3,
        tournament_size: int = 5,
    ) -> None:
        self.n_factors = n_factors
        self.population_size = population_size
        self.n_generations = n_generations
        self.mutation_rate = mutation_rate
        self.elitism_keep = elitism_keep
        self.tournament_size = tournament_size

        self.population: list[DNA] = []
        self.history: list[dict[str, float]] = []

    def initialize(self) -> None:
        """Create initial random population."""
        self.population = [DNA.random(self.n_factors) for _ in range(self.population_size)]

    def evaluate_fitness(self, dna: DNA) -> float:
        """Compute multi-objective fitness.

        This is a PLACEHOLDER — override in subclass or pass a fitness function.
        Default: higher Sharpe * Calmar / (1 + turnover).

        Returns:
            Fitness score (higher = better).
        """
        return dna.sharpe * (dna.calmar + 1.0) / (dna.turnover + 0.01)

    def evaluate_population(self, fitness_fn: Any | None = None) -> None:
        """Evaluate all DNA in the population.

        Args:
            fitness_fn: Optional callable(dna) -> fitness. Uses self.evaluate_fitness if None.
        """
        for dna in self.population:
            if fitness_fn is not None:
                dna.fitness = fitness_fn(dna)
            else:
                dna.fitness = self.evaluate_fitness(dna)

    def tournament_select(self) -> DNA:
        """Select one DNA via tournament selection."""
        contestants = random.sample(self.population, self.tournament_size)
        return max(contestants, key=lambda d: d.fitness)

    def step(self) -> dict[str, float]:
        """Run one generation step.

        Returns:
            Dict with generation stats.
        """
        # Sort by fitness
        self.population.sort(key=lambda d: d.fitness, reverse=True)

        # Elitism: keep top N unchanged
        next_gen: list[DNA] = self.population[: self.elitism_keep]

        # Fill the rest with offspring
        while len(next_gen) < self.population_size:
            parent_a = self.tournament_select()
            parent_b = self.tournament_select()
            child_a, child_b = DNA.crossover(parent_a, parent_b)
            child_a.mutate(self.mutation_rate)
            child_b.mutate(self.mutation_rate)
            next_gen.extend([child_a, child_b])

        self.population = next_gen[: self.population_size]

        best = self.population[0]
        avg_fitness = float(np.mean([d.fitness for d in self.population]))
        stats = {
            "best_fitness": best.fitness,
            "best_sharpe": best.sharpe,
            "avg_fitness": avg_fitness,
            "population_size": len(self.population),
        }
        self.history.append(stats)
        return stats

    def evolve(self, n_generations: int | None = None) -> DNA:
        """Run full evolution loop.

        Args:
            n_generations: Override max generations.

        Returns:
            Best DNA found.
        """
        if not self.population:
            self.initialize()

        gens = n_generations or self.n_generations
        for gen in range(gens):
            stats = self.step()
            if gen % 5 == 0 or gen == gens - 1:
                print(
                    f"  Gen {gen:>3d}: best_fit={stats['best_fitness']:.4f} "
                    f"best_S={stats['best_sharpe']:.4f} "
                    f"avg_fit={stats['avg_fitness']:.4f}"
                )

        self.population.sort(key=lambda d: d.fitness, reverse=True)
        return self.population[0]


__all__ = ["DNA", "StrategyEvolution"]
