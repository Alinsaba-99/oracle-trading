"""Serialization helpers for GA state — checkpoint/restore and JSON round-trips."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from genetics.genome.signal import Genome

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genetics.genome.parameters import GenomeParameter

__all__ = [
    "config_to_dict",
    "dict_to_genome",
    "genome_to_dict",
    "pop_snapshot",
    "population_from_dict",
    "population_to_dict",
    "result_to_dict",
]


def genome_to_dict(genome: Genome) -> dict[str, Any]:
    """Serialize *Genome* to a JSON-compatible dict."""
    return {
        "normalized_params": genome.normalized_params.tolist(),
        "param_names": list(genome.names),
    }


def dict_to_genome(d: dict[str, Any], param_defs: Sequence[GenomeParameter]) -> Genome:
    """Deserialize a dict back into a *Genome*.

    Args:
        d: Dict produced by :func:`genome_to_dict`.
        param_defs: Parameter definitions used for the genome.

    Returns:
        Reconstructed *Genome*.

    Raises:
        ValueError: If the parameter count mismatches ``param_defs``.
    """
    if len(d["normalized_params"]) != len(param_defs):
        msg = (
            f"Parameter count mismatch: {len(d['normalized_params'])} values "
            f"vs {len(param_defs)} defs"
        )
        raise ValueError(msg)
    params = np.array(d["normalized_params"], dtype=np.float64)
    return Genome(normalized_params=params, param_defs=param_defs)


def population_to_dict(population: list[Any]) -> list[dict[str, Any]]:
    """Serialize a DEAP population (list of individuals) to a list of dicts."""
    result: list[dict[str, Any]] = []
    for ind in population:
        entry: dict[str, Any] = {"values": list(ind)}
        if hasattr(ind, "fitness") and ind.fitness.valid:
            entry["fitness"] = {
                "values": _sanitize_fitness(ind.fitness.values),
                "weights": list(ind.fitness.weights),
            }
        result.append(entry)

    return result


def population_from_dict(data: list[dict[str, Any]], toolbox: Any) -> list[Any]:
    """Deserialize a population from a list of dicts produced by :func:`population_to_dict`.

    Uses ``toolbox.individual`` to create individuals so DEAP's ``creator.Individual``
    type is wired correctly.
    """
    population: list[Any] = []
    for entry in data:
        ind = toolbox.individual()
        # Overwrite the random values with the deserialised ones
        ind[:] = entry["values"]
        if "fitness" in entry:
            if not hasattr(ind, "fitness"):
                from deap import creator

                ind.fitness = creator.FitnessMulti()
            ind.fitness.values = entry["fitness"]["values"]
        population.append(ind)
    return population


def pop_snapshot(
    population: list[Any], generation: int, pareto_indices: list[int], diversity: float
) -> dict[str, Any]:
    """Snapshot an entire population with metadata.

    Returns a dict containing the generation number, population metadata,
    the full serialised population, Pareto-front indices, and diversity metric.
    """
    return {
        "generation": generation,
        "population_size": len(population),
        "pareto_indices": pareto_indices,
        "diversity": diversity,
        "population": population_to_dict(population),
    }


def _sanitize_fitness(fitness: tuple[float, ...]) -> list[float]:
    """Replace NaN/inf with sentinel values for JSON compliance."""
    result: list[float] = []
    for v in fitness:
        if math.isnan(v):
            result.append(0.0)
        elif math.isinf(v):
            result.append(1e6 if v > 0 else -1e6)
        else:
            result.append(v)
    return result


def config_to_dict(config: Any) -> dict[str, Any]:
    """Serialize a dataclass configuration (*GAConfig* / *GenomeConfig* / etc.) to a dict.

    Uses :func:`dataclasses.fields` introspection.  For *GenomeConfig* fields the
    ``param_defs`` are serialised as a list of parameter descriptors.
    """
    from dataclasses import fields, is_dataclass

    result: dict[str, Any] = {}
    if not is_dataclass(config):
        return dict(config.__dict__)

    for f in fields(config):
        # Skip internal / private fields
        if f.name.startswith("_"):
            continue
        val = getattr(config, f.name)
        if f.name == "param_defs":
            # Serialize parameter definitions
            result["param_defs"] = _serialize_param_defs(val)
        elif f.name == "genome_config" and hasattr(val, "param_defs"):
            result["genome_config"] = {
                "n_params": val.n_params,
                "param_defs": _serialize_param_defs(val.param_defs),
            }
        elif isinstance(val, (int, float, str, bool)) or val is None:
            result[f.name] = val
        elif isinstance(val, (list, tuple)):
            result[f.name] = list(val)
        elif isinstance(val, dict):
            result[f.name] = dict(val)
        else:
            # Fallback: convert to string repr for non-trivial types
            result[f.name] = str(val)
    return result


def _serialize_param_defs(param_defs: Sequence[Any]) -> list[dict[str, Any]]:
    """Serialize parameter definitions to JSON-compatible dicts."""
    import dataclasses

    serialized: list[dict[str, Any]] = []
    for p in param_defs:
        if dataclasses.is_dataclass(p):
            entry: dict[str, Any] = {"type": type(p).__name__}
            for df in dataclasses.fields(p):
                v = getattr(p, df.name)
                if isinstance(v, (int, float, str, bool)) or v is None:
                    entry[df.name] = v
                elif isinstance(v, (list, tuple)):
                    entry[df.name] = list(v)
                else:
                    entry[df.name] = str(v)
            serialized.append(entry)
        else:
            serialized.append(
                {
                    "type": type(p).__name__,
                    "name": p.name,
                    **{k: str(v) for k, v in p.__dict__.items()},
                }
            )
    return serialized


def result_to_dict(result: Any) -> dict[str, Any]:
    """Serialize a *GAResult* to a JSON-compatible dict."""
    from genetics.engine import GAResult

    if not isinstance(result, GAResult):
        msg = f"Expected GAResult, got {type(result).__name__}"
        raise TypeError(msg)
    return {
        "config": config_to_dict(result.config),
        "pareto_front": population_to_dict(result.pareto_front),
        "hall_of_fame": population_to_dict(result.hall_of_fame),
        "generations_log": [
            {
                "generation": g.get("generation", idx),
                **{k: v for k, v in g.items() if k != "generation"},
            }
            for idx, g in enumerate(result.generations_log)
        ],
        "timing": round(result.timing, 4),
        "checkpoint_paths": list(result.checkpoint_paths),
        "n_fitness_evaluations": result.n_fitness_evaluations,
    }
