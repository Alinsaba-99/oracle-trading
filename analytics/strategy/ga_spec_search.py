"""GA search over StrategySpec space (R4).

Uses a lightweight evolutionary algorithm that mutates and crosses over
StrategySpec dicts. Each candidate is evaluated via evaluator.evaluate_spec
(same fitness function as the LLM researcher).
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

from analytics.backtest.providers import DataRegistry
from analytics.strategy.evaluator import evaluate_spec
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.spec import (
    ENTRY_TYPES,
    FILTER_MODES,
    INSTRUMENTS,
    REGIMES,
    TIMEFRAMES,
    StrategySpec,
)

logger = logging.getLogger("oracle.strategy.ga_spec_search")

# Parameter ranges for mutation
ENTRY_PARAM_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "donchian_breakout": {"period": (10, 80)},
    "ema_trend": {"fast": (5, 30), "slow": (20, 120)},
    "rsi_reversion": {"period": (5, 30), "oversold": (20, 40), "exit_level": (50, 70)},
    "bband_reversion": {"period": (10, 40), "std": (1.0, 3.0)},
    "trend_filtered_breakout": {"period": (10, 60), "ma_period": (50, 200)},
    "roc_momentum": {"period": (5, 30)},
    "zscore_reversion": {"period": (10, 60), "entry_z": (1.5, 3.0)},
    "keltner_reversion": {"period": (10, 40), "mult": (1.0, 3.0)},
    "adx_trend": {"period": (10, 30), "threshold": (20, 35)},
    "macd_trend": {"fast": (8, 16), "slow": (20, 40), "signal": (5, 12)},
    "pullback": {"trend_period": (20, 100), "pullback_pct": (0.01, 0.05)},
    "volume_breakout": {"period": (10, 40), "vol_mult": (1.5, 3.0)},
}

# Integer parameters (must be rounded to int)
_INT_PARAMS = {
    "period",
    "fast",
    "slow",
    "signal",
    "trend_period",
    "oversold",
    "exit_level",
    "threshold",
    "ma_period",
}

# Higher-TF options (must be strictly higher than primary; must exist in lake)
_HIGHER_TF: dict[str, list[str]] = {"1h": ["4h", "1d"], "4h": ["1d"], "1d": []}


def _random_params(rng: random.Random, entry: str) -> dict[str, int | float]:
    ranges = ENTRY_PARAM_RANGES.get(entry, {})
    params: dict[str, int | float] = {}
    for k, (lo, hi) in ranges.items():
        v = rng.uniform(lo, hi)
        params[k] = round(v) if k in _INT_PARAMS else round(v, 4)
    return params


def random_spec(name: str, rng: random.Random | None = None) -> StrategySpec:
    """Generate a random valid StrategySpec."""
    if rng is None:
        rng = random.Random()
    instrument = rng.choice(list(INSTRUMENTS.keys()))
    entry = rng.choice(list(ENTRY_TYPES.keys()))
    timeframe = rng.choice(TIMEFRAMES)
    regime = rng.choice(REGIMES)
    params = _random_params(rng, entry)
    risk_pct = round(rng.uniform(0.005, 0.02), 4)
    stop_atr_mult = round(rng.uniform(1.0, 4.0), 2)

    # 20% chance of multi-TF
    filter_tf = None
    filter_entry = None
    filter_params: dict[str, int | float] = {}
    filter_mode = "gate"
    filter_sign = 1

    higher_options = _HIGHER_TF.get(timeframe, [])
    if higher_options and rng.random() < 0.2:
        filter_tf = rng.choice(higher_options)
        filter_entry = rng.choice(list(ENTRY_TYPES.keys()))
        filter_params = _random_params(rng, filter_entry)
        filter_mode = rng.choice(FILTER_MODES)
        filter_sign = rng.choice([1, -1])

    return StrategySpec(
        name=name,
        instrument=instrument,
        entry=entry,
        entry_params=params,
        timeframe=timeframe,
        regime=regime,
        risk_pct=risk_pct,
        stop_atr_mult=stop_atr_mult,
        filter_tf=filter_tf,
        filter_entry=filter_entry,
        filter_entry_params=filter_params,
        filter_mode=filter_mode,
        filter_sign=filter_sign,
    )


def mutate_spec(spec: StrategySpec, rng: random.Random | None = None) -> StrategySpec:
    """Mutate one or two fields of a spec."""
    if rng is None:
        rng = random.Random()
    data = spec.model_dump()

    field_choice = rng.choice(
        ["instrument", "entry", "timeframe", "regime", "entry_params", "risk_pct", "stop_atr_mult"]
    )

    if field_choice == "instrument":
        data["instrument"] = rng.choice(list(INSTRUMENTS.keys()))

    elif field_choice == "entry":
        new_entry = rng.choice(list(ENTRY_TYPES.keys()))
        data["entry"] = new_entry
        data["entry_params"] = _random_params(rng, new_entry)

    elif field_choice == "timeframe":
        data["timeframe"] = rng.choice(TIMEFRAMES)
        # Re-validate filter_tf
        higher = _HIGHER_TF.get(data["timeframe"], [])
        if data.get("filter_tf") and data["filter_tf"] not in higher:
            data["filter_tf"] = None
            data["filter_entry"] = None
            data["filter_entry_params"] = {}

    elif field_choice == "regime":
        data["regime"] = rng.choice(REGIMES)

    elif field_choice == "entry_params":
        ranges = ENTRY_PARAM_RANGES.get(data["entry"], {})
        params = dict(data["entry_params"])
        if ranges:
            k = rng.choice(list(ranges.keys()))
            lo, hi = ranges[k]
            # Mutate by ±10-30% of range
            delta = rng.uniform(0.1, 0.3) * (hi - lo) * rng.choice([-1, 1])
            v = max(lo, min(hi, params.get(k, (lo + hi) / 2) + delta))
            params[k] = round(v) if k in _INT_PARAMS else round(v, 4)
        data["entry_params"] = params

    elif field_choice == "risk_pct":
        data["risk_pct"] = round(rng.uniform(0.005, 0.02), 4)

    elif field_choice == "stop_atr_mult":
        data["stop_atr_mult"] = round(rng.uniform(1.0, 4.0), 2)

    return StrategySpec(**data)


def crossover_specs(
    a: StrategySpec, b: StrategySpec, name: str, rng: random.Random | None = None
) -> StrategySpec:
    """Combine fields from two parent specs."""
    if rng is None:
        rng = random.Random()

    # Pick instrument from one parent, entry from the other
    instrument = rng.choice([a.instrument, b.instrument])
    entry = rng.choice([a.entry, b.entry])
    timeframe = rng.choice([a.timeframe, b.timeframe])
    regime = rng.choice([a.regime, b.regime])
    risk_pct = rng.choice([a.risk_pct, b.risk_pct])
    stop_atr_mult = rng.choice([a.stop_atr_mult, b.stop_atr_mult])

    # Blend entry_params: take from the parent whose entry was chosen, with small noise
    if entry == a.entry:
        params = dict(a.entry_params)
    elif entry == b.entry:
        params = dict(b.entry_params)
    else:
        params = _random_params(rng, entry)

    # Light mutation on inherited params
    ranges = ENTRY_PARAM_RANGES.get(entry, {})
    for k, (lo, hi) in ranges.items():
        if k in params and rng.random() < 0.2:
            delta = rng.uniform(-0.1, 0.1) * (hi - lo)
            v = max(lo, min(hi, params[k] + delta))
            params[k] = round(v) if k in _INT_PARAMS else round(v, 4)

    # Multi-TF: inherit from either parent if valid
    filter_tf = None
    filter_entry = None
    filter_params: dict[str, int | float] = {}
    filter_mode = "gate"
    filter_sign = 1

    higher = _HIGHER_TF.get(timeframe, [])
    parent_filter = rng.choice([a, b])
    if parent_filter.filter_tf and parent_filter.filter_tf in higher:
        filter_tf = parent_filter.filter_tf
        filter_entry = parent_filter.filter_entry
        filter_params = dict(parent_filter.filter_entry_params)
        filter_mode = parent_filter.filter_mode
        filter_sign = parent_filter.filter_sign

    return StrategySpec(
        name=name,
        instrument=instrument,
        entry=entry,
        entry_params=params,
        timeframe=timeframe,
        regime=regime,
        risk_pct=risk_pct,
        stop_atr_mult=stop_atr_mult,
        filter_tf=filter_tf,
        filter_entry=filter_entry,
        filter_entry_params=filter_params,
        filter_mode=filter_mode,
        filter_sign=filter_sign,
    )


@dataclass
class GASearchConfig:
    pop_size: int = 30
    n_generations: int = 20
    n_elite: int = 5
    mutation_rate: float = 0.3
    tournament_size: int = 3
    seed: int | None = None


@dataclass
class GASearchResult:
    specs: list[tuple[StrategySpec, FitnessReport]]  # all evaluated specs
    best: tuple[StrategySpec, FitnessReport] | None
    generation_bests: list[tuple[int, float, str]]  # (gen, fitness, name)
    total_evaluations: int
    elapsed_s: float


def _tournament_select(
    population: list[tuple[StrategySpec, FitnessReport]], k: int, rng: random.Random
) -> StrategySpec:
    """k-way tournament selection; returns the winner spec."""
    contestants = rng.sample(population, min(k, len(population)))
    winner = max(contestants, key=lambda x: x[1].fitness)
    return winner[0]


def ga_spec_search(
    registry: DataRegistry,
    mode: EvalMode | str = EvalMode.FIRM,
    config: GASearchConfig | None = None,
    eval_kwargs: dict[str, Any] | None = None,
) -> GASearchResult:
    """Run GA search over StrategySpec space."""
    cfg = config or GASearchConfig()
    rng = random.Random(cfg.seed)
    kwargs = eval_kwargs or {}
    t0 = time.time()

    all_evaluated: list[tuple[StrategySpec, FitnessReport]] = []
    generation_bests: list[tuple[int, float, str]] = []
    counter = 0

    def _name() -> str:
        nonlocal counter
        counter += 1
        return f"ga_{counter:04d}"

    def _eval(spec: StrategySpec) -> FitnessReport:
        try:
            return evaluate_spec(spec, registry, mode, **kwargs)
        except Exception as exc:
            logger.warning("evaluate_spec failed for %s: %s", spec.name, exc)
            return FitnessReport(mode=EvalMode(mode), fitness=-1.0)

    # --- Initialize population ---
    logger.info("GA init: pop_size=%d generations=%d", cfg.pop_size, cfg.n_generations)
    population: list[tuple[StrategySpec, FitnessReport]] = []
    for _ in range(cfg.pop_size):
        spec = random_spec(_name(), rng)
        report = _eval(spec)
        population.append((spec, report))
        all_evaluated.append((spec, report))
        logger.debug("init %s fitness=%.4f", spec.name, report.fitness)

    population.sort(key=lambda x: x[1].fitness, reverse=True)
    if population:
        gen0_best = population[0]
        generation_bests.append((0, gen0_best[1].fitness, gen0_best[0].name))
        logger.info("gen=0 best=%s fitness=%.4f", gen0_best[0].name, gen0_best[1].fitness)

    # --- Generational loop ---
    for gen in range(1, cfg.n_generations + 1):
        elites = population[: cfg.n_elite]
        new_pop: list[tuple[StrategySpec, FitnessReport]] = list(elites)

        n_offspring = cfg.pop_size - cfg.n_elite
        for _ in range(n_offspring):
            parent_a = _tournament_select(population, cfg.tournament_size, rng)
            parent_b = _tournament_select(population, cfg.tournament_size, rng)
            child = crossover_specs(parent_a, parent_b, _name(), rng)
            if rng.random() < cfg.mutation_rate:
                child = mutate_spec(child, rng)
            report = _eval(child)
            new_pop.append((child, report))
            all_evaluated.append((child, report))
            logger.debug("gen=%d %s fitness=%.4f", gen, child.name, report.fitness)

        new_pop.sort(key=lambda x: x[1].fitness, reverse=True)
        population = new_pop

        if population:
            best_this_gen = population[0]
            generation_bests.append((gen, best_this_gen[1].fitness, best_this_gen[0].name))
            logger.info(
                "gen=%d best=%s fitness=%.4f", gen, best_this_gen[0].name, best_this_gen[1].fitness
            )

    all_evaluated.sort(key=lambda x: x[1].fitness, reverse=True)
    best = all_evaluated[0] if all_evaluated else None

    return GASearchResult(
        specs=all_evaluated,
        best=best,
        generation_bests=generation_bests,
        total_evaluations=len(all_evaluated),
        elapsed_s=time.time() - t0,
    )
