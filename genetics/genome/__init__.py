"""Genome module — typed parameters, codec, and signal adapter for genetic optimisation."""

from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    GenomeParameter,
    IntParameter,
)
from genetics.genome.hybrid_signal import HybridGenomeToSignal
from genetics.genome.protocol import BacktestSignal
from genetics.genome.signal import (
    Genome,
    GenomeConfig,
    GenomeToSignal,
    decode,
    encode,
    validate_genome,
)

__all__ = [
    "BacktestSignal",
    "CategoricalParameter",
    "ContinuousParameter",
    "Genome",
    "GenomeConfig",
    "GenomeParameter",
    "GenomeToSignal",
    "HybridGenomeToSignal",
    "IntParameter",
    "decode",
    "encode",
    "validate_genome",
]
