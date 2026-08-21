"""Lane B composite qualification via ADR-017 (DSR/PBO/CPCV) — BL-OPC-12.

Lane B composite (fundamental screen: Piotroski + Greenblatt +
Lakonishok blend, `analytics/strategy/lane_b_backtester.py`) is the
only positive edge in the project (Sharpe 0.93, alpha +59% vs SPY on
2020→2025, `docs/reports/lane-b-composite/`).  Before it can be
promoted from research to paper trading (BL-OPC-7) the edge must
survive the ADR-017 overfitting gauntlet:

* **DSR ≥ 0.95** — the Deflated Sharpe Ratio must beat 0 after
  correcting for the number of trials actually explored in discovery
  (Bailey & López de Prado 2014);
* **PSR ≥ 0.95** — the Probabilistic Sharpe Ratio must give ≥ 95%
  confidence the true Sharpe is positive;
* **PBO < 0.5** — when a returns matrix of competing variants is
  available, the Probability of Backtest Overfitting (CSCV, Bailey et
  al. 2017) must stay below 0.5.

CPCV (combinatorial purged cross-validation) supplies the honest
out-of-sample Sharpe distribution.

All statistics delegate to `analytics/qualification/dsr.py` (purgedcv
wrappers) and the observed Sharpe to `analytics/metrics/canonical.py`
(ADR-021) — no local re-derivation anywhere in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from analytics.metrics import sharpe_ratio
from analytics.qualification.dsr import (
    combinatorial_purged_cv,
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    probability_of_backtest_overfitting,
)

#: ADR-017 gate thresholds (frozen — changing them requires an ADR
#: amendment, not a code edit).
DSR_MIN: float = 0.95
PSR_MIN: float = 0.95
PBO_MAX: float = 0.5

#: Minimum observations before the gauntlet even runs.
_MIN_RETURNS: int = 60

__all__ = [
    "DSR_MIN",
    "PBO_MAX",
    "PSR_MIN",
    "LaneBQualification",
    "cpcv_oos_sharpes",
    "qualify_lane_b_composite",
]


@dataclass(frozen=True)
class LaneBQualification:
    """ADR-017 qualification report for the Lane B composite edge.

    Attributes
    ----------
    verdict
        ``APPROVED`` | ``REJECTED`` | ``INSUFFICIENT_DATA``.  The edge
        is only promoted toward paper (BL-OPC-7) on APPROVED.
    observed_sharpe
        Canonical annualised Sharpe of the backtest returns (ADR-021).
    deflated_sharpe_ratio
        DSR after the multi-trial correction; ``None`` if not enough
        data to compute it.
    probabilistic_sharpe_ratio
        PSR against a 0.0 benchmark; ``None`` if not enough data.
    pbo
        Probability of Backtest Overfitting when a competing-variant
        returns matrix was supplied; ``None`` otherwise.
    cpcv_oos_sharpe_median
        Median out-of-sample Sharpe across the CPCV paths (honest OOS
        estimate); ``None`` if the series is too short.
    reasons
        Human-readable list of which gate failed (empty on APPROVED).
    n_trials
        Number of discovery trials used for the DSR correction.
    """

    verdict: str
    observed_sharpe: float
    deflated_sharpe_ratio: float | None = None
    probabilistic_sharpe_ratio: float | None = None
    pbo: float | None = None
    cpcv_oos_sharpe_median: float | None = None
    reasons: list[str] = field(default_factory=list)
    n_trials: int = 0


def cpcv_oos_sharpes(
    returns: np.ndarray, *, n_groups: int = 6, n_test_groups: int = 2, periods_per_year: int = 252
) -> list[float]:
    """Out-of-sample Sharpe of each CPCV path (AFML ch.12).

    Each of the ``C(n_groups, n_test_groups)`` combinatorial folds
    yields an OOS Sharpe on its purged test split; the collection is
    the honest OOS distribution of the strategy.  Returns ``[]`` when
    the series is too short to split.
    """
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size < n_groups * 4:
        return []
    # purgedcv requires datetime-like times; daily stamps carry the
    # temporal ordering (purge/embargo default off → spacing is irrelevant).
    times = list(np.arange(clean.size).astype("datetime64[D]"))
    folds = combinatorial_purged_cv(
        prediction_times=times,
        evaluation_times=times,
        n_groups=n_groups,
        n_test_groups=n_test_groups,
    )
    sharpes: list[float] = []
    for _train_idx, test_idx in folds:
        test_returns = clean[test_idx]
        value = sharpe_ratio(test_returns, periods_per_year=periods_per_year)
        if math.isfinite(value):
            sharpes.append(value)
    return sharpes


def qualify_lane_b_composite(
    returns: np.ndarray,
    *,
    n_trials: int,
    periods_per_year: int = 252,
    returns_matrix: np.ndarray | None = None,
    benchmark_sharpe: float = 0.0,
    pbo_n_splits: int = 16,
) -> LaneBQualification:
    """Run the ADR-017 gauntlet on the Lane B composite return stream.

    Parameters
    ----------
    returns
        Periodic (daily) returns of the composite backtest.
    n_trials
        Honest count of strategy variants explored during Lane B
        discovery (config sweep, weight exploration, …).  DSR deflates
        by this number; under-reporting it re-opens the overfitting
        hole this gate exists to close.
    periods_per_year
        Annualization factor matching the return frequency (252 daily).
    returns_matrix
        Optional (n_trials × n_periods) matrix of competing variants'
        returns for the PBO estimate.
    benchmark_sharpe
        PSR benchmark (default 0.0 — "is the edge positive at all").
    pbo_n_splits
        CSCV sub-samples (must divide the matrix width).

    Returns
    -------
    LaneBQualification
        The full gate report (see class docstring).
    """
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size < _MIN_RETURNS:
        return LaneBQualification(
            verdict="INSUFFICIENT_DATA",
            observed_sharpe=0.0,
            reasons=[
                f"only {clean.size} observations (< {_MIN_RETURNS}); the gauntlet needs a "
                "full multi-year daily series"
            ],
            n_trials=n_trials,
        )

    observed = sharpe_ratio(clean, periods_per_year=periods_per_year)
    dsr = deflated_sharpe_ratio(clean, n_trials=n_trials, periods_per_year=periods_per_year)
    psr = probabilistic_sharpe_ratio(clean, benchmark_sharpe=benchmark_sharpe)

    pbo: float | None = None
    if returns_matrix is not None:
        pbo_result = probability_of_backtest_overfitting(returns_matrix, n_splits=pbo_n_splits)
        pbo_value = pbo_result["pbo"]
        pbo = float(pbo_value) if pbo_value is not None else None

    oos_sharpes = cpcv_oos_sharpes(clean, periods_per_year=periods_per_year)
    oos_median = float(np.median(oos_sharpes)) if oos_sharpes else None

    reasons: list[str] = []
    if dsr is None:
        reasons.append("DSR could not be computed (zero variance or too few observations)")
    elif dsr < DSR_MIN:
        reasons.append(
            f"DSR {dsr:.4f} < {DSR_MIN} after correcting for {n_trials} discovery trials"
        )
    if psr is None:
        reasons.append("PSR could not be computed")
    elif psr < PSR_MIN:
        reasons.append(f"PSR {psr:.4f} < {PSR_MIN} (true Sharpe > 0 not established)")
    if pbo is not None and pbo >= PBO_MAX:
        reasons.append(f"PBO {pbo:.4f} >= {PBO_MAX} (in-sample optimum likely OOS-mediocre)")

    verdict = "APPROVED" if not reasons else "REJECTED"
    return LaneBQualification(
        verdict=verdict,
        observed_sharpe=observed,
        deflated_sharpe_ratio=dsr,
        probabilistic_sharpe_ratio=psr,
        pbo=pbo,
        cpcv_oos_sharpe_median=oos_median,
        reasons=reasons,
        n_trials=n_trials,
    )
