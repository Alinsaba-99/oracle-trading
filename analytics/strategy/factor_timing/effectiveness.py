"""Factor effectiveness — Rank IC, ICIR, decay, null benchmark on causal windows.

Port of Inalpha's ``services/factor/.../effectiveness.py`` adapted to Oracle:

  - Polars-free (pandas/numpy only, already in deps).
  - No qlib dependency.
  - Strictly causal: factor at t uses data ≤ t; forward return r[t→t+H] uses
    close[t+H]/close[t] - 1 with the last H bars NaN-dropped.

Used by ``analytics/strategy/factor_timing/`` to rank the 50 alpha factors
(``genetics/alpha/factors.py``) by current predictive power.

Thresholds (kept identical to Inalpha — ADR-0043/0047 lineage):
  - |rank_ic| ≥ 0.02  → direction ≠ 0
  - strength = min(1, |rank_ic| / 0.05)
  - ICIR computed over 5 segments
  - "recent" window = tail 1/3
  - decay stable if |recent| ≥ 0.6 · |full|
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd

_IC_DIRECTION_THRESHOLD = 0.02
_IC_FULL_STRENGTH = 0.05
_ICIR_SEGMENTS = 5
_RECENT_FRACTION = 3
_DECAY_STABLE_RETENTION = 0.6
_EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True, slots=True)
class FactorEffectiveness:
    """Single-factor effectiveness snapshot."""

    value: float | None
    rank_ic: float
    rank_ic_recent: float
    icir: float
    turnover: float
    sample_size: int
    quantile_returns: list[tuple[int, float, int]]  # (q, mean_return, n)
    long_short_return: float
    direction: int  # -1 / 0 / +1
    strength: float  # 0..1
    low_confidence: bool
    decay_state: str  # stable / fading / decaying


def decay_state(rank_ic: float, rank_ic_recent: float) -> str:
    """Three-state decay classification."""
    if rank_ic_recent == 0.0 or np.sign(rank_ic_recent) != np.sign(rank_ic):
        return "decaying"
    if abs(rank_ic_recent) >= _DECAY_STABLE_RETENTION * abs(rank_ic):
        return "stable"
    return "fading"


def _forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """Cumulative forward return over ``horizon`` bars; last ``horizon`` are NaN."""
    return close.shift(-horizon) / close - 1.0


def null_ic_benchmark(n_candidates: int, sample_size: int, horizon: int) -> float:
    """E[max |IC| | pure noise] across N candidates (Bailey–López de Prado asymptotic).

    If the top factor's |rank_ic| is not significantly above this benchmark,
    the apparent edge is likely selection effect across N candidates, not
    signal.  This is a floor, not a hypothesis test — surface it for the
    caller to judge.
    """
    if n_candidates < 1 or sample_size < 1:
        return 0.0
    n_eff = max(4, sample_size // max(1, horizon))
    sigma = 1.0 / np.sqrt(n_eff - 1)
    if n_candidates == 1:
        return float(sigma)
    inv = NormalDist().inv_cdf
    e_max = (1 - _EULER_GAMMA) * inv(1 - 1.0 / n_candidates) + _EULER_GAMMA * inv(
        1 - 1.0 / (n_candidates * np.e)
    )
    return float(sigma * e_max)


def ic_pvalue(ic: float, sample_size: int, horizon: int = 1) -> float:
    """Two-sided p-value for a rank IC (t-approx + large-sample normal)."""
    n_eff = max(4, sample_size // max(1, horizon))
    ic = float(min(0.999999, max(-0.999999, ic)))
    t = abs(ic) * np.sqrt((n_eff - 2) / (1.0 - ic * ic))
    return float(2.0 * (1.0 - NormalDist().cdf(t)))


def bh_adjust(pvalues: list[float]) -> list[float]:
    """Benjamini–Hochberg FDR adjustment (preserves input order)."""
    m = len(pvalues)
    if m == 0:
        return []
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    ranked = p[order] * m / (np.arange(m) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m, dtype=float)
    out[order] = np.clip(ranked, 0.0, 1.0)
    return [float(v) for v in out]


def _rank_ic(factor: pd.Series, fwd: pd.Series) -> tuple[float, int]:
    """Spearman rank correlation between factor and forward return."""
    pair = pd.concat([factor, fwd], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(pair)
    if n < 3:
        return 0.0, n
    fr = pair.iloc[:, 0].rank()
    rr = pair.iloc[:, 1].rank()
    if fr.std(ddof=0) == 0 or rr.std(ddof=0) == 0:
        return 0.0, n
    ic = float(fr.corr(rr))
    if np.isnan(ic):
        return 0.0, n
    return ic, n


def _icir(factor: pd.Series, fwd: pd.Series, segments: int) -> float:
    """Segmented IC mean/std — stability measure."""
    pair = pd.concat([factor, fwd], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(pair) < segments * 3:
        return 0.0
    bounds = np.linspace(0, len(pair), segments + 1, dtype=int)
    ics: list[float] = []
    for i in range(segments):
        ch = pair.iloc[bounds[i] : bounds[i + 1]]
        if len(ch) < 3:
            continue
        fr = ch.iloc[:, 0].rank()
        rr = ch.iloc[:, 1].rank()
        if fr.std(ddof=0) == 0 or rr.std(ddof=0) == 0:
            continue
        ic = fr.corr(rr)
        if not np.isnan(ic):
            ics.append(float(ic))
    if len(ics) < 2:
        return 0.0
    arr = np.array(ics)
    sd = arr.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(arr.mean() / sd)


def _recent_rank_ic(factor: pd.Series, fwd: pd.Series) -> float:
    """Rank IC on the tail 1/3 of the sample (decay detection)."""
    pair = pd.concat([factor, fwd], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    tail = len(pair) // _RECENT_FRACTION
    if tail < 3:
        return 0.0
    ch = pair.iloc[-tail:]
    fr = ch.iloc[:, 0].rank()
    rr = ch.iloc[:, 1].rank()
    if fr.std(ddof=0) == 0 or rr.std(ddof=0) == 0:
        return 0.0
    ic = float(fr.corr(rr))
    return 0.0 if np.isnan(ic) else ic


def _turnover(factor: pd.Series) -> float:
    """1 - spearman(rank(f_t), rank(f_{t-1})) — signal reversal rate."""
    f = factor.replace([np.inf, -np.inf], np.nan)
    pair = pd.concat([f.rename("cur"), f.shift(1).rename("prev")], axis=1).dropna()
    if len(pair) < 3:
        return 0.0
    fr, pr = pair["cur"].rank(), pair["prev"].rank()
    if fr.std(ddof=0) == 0 or pr.std(ddof=0) == 0:
        return 0.0
    ac = fr.corr(pr)
    if np.isnan(ac):
        return 0.0
    return float(min(1.0, max(0.0, 1.0 - ac)))


def _quantile_returns(
    factor: pd.Series, fwd: pd.Series, quantiles: int
) -> tuple[list[tuple[int, float, int]], float]:
    """Per-quantile forward return mean + (top - bottom) long-short spread."""
    pair = pd.concat([factor.rename("f"), fwd.rename("r")], axis=1)
    pair = pair.replace([np.inf, -np.inf], np.nan).dropna()
    if len(pair) < quantiles * 3:
        return [], 0.0
    try:
        labels = pd.qcut(pair["f"], quantiles, labels=False, duplicates="drop")
    except (ValueError, IndexError):
        return [], 0.0
    pair = pair.assign(q=labels)
    stats: list[tuple[int, float, int]] = []
    grp = pair.groupby("q")["r"]
    for q, sub in grp:
        stats.append((int(q), float(sub.mean()), len(sub)))
    if not stats:
        return [], 0.0
    stats.sort(key=lambda t: t[0])
    long_short = stats[-1][1] - stats[0][1]
    return stats, float(long_short)


def score_factor(
    factor: pd.Series, close: pd.Series, *, horizon: int, quantiles: int = 5, min_samples: int = 60
) -> FactorEffectiveness:
    """Score one factor against forward returns.

    Args:
        factor: factor time series (same index as ``close``, warmup NaN ok).
        close: close price series.
        horizon: forward-return window in bars.
        quantiles: quantile bucket count for spread analysis.
        min_samples: below this, mark ``low_confidence=True``.
    """
    fwd = _forward_return(close, horizon)
    rank_ic, n = _rank_ic(factor, fwd)
    rank_ic_recent = _recent_rank_ic(factor, fwd)
    icir = _icir(factor, fwd, _ICIR_SEGMENTS)
    turnover = _turnover(factor)
    qstats, long_short = _quantile_returns(factor, fwd, quantiles)

    low_conf = n < min_samples
    direction = 0
    if not low_conf and abs(rank_ic) >= _IC_DIRECTION_THRESHOLD:
        direction = 1 if rank_ic > 0 else -1
    strength = float(min(1.0, abs(rank_ic) / _IC_FULL_STRENGTH))

    valid = factor.replace([np.inf, -np.inf], np.nan).dropna()
    value = float(valid.iloc[-1]) if len(valid) else None

    return FactorEffectiveness(
        value=value,
        rank_ic=rank_ic,
        rank_ic_recent=rank_ic_recent,
        icir=icir,
        turnover=turnover,
        sample_size=n,
        quantile_returns=qstats,
        long_short_return=long_short,
        direction=direction,
        strength=strength,
        low_confidence=low_conf,
        decay_state=decay_state(rank_ic, rank_ic_recent),
    )


__all__ = [
    "FactorEffectiveness",
    "bh_adjust",
    "decay_state",
    "ic_pvalue",
    "null_ic_benchmark",
    "score_factor",
]
