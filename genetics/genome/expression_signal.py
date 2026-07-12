"""ExpressionGenomeToSignal — BacktestSignal for GP-evolved expression alpha.

Bridges the expression-based alpha system with the GA pipeline:
an expression string is stored in the genome, parsed into an ExprNode
AST, and evaluated using the operator library.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import polars as pl

from genetics.genome.parameters import GenomeParameter
from genetics.genome.signal import Genome


class ExpressionGenomeToSignal:
    """BacktestSignal powered by GP-evolved expression trees.

    The genome carries a single ``expression`` parameter (string) that
    is parsed and evaluated on market data.

    GA-optimisable parameters (future):
        expression: str — the alpha factor expression
            (evolved by DEAP GP or hand-crafted)
    """

    def __init__(
        self,
        genome: Genome,
        param_defs: Sequence[GenomeParameter],  # noqa: ARG002
    ) -> None:
        from genetics.genome.signal import decode

        raw = decode(genome)
        self._expr_str = str(raw.get("expression", "0"))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute expression on market data."""
        n = len(data)
        if n < 10:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        try:
            from genetics.alpha.expression import evaluate, parse_expression
            from genetics.alpha.operators import OPERATORS_MAP

            node = parse_expression(self._expr_str)
            result = evaluate(node, data, OPERATORS_MAP)

            # Threshold to -1, 0, 1
            threshold = 0.0
            signal = np.zeros(n, dtype=np.int8)
            signal[result > threshold] = 1
            signal[result < -threshold] = -1

            return pl.Series("signal", signal, dtype=pl.Int8)
        except Exception:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)


def encode_expression(expr_str: str, genome_len: int = 1) -> Genome:  # noqa: ARG001 -> Genome:
    """Encode an expression string into a Genome suitable for GA.

    Uses a hash of the string to create a seed genome with known params.
    """
    from genetics.genome.parameters import CategoricalParameter
    from genetics.genome.signal import encode

    # Store the expression as a categorical parameter
    raw = {"expression": expr_str}
    param_defs = [CategoricalParameter("expression", categories=[expr_str])]
    return encode(raw, param_defs)
