"""HybridGenomeToSignal — KNN + Alpha Factors + Heikin Ashi."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import polars as pl

    from genetics.genome.parameters import GenomeParameter
    from genetics.genome.signal import Genome


class HybridGenomeToSignal:
    """Combines KNN Lorentziano + 50 Alpha Factors + Heikin Ashi preprocessing.

    Flow:
        1. Heikin Ashi conversion on input OHLCV
        2. KNN signal on HA features (RSI/CCI/ADX/WaveTrend/Momentum)
        3. Alpha factor signal on HA data (50 factors, 8 categories)
        4. Weighted combination with conflict resolution

    26 GA-optimisable parameters (15 KNN + 9 alpha + 2 hybrid weights).
    Individual signal weights capped at 0.8 to force cooperation.
    On conflict (KNN and Alpha disagree): signal = 0 (neutral).
    """

    def __init__(self, genome: Genome, param_defs: Sequence[GenomeParameter]) -> None:
        from genetics.genome.signal import decode

        self._raw = decode(genome)
        self._param_defs = param_defs

    def compute(self, data: pl.DataFrame) -> pl.Series:
        import polars as pl

        from genetics.genome.knn_signal import KNNGenomeToSignal
        from genetics.genome.signal import AlphaGenomeToSignal
        from genetics.signal.heikin_ashi import to_heikin_ashi

        n = len(data)
        if n == 0:
            return pl.Series("signal", [], dtype=pl.Int8)

        # 1. Heikin Ashi preprocessing
        ha_data = to_heikin_ashi(data)

        # 2. KNN signal — map hybrid params to KNN names
        knn_raw = {
            "k_neighbors": self._raw.get("knn_k", 8),
            "train_length": self._raw.get("knn_train_len", 4),
            "threshold": self._raw.get("knn_threshold", 0.5),
            "class_weight": self._raw.get("knn_class_weight", 1.0),
            "rsi_period": self._raw.get("knn_rsi_period", 14),
            "cci_period": self._raw.get("knn_cci_period", 20),
            "adx_period": self._raw.get("knn_adx_period", 14),
            "wt_channel": self._raw.get("knn_wt_channel", 10),
            "wt_avg": self._raw.get("knn_wt_avg", 11),
            "mom_period": self._raw.get("knn_mom_period", 12),
            "w_rsi": self._raw.get("knn_w_rsi", 1.0),
            "w_cci": self._raw.get("knn_w_cci", 1.0),
            "w_adx": self._raw.get("knn_w_adx", 1.0),
            "w_wt": self._raw.get("knn_w_wt", 1.0),
            "w_mom": self._raw.get("knn_w_mom", 1.0),
        }
        knn_obj = KNNGenomeToSignal.__new__(KNNGenomeToSignal)
        knn_obj._raw = knn_raw
        knn_sig = knn_obj.compute(ha_data)

        # 3. Alpha signal — map hybrid params to Alpha names
        alpha_raw = {
            "mom_weight": self._raw.get("alpha_ret_w", 1.0),
            "mr_weight": self._raw.get("alpha_mom_w", 1.0),
            "vol_weight": self._raw.get("alpha_vol_w", 1.0),
            "corr_weight": self._raw.get("alpha_corr_w", 1.0),
            "volu_weight": self._raw.get("alpha_volu_w", 1.0),
            "seas_weight": self._raw.get("alpha_seas_w", 1.0),
            "fund_weight": self._raw.get("alpha_fund_w", 1.0),
            "micr_weight": self._raw.get("alpha_micr_w", 1.0),
            "threshold": self._raw.get("alpha_threshold", 0.2),
        }
        alpha_obj = AlphaGenomeToSignal.__new__(AlphaGenomeToSignal)
        alpha_obj._raw_params = alpha_raw
        alpha_sig = alpha_obj.compute(ha_data)

        # 4. Weights from genome (capped at 0.8)
        knn_w = min(float(self._raw.get("hybrid_knn_w", 0.5)), 0.8)
        alpha_w = min(float(self._raw.get("hybrid_alpha_w", 0.5)), 0.8)
        total_w = knn_w + alpha_w
        if total_w == 0:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        # 5. Weighted combination with conflict resolution
        knn_arr = knn_sig.to_numpy()
        alpha_arr = alpha_sig.to_numpy()
        combined = np.zeros(n, dtype=np.float64)

        # Both agree: weighted signal
        both_positive = (knn_arr == 1) & (alpha_arr == 1)
        both_negative = (knn_arr == -1) & (alpha_arr == -1)
        combined[both_positive] = (knn_w + alpha_w) / total_w
        combined[both_negative] = -(knn_w + alpha_w) / total_w

        # Only one active: scaled weight
        knn_only_long = (knn_arr == 1) & (alpha_arr == 0)
        knn_only_short = (knn_arr == -1) & (alpha_arr == 0)
        alpha_only_long = (alpha_arr == 1) & (knn_arr == 0)
        alpha_only_short = (alpha_arr == -1) & (knn_arr == 0)

        combined[knn_only_long] = knn_w / total_w
        combined[knn_only_short] = -knn_w / total_w
        combined[alpha_only_long] = alpha_w / total_w
        combined[alpha_only_short] = -alpha_w / total_w

        # On conflict (opposite directions): neutral = 0 (already 0 by default)

        # Threshold to -1, 0, 1
        result = np.zeros(n, dtype=np.int8)
        result[combined > 0.3] = 1
        result[combined < -0.3] = -1

        return pl.Series("signal", result, dtype=pl.Int8)
