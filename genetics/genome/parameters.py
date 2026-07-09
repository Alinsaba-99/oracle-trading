"""Typed parameter taxonomy for genetic algorithm genomes.

Provides parameter types with bounds, scaling, and mutation configuration.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "CategoricalParameter",
    "ContinuousParameter",
    "GenomeParameter",
    "IntParameter",
]

type GenomeParameter = ContinuousParameter | IntParameter | CategoricalParameter


class ContinuousParameter:
    """A continuous-valued parameter with float bounds.

    Attributes:
        name: Parameter identifier.
        low: Minimum value (inclusive).
        high: Maximum value (inclusive).
        init_range: (low, high) fraction of [low, high] used for random init.
        scaling: Linear or logarithmic scaling.
        mutation_step_size: Step size for Gaussian mutation; None for auto.
    """

    def __init__(
        self,
        name: str,
        low: float,
        high: float,
        init_range: tuple[float, float] = (0.0, 1.0),
        scaling: Literal["linear", "log"] = "linear",
        mutation_step_size: float | None = None,
    ) -> None:
        if scaling == "log" and low <= 0:
            msg = f"Log scaling requires low > 0, got low={low} for {name!r}"
            raise ValueError(msg)
        if not (0.0 <= init_range[0] <= 1.0 and 0.0 <= init_range[1] <= 1.0):
            msg = f"init_range values must be in [0, 1], got {init_range}"
            raise ValueError(msg)
        if low >= high:
            msg = f"low ({low}) must be < high ({high}) for {name!r}"
            raise ValueError(msg)

        self.name = name
        self.low = low
        self.high = high
        self.init_range = init_range
        self.scaling = scaling
        self.mutation_step_size = mutation_step_size

    def __repr__(self) -> str:
        return f"ContinuousParameter(name={self.name!r}, low={self.low}, high={self.high})"


class IntParameter:
    """An integer-valued parameter with inclusive bounds.

    Attributes:
        name: Parameter identifier.
        low: Minimum value (inclusive).
        high: Maximum value (inclusive).
        init_range: (low, high) fraction of [low, high] used for random init.
        scaling: Linear or logarithmic scaling.
        mutation_step_size: Step size for integer mutation; None for auto.
    """

    def __init__(
        self,
        name: str,
        low: int,
        high: int,
        init_range: tuple[int, int] = (0, 1),
        scaling: Literal["linear", "log"] = "linear",
        mutation_step_size: int | None = None,
    ) -> None:
        if scaling == "log" and low <= 0:
            msg = f"Log scaling requires low > 0, got low={low} for {name!r}"
            raise ValueError(msg)
        if not (0 <= init_range[0] <= 1 and 0 <= init_range[1] <= 1):
            msg = f"init_range values must be in [0, 1], got {init_range}"
            raise ValueError(msg)
        if low >= high:
            msg = f"low ({low}) must be < high ({high}) for {name!r}"
            raise ValueError(msg)

        self.name = name
        self.low = low
        self.high = high
        self.init_range = init_range
        self.scaling = scaling
        self.mutation_step_size = mutation_step_size

    def __repr__(self) -> str:
        return f"IntParameter(name={self.name!r}, low={self.low}, high={self.high})"


class CategoricalParameter:
    """A categorical parameter with discrete choices.

    Attributes:
        name: Parameter identifier.
        categories: Allowed category labels.
        weights: Optional sampling weights (same length as categories).
    """

    def __init__(
        self,
        name: str,
        categories: list[str],
        weights: list[float] | None = None,
    ) -> None:
        if not categories:
            msg = f"Categories must be non-empty for {name!r}"
            raise ValueError(msg)
        if weights is not None and len(weights) != len(categories):
            msg = (
                f"Weights length ({len(weights)}) must match categories "
                f"({len(categories)}) for {name!r}"
            )
            raise ValueError(msg)

        self.name = name
        self.categories = categories
        self.weights = weights

    def __repr__(self) -> str:
        return f"CategoricalParameter(name={self.name!r}, categories={self.categories})"
