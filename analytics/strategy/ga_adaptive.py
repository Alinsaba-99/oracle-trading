"""Adaptive multi-objective GA over the strategy spec space.

The scalar GA in :mod:`ga_spec_search` maximises one number, which makes it
converge onto whatever the fitness function over-rewards — typically high
return with a drawdown that a funded account would never survive. This module
replaces that with three mechanisms that attack the failure modes directly:

* **Pareto ranking (NSGA-II)** over competing objectives, so "high return with
  a deep drawdown" and "modest return that never breaches" both stay in the
  population instead of one crowding the other out.
* **Island model with migration** — sub-populations evolve independently and
  exchange members periodically, which preserves the diversity a single
  panmictic population burns through in a few generations.
* **Adaptive mutation** — the rate rises when the population's spread collapses
  and falls when it is exploring, so the search re-diversifies on its own
  rather than needing a hand-tuned schedule.

Objectives are maximised, so drawdown enters negated. Ranking never sees raw
fitness alone, which is what stops a single lucky backtest from dominating.
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from analytics.backtest.providers import DataRegistry
from analytics.strategy.evaluator import evaluate_spec
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.ga_spec_search import crossover_specs, mutate_spec, random_spec
from analytics.strategy.spec import StrategySpec

log = logging.getLogger("oracle.strategy.ga_adaptive")


@dataclass
class Objectives:
    """One candidate's position in objective space (all maximised)."""

    fitness: float = 0.0
    #: Negated drawdown — deeper drawdown must score worse.
    neg_drawdown: float = 0.0
    #: Risk-adjusted return.
    sharpe: float = 0.0
    #: Trade count, log-scaled: statistical significance saturates, so the
    #: difference between 30 and 60 trades matters far more than 3000 vs 6000.
    log_trades: float = 0.0

    def as_tuple(self) -> tuple[float, ...]:
        return (self.fitness, self.neg_drawdown, self.sharpe, self.log_trades)


def objectives_from(report: FitnessReport) -> Objectives:
    return Objectives(
        fitness=float(report.fitness),
        neg_drawdown=-abs(float(report.max_drawdown)),
        sharpe=float(report.sharpe),
        log_trades=math.log1p(max(0, int(report.total_trades))),
    )


@dataclass
class Individual:
    spec: StrategySpec
    report: FitnessReport
    objectives: Objectives
    island: int = 0
    #: NSGA-II Pareto front index; 0 is the non-dominated front.
    rank: int = 0
    #: Crowding distance within the front — higher means more isolated.
    crowding: float = 0.0

    @property
    def fitness(self) -> float:
        return self.report.fitness


# --------------------------------------------------------------- NSGA-II core


def dominates(a: Objectives, b: Objectives) -> bool:
    """True when ``a`` is at least as good everywhere and strictly better once."""
    at = a.as_tuple()
    bt = b.as_tuple()
    strictly_better = False
    for x, y in zip(at, bt, strict=True):
        if x < y:
            return False
        if x > y:
            strictly_better = True
    return strictly_better


def _domination_matrix(population: list[Individual]) -> tuple[list[list[int]], list[int]]:
    """Return (indices each member dominates, how many dominate each member)."""
    dominated_by: list[list[int]] = [[] for _ in population]
    domination_count = [0] * len(population)
    # Each unordered pair is compared once; the relation is antisymmetric.
    for i in range(len(population)):
        for j in range(i + 1, len(population)):
            a, b = population[i].objectives, population[j].objectives
            if dominates(a, b):
                dominated_by[i].append(j)
                domination_count[j] += 1
            elif dominates(b, a):
                dominated_by[j].append(i)
                domination_count[i] += 1
    return dominated_by, domination_count


def fast_non_dominated_sort(population: list[Individual]) -> list[list[Individual]]:
    """Partition into Pareto fronts, assigning ``rank`` in place."""
    fronts: list[list[Individual]] = []
    dominated_by, domination_count = _domination_matrix(population)

    current = [i for i, count in enumerate(domination_count) if count == 0]
    rank = 0
    while current:
        for i in current:
            population[i].rank = rank
        fronts.append([population[i] for i in current])
        nxt: list[int] = []
        for i in current:
            for j in dominated_by[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    nxt.append(j)
        current = nxt
        rank += 1
    return fronts


def assign_crowding_distance(front: list[Individual]) -> None:
    """Set crowding distance within one front (boundary members get infinity).

    This is what maintains spread along the front: without it, selection
    collapses onto whichever region of objective space happens to be denser.
    """
    if not front:
        return
    n_obj = len(front[0].objectives.as_tuple())
    for ind in front:
        ind.crowding = 0.0
    for m in range(n_obj):
        front.sort(key=lambda ind: ind.objectives.as_tuple()[m])
        lo = front[0].objectives.as_tuple()[m]
        hi = front[-1].objectives.as_tuple()[m]
        # Boundary solutions are always kept — they define the front's extent.
        front[0].crowding = math.inf
        front[-1].crowding = math.inf
        span = hi - lo
        if span <= 0:
            continue
        for k in range(1, len(front) - 1):
            prev_v = front[k - 1].objectives.as_tuple()[m]
            next_v = front[k + 1].objectives.as_tuple()[m]
            front[k].crowding += (next_v - prev_v) / span


def crowded_compare(a: Individual, b: Individual) -> Individual:
    """NSGA-II tournament: lower rank wins, then higher crowding distance."""
    if a.rank != b.rank:
        return a if a.rank < b.rank else b
    if a.crowding != b.crowding:
        return a if a.crowding > b.crowding else b
    return a if a.fitness >= b.fitness else b


def select_survivors(population: list[Individual], n: int) -> list[Individual]:
    """Elitist truncation by front, using crowding to cut the boundary front."""
    if len(population) <= n:
        return list(population)
    fronts = fast_non_dominated_sort(population)
    survivors: list[Individual] = []
    for front in fronts:
        assign_crowding_distance(front)
        if len(survivors) + len(front) <= n:
            survivors.extend(front)
            continue
        # Partially admit this front, keeping the most isolated members.
        front.sort(key=lambda ind: ind.crowding, reverse=True)
        survivors.extend(front[: n - len(survivors)])
        break
    return survivors


# ------------------------------------------------------------------ diversity


def spec_signature(spec: StrategySpec) -> tuple[str, str, str, str | None, str | None]:
    """Coarse structural identity, used to measure population diversity.

    Deliberately ignores parameter values: two Donchian breakouts with periods
    20 and 22 are the same idea, and counting them as distinct would report a
    converged population as diverse.
    """
    return (spec.instrument, spec.entry, spec.timeframe, spec.filter_tf, spec.filter_entry)


def population_diversity(population: list[Individual]) -> float:
    """Fraction of distinct structural signatures (1.0 = all different)."""
    if not population:
        return 0.0
    return len({spec_signature(ind.spec) for ind in population}) / len(population)


def adaptive_mutation_rate(
    diversity: float, base_rate: float, *, floor: float = 0.15, ceiling: float = 0.85
) -> float:
    """Raise mutation as diversity collapses.

    Converging on a local optimum is the usual GA failure. Scaling mutation
    inversely with diversity makes the search push back out on its own instead
    of grinding on near-duplicates.
    """
    rate = base_rate + (1.0 - max(0.0, min(1.0, diversity))) * (ceiling - base_rate)
    return float(max(floor, min(ceiling, rate)))


@dataclass
class AdaptiveGAConfig:
    #: Members per island. Total population = pop_per_island * n_islands.
    pop_per_island: int = 20
    n_islands: int = 4
    n_generations: int = 25
    #: Base mutation rate, scaled up automatically as diversity falls.
    base_mutation_rate: float = 0.25
    tournament_size: int = 3
    #: Generations between migrations; 0 disables migration entirely.
    migration_interval: int = 5
    #: Members each island sends to its neighbour on a migration generation.
    migration_size: int = 2
    #: Fresh random specs injected per generation to fight stagnation.
    n_random_immigrants: int = 1
    seed: int | None = None


@dataclass
class AdaptiveGAResult:
    #: Every candidate evaluated, best-first by scalar fitness.
    all_evaluated: list[Individual] = field(default_factory=list)
    #: The final non-dominated front — the set of real trade-offs.
    pareto_front: list[Individual] = field(default_factory=list)
    best: Individual | None = None
    #: (generation, best_fitness, mean_fitness, diversity, mutation_rate)
    history: list[tuple[int, float, float, float, float]] = field(default_factory=list)
    total_evaluations: int = 0
    elapsed_s: float = 0.0

    def summary(self) -> str:
        lines = [
            f"evaluations={self.total_evaluations} elapsed={self.elapsed_s:.1f}s",
            f"pareto_front={len(self.pareto_front)}",
        ]
        if self.best is not None:
            b = self.best
            lines.append(
                f"best={b.spec.name} fitness={b.fitness:.4f} "
                f"sharpe={b.report.sharpe:.2f} "
                f"dd={abs(b.report.max_drawdown) * 100:.1f}% "
                f"trades={b.report.total_trades}"
            )
        return "\n".join(lines)


def _migrate(islands: list[list[Individual]], n_migrants: int, rng: random.Random) -> None:
    """Ring migration: each island sends its best few to the next island.

    Migrants are copied rather than moved, so a good idea can spread without
    any island losing population.
    """
    if len(islands) < 2 or n_migrants <= 0:
        return
    outgoing: list[list[Individual]] = []
    for island in islands:
        ranked = sorted(island, key=lambda ind: ind.fitness, reverse=True)
        outgoing.append(ranked[:n_migrants])
    for idx, island in enumerate(islands):
        migrants = outgoing[(idx - 1) % len(islands)]
        # Displace this island's weakest so size stays constant.
        island.sort(key=lambda ind: ind.fitness)
        for offset, migrant in enumerate(migrants):
            if offset < len(island):
                island[offset] = Individual(
                    spec=migrant.spec,
                    report=migrant.report,
                    objectives=migrant.objectives,
                    island=idx,
                )
    del rng  # ring topology is deterministic; kept for signature stability


def _advance_island(
    island: list[Individual],
    island_idx: int,
    *,
    cfg: AdaptiveGAConfig,
    rng: random.Random,
    mutation_rate: float,
    name: Any,
    evaluate: Any,
) -> list[Individual]:
    """Produce the next generation of one island (elitist, NSGA-II selection)."""
    # Rank within the island so tournaments can use rank + crowding.
    for front in fast_non_dominated_sort(island):
        assign_crowding_distance(front)

    def _pick() -> Individual:
        contestants = [rng.choice(island) for _ in range(max(2, cfg.tournament_size))]
        winner = contestants[0]
        for challenger in contestants[1:]:
            winner = crowded_compare(winner, challenger)
        return winner

    offspring: list[Individual] = []
    n_children = max(0, cfg.pop_per_island - cfg.n_random_immigrants)
    for _ in range(n_children):
        child_spec = crossover_specs(_pick().spec, _pick().spec, name(), rng)
        if rng.random() < mutation_rate:
            child_spec = mutate_spec(child_spec, rng)
        offspring.append(evaluate(child_spec, island_idx))

    # Fresh blood: guarantees the island can still reach unexplored regions
    # even after it has converged internally.
    for _ in range(cfg.n_random_immigrants):
        offspring.append(evaluate(random_spec(name(), rng), island_idx))

    # Parents and children compete for the same slots.
    return select_survivors(island + offspring, cfg.pop_per_island)


def adaptive_ga_search(
    registry: DataRegistry,
    mode: EvalMode | str = EvalMode.FIRM,
    config: AdaptiveGAConfig | None = None,
    eval_kwargs: dict[str, Any] | None = None,
) -> AdaptiveGAResult:
    """Run the island-model NSGA-II search over the spec space."""
    cfg = config or AdaptiveGAConfig()
    mode = EvalMode(mode)
    rng = random.Random(cfg.seed)
    kwargs = eval_kwargs or {}
    t0 = time.time()

    all_evaluated: list[Individual] = []
    history: list[tuple[int, float, float, float, float]] = []
    counter = 0

    def _name() -> str:
        nonlocal counter
        counter += 1
        return f"aga_{counter:05d}"

    def _evaluate(spec: StrategySpec, island: int) -> Individual:
        try:
            report = evaluate_spec(spec, registry, mode, **kwargs)
        except Exception as exc:
            log.debug("evaluate_spec failed for %s: %s", spec.name, exc)
            # A failed evaluation must not win anything, but keeping it in the
            # population preserves the island's size.
            report = FitnessReport(mode=mode, fitness=-1.0)
        ind = Individual(
            spec=spec, report=report, objectives=objectives_from(report), island=island
        )
        all_evaluated.append(ind)
        return ind

    # ── seed the islands ───────────────────────────────────────────────────
    log.info(
        "adaptive GA: %d islands x %d members x %d generations",
        cfg.n_islands,
        cfg.pop_per_island,
        cfg.n_generations,
    )
    islands: list[list[Individual]] = [
        [_evaluate(random_spec(_name(), rng), island_idx) for _ in range(cfg.pop_per_island)]
        for island_idx in range(cfg.n_islands)
    ]

    # ── generational loop ──────────────────────────────────────────────────
    for gen in range(1, cfg.n_generations + 1):
        flat = [ind for island in islands for ind in island]
        diversity = population_diversity(flat)
        mutation_rate = adaptive_mutation_rate(diversity, cfg.base_mutation_rate)

        for island_idx, island in enumerate(islands):
            islands[island_idx] = _advance_island(
                island,
                island_idx,
                cfg=cfg,
                rng=rng,
                mutation_rate=mutation_rate,
                name=_name,
                evaluate=_evaluate,
            )

        if cfg.migration_interval and gen % cfg.migration_interval == 0:
            _migrate(islands, cfg.migration_size, rng)
            log.debug("gen=%d migrated %d per island", gen, cfg.migration_size)

        flat = [ind for island in islands for ind in island]
        fitnesses = [ind.fitness for ind in flat]
        best_fit = max(fitnesses) if fitnesses else 0.0
        mean_fit = statistics.fmean(fitnesses) if fitnesses else 0.0
        history.append((gen, best_fit, mean_fit, diversity, mutation_rate))
        log.info(
            "gen=%d best=%.4f mean=%.4f diversity=%.2f mutation=%.2f",
            gen,
            best_fit,
            mean_fit,
            diversity,
            mutation_rate,
        )

    # ── assemble the result ────────────────────────────────────────────────
    all_evaluated.sort(key=lambda ind: ind.fitness, reverse=True)
    final = [ind for island in islands for ind in island]
    pareto: list[Individual] = []
    if final:
        fronts = fast_non_dominated_sort(final)
        if fronts:
            pareto = fronts[0]
            assign_crowding_distance(pareto)
            pareto.sort(key=lambda ind: ind.fitness, reverse=True)

    return AdaptiveGAResult(
        all_evaluated=all_evaluated,
        pareto_front=pareto,
        best=all_evaluated[0] if all_evaluated else None,
        history=history,
        total_evaluations=len(all_evaluated),
        elapsed_s=time.time() - t0,
    )
