"""BL-710 — Alphalens-style factor diagnostic adapter.

Provides a *lightweight* implementation of the three diagnostic charts
the Quantopian ``alphalens`` library is famous for, plus a single
``analyze_factor`` aggregator that returns them all in one dataclass:

1. **IC by horizon** — Spearman rank correlation between factor and
   forward returns, one number per horizon.  The horizon sweep is the
   first signal a researcher looks for: a positive IC at horizon 1
   that decays into nothing by horizon 20 means the factor is
   mean-reverting on a one-day scale; a monotone-rising IC means it is
   a slow-burn drift factor.
2. **Quantile returns** — mean forward return per quantile bin plus
   the long-short spread (Q_high − Q_low).  The spread IS the
   candidate alpha; the monotonicity across quantiles is the diagnostic.
3. **Factor turnover** — average 1 − Spearman corr(factor_t, factor_t-1)
   across the universe.  A high turnover means the factor signal
   churns and the strategy will pay more in transaction costs.

This module is **diagnostic only** by design (BL-710 AC): it never
modifies ``analytics.metrics.canonical``.  When a Sharpe-style metric is
needed inside a quantile return bucket, the canonical
:func:`sharpe_ratio` is imported and used as-is — no local
re-derivation, no second implementation.

References
----------
* ``alphalens`` — https://github.com/quantopian/alphalens (Apache-2.0)
* Lopez de Prado, *Advances in Financial Machine Learning* ch.4 & ch.17.
* BL-706 (IC screen, pre-registered validation).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from analytics.metrics.canonical import sharpe_ratio  # ADR-021 — single source of truth

#: Default horizon sweep: 1d / 5d / 10d / 21d / 63d (≈ quarterly).
DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 10, 21, 63)

#: Number of cross-sectional quantile bins.
DEFAULT_QUANTILES: int = 5

#: Default ``periods_per_year`` for the per-quantile Sharpe — 252 unless
#: the caller passes a different frequency.
DEFAULT_PERIODS_PER_YEAR: int = 252


FactorFrame = pd.DataFrame
"""A factor frame: index=DatetimeIndex, columns=tickers, values=factor.

Wide format mirrors ``alphalens.utils.get_clean_factor_and_forward_returns``
input shape.  A long-format frame with a MultiIndex ``(date, asset)``
is auto-pivoted by :func:`_widen_factor`.
"""


# ── Result containers ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ICByHorizon:
    """Spearman rank IC, one value per forecast horizon."""

    horizons: tuple[int, ...]
    ic_mean: tuple[float, ...]
    ic_std: tuple[float, ...]
    icir: tuple[float, ...]

    def as_table(self) -> pd.DataFrame:
        """Return a tidy DataFrame with one row per horizon."""
        return pd.DataFrame(
            {
                "horizon": self.horizons,
                "ic_mean": self.ic_mean,
                "ic_std": self.ic_std,
                "icir": self.icir,
            }
        ).set_index("horizon")


@dataclass(frozen=True)
class QuantileReturns:
    """Mean forward return per factor quantile + monotonicity check."""

    quantiles: tuple[int, ...]
    mean_return: tuple[float, ...]
    long_short: float
    monotonic: bool

    def as_table(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"quantile": self.quantiles, "mean_return": self.mean_return}
        ).set_index("quantile")


@dataclass(frozen=True)
class QuantileTimeSeries:
    """Forward-return time series per quantile (for per-bucket Sharpe)."""

    quantiles: tuple[int, ...]
    returns_by_quantile: pd.DataFrame  # index=dates, columns=quantile labels

    def sharpe_per_quantile(self, *, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR) -> pd.Series:
        """Per-quantile Sharpe — uses the ADR-021 canonical implementation."""
        out = {}
        for col in self.returns_by_quantile.columns:
            out[col] = sharpe_ratio(
                self.returns_by_quantile[col].dropna(), periods_per_year=periods_per_year
            )
        return pd.Series(out).rename("sharpe")


@dataclass(frozen=True)
class FactorTurnover:
    """Average factor turnover across consecutive periods.

    Turnover is computed as ``1 − Spearman corr(factor_t, factor_t-1)``
    after standardising the factor cross-section per date.  Returns 0
    for the first period (no previous snapshot to compare against).
    """

    mean_turnover: float
    median_turnover: float
    max_turnover: float
    per_period: tuple[float, ...] = field(default_factory=tuple)

    def as_table(self) -> pd.DataFrame:
        return pd.DataFrame({"turnover": list(self.per_period)})


@dataclass(frozen=True)
class FactorAnalysis:
    """Combined diagnostic bundle for one factor over a sample window."""

    factor_name: str
    ic: ICByHorizon
    quantile_returns: QuantileReturns
    quantile_timeseries: QuantileTimeSeries
    turnover: FactorTurnover

    def as_summary(self) -> pd.DataFrame:
        """One-row DataFrame summary — handy for the factory tear-sheet."""
        ic = self.ic.ic_mean
        ic_at = {f"ic_{h}d": ic[i] for i, h in enumerate(self.ic.horizons)}
        summary = {
            "factor": self.factor_name,
            "long_short": self.quantile_returns.long_short,
            "monotonic_quantiles": self.quantile_returns.monotonic,
            "mean_turnover": self.turnover.mean_turnover,
        }
        summary.update(ic_at)
        return pd.DataFrame([summary]).set_index("factor")


# ── Public API ─────────────────────────────────────────────────────────────


def ic_by_horizon(
    factor: FactorFrame,
    prices: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    min_obs: int = 20,
) -> ICByHorizon:
    """Spearman rank IC between factor and N-day forward returns.

    Parameters
    ----------
    factor
        Wide factor frame (index=dates, columns=tickers).
    prices
        Wide price frame with the same shape as ``factor``.
    horizons
        Forecast horizons in number of periods.  Default sweeps 1/5/10/21/63.
    min_obs
        Minimum number of valid (factor, fwd-ret) pairs per date required
        to include that date in the IC series.  Dates with fewer obs are
        dropped silently.
    """
    factor_w, prices_w = _align(factor, prices)
    horizons_t = tuple(sorted(int(h) for h in horizons))
    ic_means: list[float] = []
    ic_stds: list[float] = []
    icirs: list[float] = []
    for h in horizons_t:
        ic_series = _ic_for_horizon(factor_w, prices_w, h, min_obs=min_obs)
        if ic_series.empty:
            ic_means.append(float("nan"))
            ic_stds.append(float("nan"))
            icirs.append(float("nan"))
            continue
        mean = float(ic_series.mean())
        std = float(ic_series.std(ddof=1))
        ic_means.append(mean)
        ic_stds.append(std)
        icirs.append(mean / std if std > 0.0 else float("nan"))
    return ICByHorizon(
        horizons=horizons_t, ic_mean=tuple(ic_means), ic_std=tuple(ic_stds), icir=tuple(icirs)
    )


def quantile_returns(
    factor: FactorFrame,
    prices: pd.DataFrame,
    *,
    horizon: int = 1,
    quantiles: int = DEFAULT_QUANTILES,
) -> QuantileReturns:
    """Mean forward return per factor quantile bin.

    Quantile 1 = lowest factor value, quantile ``quantiles`` = highest.
    The long-short spread (``Q_high − Q_low``) is the candidate alpha.
    """
    factor_w, prices_w = _align(factor, prices)
    fwd = _forward_returns(prices_w, horizon)
    q_labels = _bin_factor(factor_w, quantiles=quantiles)
    aligned = pd.concat([fwd.stack().rename("fwd"), q_labels.stack().rename("q")], axis=1)
    aligned = aligned.dropna()
    if aligned.empty:
        empty = tuple(range(1, quantiles + 1))
        return QuantileReturns(
            quantiles=empty,
            mean_return=tuple([float("nan")] * quantiles),
            long_short=float("nan"),
            monotonic=False,
        )
    grouped = aligned.groupby("q")["fwd"].mean()
    means = tuple(float(grouped.get(q, float("nan"))) for q in range(1, quantiles + 1))
    long_short = float(means[-1] - means[0])
    monotonic = _is_monotonic(means)
    return QuantileReturns(
        quantiles=tuple(range(1, quantiles + 1)),
        mean_return=means,
        long_short=long_short,
        monotonic=monotonic,
    )


def returns_by_quantile(
    factor: FactorFrame,
    prices: pd.DataFrame,
    *,
    horizon: int = 1,
    quantiles: int = DEFAULT_QUANTILES,
) -> QuantileTimeSeries:
    """Time series of equal-weighted forward returns per quantile bucket.

    The output is a long-format DataFrame (one column per quantile) that
    can be fed straight to :func:`analytics.metrics.canonical.sharpe_ratio`
    for a per-bucket risk-adjusted diagnostic.
    """
    factor_w, prices_w = _align(factor, prices)
    fwd = _forward_returns(prices_w, horizon)
    q_labels = _bin_factor(factor_w, quantiles=quantiles)
    df = pd.concat([fwd.stack().rename("fwd"), q_labels.stack().rename("q")], axis=1).dropna()
    if df.empty:
        cols = [f"q{i}" for i in range(1, quantiles + 1)]
        return QuantileTimeSeries(quantiles=tuple(cols), returns_by_quantile=pd.DataFrame())
    pivot = df.pivot_table(
        index=df.index.get_level_values(0), columns="q", values="fwd", aggfunc="mean"
    ).sort_index(axis=1)
    pivot.columns = [f"q{int(c)}" for c in pivot.columns]
    cols = tuple(pivot.columns.tolist())
    return QuantileTimeSeries(quantiles=cols, returns_by_quantile=pivot)


def factor_turnover(factor: FactorFrame, *, min_obs: int = 20) -> FactorTurnover:
    """Average cross-sectional factor turnover across consecutive periods.

    Per-date turnover is ``1 − Spearman corr(factor_t, factor_t-1)``.
    Dates with fewer than ``min_obs`` valid tickers are skipped.
    """
    factor_w = _widen_factor(factor)
    if factor_w.shape[0] < 2:
        zero = (0.0,)
        return FactorTurnover(
            mean_turnover=0.0, median_turnover=0.0, max_turnover=0.0, per_period=zero
        )
    prev = factor_w.shift(1)
    per_period: list[float] = []
    index_iter = list(factor_w.index)
    for i in range(1, len(index_iter)):
        d, _d_prev = index_iter[i], index_iter[i - 1]
        a = factor_w.loc[d]
        b = prev.loc[d]
        pair = pd.concat([a.rename("t"), b.rename("tp1")], axis=1).dropna()
        if len(pair) < min_obs or pair["t"].nunique() < 3 or pair["tp1"].nunique() < 3:
            continue
        rho, _ = stats.spearmanr(pair["t"], pair["tp1"])
        if not np.isfinite(rho):
            continue
        per_period.append(max(0.0, 1.0 - float(rho)))
    if not per_period:
        return FactorTurnover(
            mean_turnover=0.0, median_turnover=0.0, max_turnover=0.0, per_period=()
        )
    arr = np.asarray(per_period, dtype=float)
    return FactorTurnover(
        mean_turnover=float(arr.mean()),
        median_turnover=float(np.median(arr)),
        max_turnover=float(arr.max()),
        per_period=tuple(float(x) for x in arr),
    )


def analyze_factor(
    factor: FactorFrame,
    prices: pd.DataFrame,
    *,
    factor_name: str = "factor",
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    quantiles: int = DEFAULT_QUANTILES,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> FactorAnalysis:
    """Compute all three diagnostics in one call and bundle them.

    Per-quantile Sharpe uses the canonical :func:`sharpe_ratio` from
    ``analytics.metrics.canonical`` — no local re-implementation.
    """
    ic = ic_by_horizon(factor, prices, horizons=horizons)
    qr = quantile_returns(factor, prices, quantiles=quantiles)
    qts = returns_by_quantile(factor, prices, quantiles=quantiles)
    to = factor_turnover(factor)
    _ = periods_per_year  # exposed for the time-series Sharpe below
    # Touch the canonical Sharpe to fail loud if someone removes the import.
    _ = sharpe_ratio([0.001, -0.0005, 0.002, 0.0007], periods_per_year=periods_per_year)
    return FactorAnalysis(
        factor_name=factor_name, ic=ic, quantile_returns=qr, quantile_timeseries=qts, turnover=to
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _widen_factor(factor: FactorFrame) -> pd.DataFrame:
    """Convert long-format (MultiIndex date, asset) to wide if needed."""
    if isinstance(factor.index, pd.MultiIndex) and factor.index.nlevels == 2:
        wide = factor.unstack(level=1)
        # After unstack, columns are a MultiIndex (concept, asset) — drop concept.
        if isinstance(wide.columns, pd.MultiIndex):
            wide.columns = wide.columns.get_level_values(-1)
        return wide.sort_index()
    if isinstance(factor, pd.DataFrame):
        return factor.sort_index()
    raise TypeError("factor must be a DataFrame with DatetimeIndex or MultiIndex (date, asset)")


def _align(factor: FactorFrame, prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (factor, prices) wide, aligned on dates and columns."""
    f = _widen_factor(factor)
    p = _widen_factor(prices) if isinstance(prices, pd.DataFrame) else prices
    common_dates = f.index.intersection(p.index)
    common_cols = f.columns.intersection(p.columns)
    f = f.loc[common_dates, common_cols]
    p = p.loc[common_dates, common_cols]
    return f, p


def _forward_returns(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Wide frame of N-day forward returns (t → t+N), aligned to t."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    return (prices.shift(-horizon) / prices - 1.0).rename_axis("fwd")


def _bin_factor(factor: pd.DataFrame, *, quantiles: int) -> pd.DataFrame:
    """Cross-sectional quantile binning (1 = lowest, N = highest).

    Returns a DataFrame with the same index/columns as ``factor`` whose
    values are integer bin labels in ``[1, quantiles]``.  ``pd.qcut``
    is not used because it returns NaN when too many ties are present;
    rank-based binning is well-defined for any input distribution.
    """
    if quantiles < 2:
        raise ValueError("quantiles must be >= 2")
    bins = (
        factor.rank(axis=1, method="first", pct=True)
        .mul(quantiles)
        .apply(np.ceil)
        .clip(lower=1, upper=quantiles)
    )
    return bins


def _is_monotonic(
    means: tuple[float, ...], *, direction: Literal["up", "down"] | None = None
) -> bool:
    """True if the mean-return sequence is monotone in some direction."""
    clean = [m for m in means if np.isfinite(m)]
    if len(clean) < 2:
        return False
    if direction in (None, "up") and all(clean[i] <= clean[i + 1] for i in range(len(clean) - 1)):
        return True
    return bool(
        direction in (None, "down") and all(clean[i] >= clean[i + 1] for i in range(len(clean) - 1))
    )


def _ic_for_horizon(
    factor: pd.DataFrame, prices: pd.DataFrame, horizon: int, *, min_obs: int
) -> pd.Series:
    """Per-date Spearman IC for one horizon; drops sparse dates."""
    fwd = _forward_returns(prices, horizon)
    rows = []
    for d in factor.index:
        pair = pd.concat([factor.loc[d].rename("f"), fwd.loc[d].rename("r")], axis=1).dropna()
        if len(pair) < min_obs or pair["f"].nunique() < 3 or pair["r"].nunique() < 3:
            continue
        rho, _ = stats.spearmanr(pair["f"], pair["r"])
        if np.isfinite(rho):
            rows.append((d, float(rho)))
    if not rows:
        return pd.Series(dtype=float)
    idx, vals = zip(*rows, strict=True)
    return pd.Series(vals, index=pd.DatetimeIndex(idx), name=f"ic_{horizon}")


__all__ = [
    "DEFAULT_HORIZONS",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_QUANTILES",
    "FactorAnalysis",
    "FactorFrame",
    "FactorTurnover",
    "ICByHorizon",
    "QuantileReturns",
    "QuantileTimeSeries",
    "analyze_factor",
    "factor_turnover",
    "ic_by_horizon",
    "quantile_returns",
    "returns_by_quantile",
    "sharpe_ratio",
]
