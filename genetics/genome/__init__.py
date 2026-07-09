"""Genome module — typed parameters, codec, and signal adapter for genetic optimisation."""

from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    GenomeParameter,
    IntParameter,
)
from genetics.genome.signal import (
    Genome,
    GenomeConfig,
    GenomeToSignal,
    decode,
    encode,
    validate_genome,
)

__all__ = [
    "CategoricalParameter",
    "ContinuousParameter",
    "Genome",
    "GenomeConfig",
    "GenomeParameter",
    "GenomeToSignal",
    "IntParameter",
    "decode",
    "encode",
    "validate_genome",
]
