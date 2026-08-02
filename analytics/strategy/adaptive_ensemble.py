"""Adaptive ensemble — regime-conditional specialist weights per asset.

Dynamically adjusts specialist weights based on the current regime
classification AND the asset being traded.  Weights are pre-calibrated
from the multi-asset sweep results (docs/SWEEP_ROOT_CAUSE_ANALYSIS.md).

Supports two regime detectors:
  1. SMA heuristic (default, deterministic) — ``_sma_regime_heuristic``
  2. PyTorch MLP classifier (8 regimes) — ``RegimeClassifier`` (Kairos-v2)

Usage::

    from analytics.strategy.adaptive_ensemble import AdaptiveEnsemble

    ensemble = AdaptiveEnsemble("ES", "1d")
    ensemble.compute(df)       # returns combined signal
    info = ensemble.get_info() # regime, weights, routing
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from analytics.strategy.regime_ensemble import (
    RegimeAwareEnsemble,
    RegimeLabel,
    RoutingDecision,
    SpecialistId,
)
from analytics.strategy.weight_evolver import WeightEvolver

# ── Regime mapping: 8 Kairos-v2 regimes -> 4 Oracle RegimeLabel ──────

_KAIROS_TO_ORACLE: dict[str, RegimeLabel] = {
    "Dong_Bang": RegimeLabel.UNKNOWN,
    "Nen_Chat": RegimeLabel.CHOPPY,  # Compression -> choppy
    "Dau_XH": RegimeLabel.BULL,  # Start uptrend -> bull
    "XH_Manh": RegimeLabel.BULL,  # Strong uptrend -> bull
    "Cao_Trao": RegimeLabel.VOLATILE,  # Climax -> volatile
    "Hoi_Quy": RegimeLabel.BEAR,  # Retracement -> bear
    "Nhieu_Dong": RegimeLabel.CHOPPY,  # Noisy -> choppy
    "Quet_TK": RegimeLabel.UNKNOWN,  # Stop hunting -> unknown
}

# ── Weight matrix ─────────────────────────────────────────────────────

# Pre-calibrated weights from 19-asset sweep (see SWEEP_ROOT_CAUSE_ANALYSIS.md)

_WEIGHT_MATRIX: dict[tuple[str, str], dict[RegimeLabel, dict[SpecialistId, float]]] = {
    ("ES", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 1.0},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.8, SpecialistId.BREAKOUT: 0.2},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.6,
            SpecialistId.BREAKOUT: 0.3,
            SpecialistId.TREND: 0.1,
        },
        RegimeLabel.VOLATILE: {
            SpecialistId.BREAKOUT: 0.5,
            SpecialistId.MEAN_REVERSION: 0.3,
            SpecialistId.TREND: 0.2,
        },
    },
    ("ES", "1h"): {
        RegimeLabel.BULL: {SpecialistId.MEAN_REVERSION: 0.7, SpecialistId.TREND: 0.3},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.7, SpecialistId.BREAKOUT: 0.3},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.6,
            SpecialistId.BREAKOUT: 0.2,
            SpecialistId.TREND: 0.2,
        },
        RegimeLabel.VOLATILE: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.BREAKOUT: 0.4},
    },
    ("NQ", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 1.0},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.BREAKOUT: 0.4},
        RegimeLabel.CHOPPY: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.TREND: 0.4},
        RegimeLabel.VOLATILE: {SpecialistId.BREAKOUT: 0.5, SpecialistId.MEAN_REVERSION: 0.5},
    },
    ("SPY", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 1.0},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.BREAKOUT: 0.4},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.5,
            SpecialistId.BREAKOUT: 0.3,
            SpecialistId.TREND: 0.2,
        },
        RegimeLabel.VOLATILE: {SpecialistId.BREAKOUT: 0.6, SpecialistId.MEAN_REVERSION: 0.4},
    },
    ("QQQ", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 1.0},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.BREAKOUT: 0.4},
        RegimeLabel.CHOPPY: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.TREND: 0.4},
        RegimeLabel.VOLATILE: {SpecialistId.BREAKOUT: 0.6, SpecialistId.MEAN_REVERSION: 0.4},
    },
    ("IWM", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 1.0},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.7, SpecialistId.BREAKOUT: 0.3},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.6,
            SpecialistId.TREND: 0.2,
            SpecialistId.BREAKOUT: 0.2,
        },
        RegimeLabel.VOLATILE: {SpecialistId.BREAKOUT: 0.5, SpecialistId.MEAN_REVERSION: 0.5},
    },
    ("GC", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 0.6, SpecialistId.MEAN_REVERSION: 0.4},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 1.0},  # BEST: Sharpe +5.84
        RegimeLabel.CHOPPY: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.TREND: 0.4},
        RegimeLabel.VOLATILE: {SpecialistId.MEAN_REVERSION: 0.5, SpecialistId.BREAKOUT: 0.5},
    },
    ("CL", "1h"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 0.6, SpecialistId.MEAN_REVERSION: 0.4},
        RegimeLabel.BEAR: {SpecialistId.BREAKOUT: 0.5, SpecialistId.MEAN_REVERSION: 0.5},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.5,
            SpecialistId.TREND: 0.3,
            SpecialistId.BREAKOUT: 0.2,
        },
        RegimeLabel.VOLATILE: {
            SpecialistId.BREAKOUT: 0.5,
            SpecialistId.MEAN_REVERSION: 0.3,
            SpecialistId.TREND: 0.2,
        },
    },
    ("EURUSD", "1d"): {
        RegimeLabel.BULL: {SpecialistId.MEAN_REVERSION: 0.5, SpecialistId.TREND: 0.5},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.8, SpecialistId.BREAKOUT: 0.2},
        RegimeLabel.CHOPPY: {SpecialistId.MEAN_REVERSION: 1.0},
        RegimeLabel.VOLATILE: {SpecialistId.MEAN_REVERSION: 0.6, SpecialistId.BREAKOUT: 0.4},
    },
    ("BTCUSDT", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 0.5, SpecialistId.MEAN_REVERSION: 0.5},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.5, SpecialistId.BREAKOUT: 0.5},
        RegimeLabel.CHOPPY: {
            SpecialistId.MEAN_REVERSION: 0.5,
            SpecialistId.BREAKOUT: 0.3,
            SpecialistId.TREND: 0.2,
        },
        RegimeLabel.VOLATILE: {
            SpecialistId.BREAKOUT: 0.5,
            SpecialistId.MEAN_REVERSION: 0.3,
            SpecialistId.TREND: 0.2,
        },
    },
    ("BNBUSDT", "1d"): {
        RegimeLabel.BULL: {SpecialistId.TREND: 0.5, SpecialistId.MEAN_REVERSION: 0.5},
        RegimeLabel.BEAR: {SpecialistId.MEAN_REVERSION: 0.5, SpecialistId.BREAKOUT: 0.5},
        RegimeLabel.CHOPPY: {SpecialistId.MEAN_REVERSION: 1.0},
        RegimeLabel.VOLATILE: {SpecialistId.BREAKOUT: 0.6, SpecialistId.MEAN_REVERSION: 0.4},
    },
}


@dataclass
class AdaptiveResult:
    """Result from one compute() call on AdaptiveEnsemble."""

    signal: np.ndarray
    regime: RegimeLabel
    routing: RoutingDecision
    weights: dict[SpecialistId, float] = field(default_factory=dict)


# ── Class-level ML classifier cache ────────────────────────────────

_ML_CLF_CACHE: object | None = None
"""Cached RegimeClassifier instance (loaded once, reused across all AdaptiveEnsemble instances)."""

# ── Adaptive Ensemble ───────────────────────────────────────────────


class AdaptiveEnsemble:
    """Regime-conditional ensemble with pre-calibrated weights per asset.

    Extends RegimeAwareEnsemble with dynamic weight assignment based
    on the asset's sweep-calibrated optimal response to each regime.

    Args:
        asset: Trading symbol (e.g. "ES").
        timeframe: Bar timeframe (e.g. "1d", "1h").
    """

    def __init__(self, asset: str, timeframe: str) -> None:
        self._asset = asset.upper()
        self._tf = timeframe
        from analytics.strategy.lorentzian import LorentzianKNN
        from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion

        self._ensemble = RegimeAwareEnsemble(
            specialists={
                SpecialistId.TREND: EmaTrend(fast=10, slow=30),
                SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
                SpecialistId.BREAKOUT: DonchianBreakout(period=20),
                SpecialistId.LORENTZIAN: LorentzianKNN(
                    k=4, lookahead=4, max_bars_back=80, feature_count=3
                ),
            }
        )
        self._weights: dict[SpecialistId, float] = {}
        self._regime: RegimeLabel = RegimeLabel.CHOPPY
        self._routing: RoutingDecision | None = None
        self._evolver = WeightEvolver(window=50)
        self._ml_classifier = self._load_ml_classifier_cached()

    @staticmethod
    def _load_ml_classifier_cached() -> object | None:
        """Load ML classifier once, cache at module level."""
        global _ML_CLF_CACHE
        if _ML_CLF_CACHE is None:
            _ML_CLF_CACHE = AdaptiveEnsemble._try_load_ml_classifier_static()
        return _ML_CLF_CACHE

    @staticmethod
    def _try_load_ml_classifier_static() -> object | None:
        """Try to load PyTorch regime classifier (Kairos-v2). Returns None if unavailable."""
        # First try the 72-dim multi-TF model (36.5% accuracy)
        for model_dir, input_dim, prefix in [
            ("models/regime_72d", 72, "72-dim"),
            ("models/regime", 18, "18-dim"),
        ]:
            try:
                from analytics.regime.ml_classifier import RegimeClassifier

                clf = RegimeClassifier(model_dir=model_dir)
                clf.load_or_init(input_dim=input_dim)
                if clf.model is not None:
                    import torch

                    dummy = torch.randn(1, input_dim)
                    _ = clf.model(dummy)
                    if model_dir == "models/regime_72d":
                        print(f"  AdaptiveEnsemble: loaded 72-dim classifier ({prefix})")
                    return clf
            except Exception:
                continue
        return None

    def _try_load_ml_classifier(self) -> object | None:
        """Legacy per-instance loader (delegates to static)."""
        return self._load_ml_classifier_cached()

    def _detect_regime_ml(self, data: pl.DataFrame) -> RegimeLabel:
        """Detect regime using PyTorch ML classifier (8 regimes from Kairos-v2)."""
        if self._ml_classifier is None:
            return RegimeLabel.CHOPPY
        try:
            kairos_regime, confidence = self._ml_classifier.predict(data)  # type: ignore[attr-defined]
            mapped = _KAIROS_TO_ORACLE.get(kairos_regime, RegimeLabel.CHOPPY)
            if confidence < 0.3:
                return RegimeLabel.CHOPPY
            return mapped
        except Exception:
            return RegimeLabel.CHOPPY

    def set_factor_weights(self, weights: dict[str, float]) -> None:
        """Override ensemble weights with GA-evolved DNA factor weights.

        Maps individual factor names to SpecialistId weights.
        """
        from analytics.strategy.regime_ensemble import SpecialistId

        specialist_map: dict[str, SpecialistId] = {
            "ema_trend": SpecialistId.TREND,
            "rsi_rev": SpecialistId.MEAN_REVERSION,
            "donchian_breakout": SpecialistId.BREAKOUT,
            "bband_rev": SpecialistId.MEAN_REVERSION,
            "roc_momentum": SpecialistId.TREND,
            "zscore_rev": SpecialistId.MEAN_REVERSION,
            "keltner_rev": SpecialistId.MEAN_REVERSION,
            "alpha_003": SpecialistId.MEAN_REVERSION,
            "alpha_020": SpecialistId.MEAN_REVERSION,
            "alpha_044": SpecialistId.MEAN_REVERSION,
            "alpha_050": SpecialistId.MEAN_REVERSION,
            "alpha_063": SpecialistId.MEAN_REVERSION,
            "trend": SpecialistId.TREND,
            "mean_rev": SpecialistId.MEAN_REVERSION,
            "breakout": SpecialistId.BREAKOUT,
            "lorentzian": SpecialistId.LORENTZIAN,
        }
        new_weights: dict[SpecialistId, float] = {}
        for name, w in weights.items():
            sid = specialist_map.get(name)
            if sid is not None:
                new_weights[sid] = new_weights.get(sid, 0) + w
        w_total = sum(new_weights.values())
        if w_total > 0:
            self._weights = {k: v / w_total for k, v in new_weights.items()}

    def _get_weights(self, regime: RegimeLabel) -> dict[SpecialistId, float]:
        """Get pre-calibrated or evolved weights for (asset×tf, regime)."""
        evolved = self._evolver.get_weights(self._asset, self._tf, regime)
        if evolved != dict.fromkeys(SpecialistId, 1.0 / 4):
            # Evolved weights have meaningful data
            return evolved
        return self._static_weights(regime)

    def _static_weights(self, regime: RegimeLabel) -> dict[SpecialistId, float]:
        """Get pre-calibrated weights for current (asset x tf, regime)."""
        key = (self._asset, self._tf)
        fallback: dict[RegimeLabel, dict[SpecialistId, float]] = {
            RegimeLabel.BULL: {
                SpecialistId.TREND: 0.5,
                SpecialistId.MEAN_REVERSION: 0.3,
                SpecialistId.BREAKOUT: 0.2,
            },
            RegimeLabel.BEAR: {
                SpecialistId.MEAN_REVERSION: 0.5,
                SpecialistId.TREND: 0.3,
                SpecialistId.BREAKOUT: 0.2,
            },
            RegimeLabel.CHOPPY: {
                SpecialistId.MEAN_REVERSION: 0.5,
                SpecialistId.TREND: 0.3,
                SpecialistId.BREAKOUT: 0.2,
            },
            RegimeLabel.VOLATILE: {
                SpecialistId.BREAKOUT: 0.4,
                SpecialistId.MEAN_REVERSION: 0.3,
                SpecialistId.TREND: 0.3,
            },
        }
        matrix = _WEIGHT_MATRIX.get(key, fallback)
        return matrix.get(regime, fallback[regime])

    def compute(self, data: pl.DataFrame) -> np.ndarray:
        """Compute combined signal with regime-conditional weights.

        Args:
            data: OHLCV DataFrame with close column.

        Returns:
            Combined signal array (-1, 0, 1 weighted per specialist).
        """
        # Get base ensemble signals + regime
        base = self._ensemble.compute(data)
        base_signal = base.to_numpy() if hasattr(base, "to_numpy") else np.asarray(base)

        # Detect regime: ML classifier (8 regimes) or fallback to SMA heuristic
        ml_regime = self._detect_regime_ml(data)
        if ml_regime != RegimeLabel.CHOPPY or self._ml_classifier is None:
            self._regime = ml_regime
        else:
            # Fallback to SMA heuristic from ensemble
            self._routing = self._ensemble.route(data)
            self._regime = self._routing.regime

        if self._routing is None:
            self._routing = RoutingDecision(
                regime=self._regime,
                regime_confidence=0.5,
                specialist=SpecialistId.MEAN_REVERSION,
                reason="adaptive",
            )

        # Get weights for this (asset, tf, regime)
        self._weights = self._get_weights(self._regime)

        if len(self._weights) <= 1:
            return base_signal.astype(np.int8)

        return self._weighted_combine(data)

    def _weighted_combine(self, data: pl.DataFrame) -> np.ndarray:
        """Compute weighted combination of all specialist signals."""
        signals: list[np.ndarray] = []
        total_weight = sum(self._weights.values())

        for spec_id, weight in self._weights.items():
            if weight <= 0:
                continue
            spec_signal = self._ensemble.compute_specialist(data, spec_id)
            signals.append(spec_signal.to_numpy().astype(float) * weight / total_weight)

        if not signals:
            return np.zeros(len(data))

        combined = np.zeros(len(data))
        for sig in signals:
            combined += sig

        return np.sign(combined).astype(np.int8)

    def route(self, data: pl.DataFrame) -> RoutingDecision:
        """Re-route based on current state; identical to RegimeAwareEnsemble."""
        if self._routing is None:
            self.compute(data)
        return self._routing  # type: ignore[return-value]

    def get_info(self) -> AdaptiveResult:
        """Return structured result with weights, regime, and routing."""
        return AdaptiveResult(
            signal=np.array([]),
            regime=self._regime,
            routing=self._routing
            or RoutingDecision(
                specialist=SpecialistId.MEAN_REVERSION,
                regime=RegimeLabel.CHOPPY,
                regime_confidence=0.0,
                reason="default",
            ),
            weights=self._weights,
        )

    def record_performance(
        self, specialist: SpecialistId, regime: RegimeLabel, sharpe: float
    ) -> None:
        """Record a realised Sharpe to evolve weights over time.

        Call after each session or fold to feed the WeightEvolver.
        Over time, the ensemble weights shift toward the best-performing
        specialist for each (asset, tf, regime) combination.
        """
        self._evolver.update(
            asset=self._asset,
            timeframe=self._tf,
            specialist=specialist,
            regime=regime,
            sharpe=sharpe,
        )


__all__ = ["AdaptiveEnsemble", "AdaptiveResult"]
