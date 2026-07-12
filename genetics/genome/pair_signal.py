"""PairTradingSignal — mean-reverting spread trading."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import polars as pl
from analytics.technical.pair_trading import compute_cointegration
from genetics.genome.parameters import GenomeParameter
from genetics.genome.signal import Genome


class PairTradingSignal:
    """BacktestSignal for mean-reverting pair trading.

    GA-optimisable parameters:
        entry_threshold (1.0-3.0): z-score entry level
        exit_threshold (0.0-1.5): z-score exit level
        window (10-100): rolling window for z-score calculation
    """

    def __init__(self, genome: Genome, _param_defs: Sequence[GenomeParameter]) -> None:
        from genetics.genome.signal import decode

        raw = decode(genome)
        self._entry = max(0.5, min(5.0, float(raw.get("entry_threshold", 2.0))))
        self._exit = max(0.0, min(2.0, float(raw.get("exit_threshold", 0.5))))
        self._spread: pl.Series | None = None

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute pair trading signal from an already-computed spread.

        The input DataFrame must have a 'spread' column (pre-computed
        via build_pair_df or compute_cointegration).

        If 'close_a' and 'close_b' columns are present, the spread
        is computed on the fly.
        """
        if "spread" in data.columns:
            spread = data["spread"]
        elif "close_a" in data.columns and "close_b" in data.columns:
            result = compute_cointegration(data["close_a"], data["close_b"])
            spread = result.spread
        else:
            # Single-asset mode: use the close price as 'spread'
            # (degenerate case for testing)
            spread = data["close"] if "close" in data.columns else pl.Series([0.0] * len(data))

        self._spread = spread

        # Compute signal with expanding z-score (no lookahead)
        arr = spread.to_numpy()
        n = len(arr)
        signal = np.zeros(n, dtype=np.int8)
        z = np.zeros(n)

        for i in range(1, n):
            prefix = arr[: i + 1]
            mean = float(np.nanmean(prefix))
            std = float(np.nanstd(prefix))
            if std > 1e-10:
                z[i] = (float(arr[i]) - mean) / std

        in_pos = 0
        for i in range(1, n):
            if in_pos == 0:
                if z[i] > self._entry:
                    signal[i] = -1
                    in_pos = -1
                elif z[i] < -self._entry:
                    signal[i] = 1
                    in_pos = 1
            elif in_pos == 1:
                if z[i] > -self._exit:
                    signal[i] = 0
                    in_pos = 0
                else:
                    signal[i] = 1
            elif in_pos == -1:
                if z[i] < self._exit:
                    signal[i] = 0
                    in_pos = 0
                else:
                    signal[i] = -1

        return pl.Series("signal", signal, dtype=pl.Int8)
