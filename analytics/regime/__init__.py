"""Regime detection — ensemble of 6 detectors with hysteresis voting.

Detects market regimes (bull, bear, choppy, volatile) by combining:
- HMM (hidden Markov model on returns)
- BOCD / PELT changepoint detection
- Volatility clustering (KMeans)
- Cross-instrument correlation
- Macro context (seeded from M8)
"""

from analytics.regime.config import RegimeSettings
from analytics.regime.detector import RegimeDetector
from analytics.regime.detectors import (
    BOCDDetector,
    CorrelationDetector,
    HMMDetector,
    PELTDetector,
    VolClusterDetector,
)
from analytics.regime.ensemble import EnsembleVoter

__all__ = [
    "BOCDDetector",
    "CorrelationDetector",
    "EnsembleVoter",
    "HMMDetector",
    "PELTDetector",
    "RegimeDetector",
    "RegimeSettings",
    "VolClusterDetector",
]
