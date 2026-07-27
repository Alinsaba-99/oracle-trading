"""Factor ranking engine — scores all factors, returns sorted list.

Bridges the 50 alpha factors in ``genetics/alpha/factors.py`` (Polars)
with the effectiveness scorer (pandas).  Handles the impedance
mismatch: factors take a Polars DataFrame of OHLCV and return a Polars
Series; the scorer wants a pandas Series.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass

import polars as pl

from analytics.strategy.factor_timing.effectiveness import (
    FactorEffectiveness,
    bh_adjust,
    ic_pvalue,
    null_ic_benchmark,
    score_factor,
)

logger = logging.getLogger("oracle.strategy.factor_timing")

FactorFn = Callable[[pl.DataFrame], pl.Series]


@dataclass(frozen=True, slots=True)
class FactorRanking:
    """One factor + its effectiveness + adjusted p-value."""

    name: str
    effectiveness: FactorEffectiveness
    p_value: float
    p_value_bh: float  # after Benjamini-Hochberg correction across candidates
    null_benchmark: float = 0.0  # E[max |IC| | noise] for this candidate pool

    @property
    def passes_null_benchmark(self) -> bool:
        """True if |rank_ic| exceeds the selection-effect noise floor."""
        return abs(self.effectiveness.rank_ic) > self.null_benchmark


class FactorTimingEngine:
    """Ranks the factor catalog by current predictive power.

    Discovers factors from ``genetics/alpha/factors.py`` by introspection
    (any module-level ``def name(data: pl.DataFrame) -> pl.Series``).
    """

    def __init__(
        self, catalog: dict[str, FactorFn] | None = None, quantiles: int = 5, min_samples: int = 60
    ) -> None:
        if catalog is None:
            catalog = _default_catalog()
        self._catalog = catalog
        self._quantiles = quantiles
        self._min_samples = min_samples

    @property
    def catalog(self) -> dict[str, FactorFn]:
        return dict(self._catalog)

    def rank(
        self,
        data: pl.DataFrame,
        close_col: str = "close",
        horizon: int = 5,
        skip_errors: bool = True,
    ) -> list[FactorRanking]:
        """Score every factor in the catalog against forward returns.

        Args:
            data: OHLCV Polars DataFrame (lowercase cols by default — see
                  ``genetics/alpha/factors.py``).  Capitalised aliases
                  (``Close``, ``High``, etc.) are accepted and renamed
                  internally to lowercase before invoking factor functions.
            close_col: name of the close-price column (default ``"close"``).
            horizon: forward-return window in bars.
            skip_errors: if True, log+skip factors that fail; if False, raise.

        Returns:
            List of FactorRanking sorted by |rank_ic| descending,
            with BH-adjusted p-values.
        """
        # Normalize column names to lowercase for the genetics catalog
        rename_map = {c: c.lower() for c in data.columns if c != c.lower()}
        if rename_map:
            data = data.rename(rename_map)
        close_col = close_col.lower()

        if close_col not in data.columns:
            raise ValueError(f"close_col {close_col!r} not in {data.columns}")

        close_pd = data[close_col].to_pandas()
        # Use a positional index so factor & close align by row number
        close_pd = close_pd.reset_index(drop=True)

        # Compute each factor + score
        scored: list[tuple[str, FactorEffectiveness]] = []
        for name, fn in self._catalog.items():
            try:
                series_pl = fn(data)
                factor_pd = series_pl.to_pandas().reset_index(drop=True)
                eff = score_factor(
                    factor_pd,
                    close_pd,
                    horizon=horizon,
                    quantiles=self._quantiles,
                    min_samples=self._min_samples,
                )
                scored.append((name, eff))
            except Exception as e:
                if not skip_errors:
                    raise
                logger.warning(f"factor {name} failed: {type(e).__name__}: {e}")

        if not scored:
            return []

        # Multiple-testing correction across all candidates
        pvalues = [ic_pvalue(e.rank_ic, e.sample_size, horizon=horizon) for _, e in scored]
        pvalues_bh = bh_adjust(pvalues)

        # Null benchmark: E[max |IC| | pure noise] across N candidates
        n = len(scored)
        sample_size = max((e.sample_size for _, e in scored), default=0)
        null_bench = null_ic_benchmark(n, sample_size, horizon)

        rankings = [
            FactorRanking(
                name=name, effectiveness=eff, p_value=pv, p_value_bh=pvbh, null_benchmark=null_bench
            )
            for (name, eff), pv, pvbh in zip(scored, pvalues, pvalues_bh, strict=True)
        ]

        # Sort by |rank_ic| descending, stable
        rankings.sort(key=lambda r: -abs(r.effectiveness.rank_ic))
        return rankings


def _is_factor_fn(fn: object, module_name: str) -> bool:
    """Predicate: does ``fn`` look like a factor?"""
    if not inspect.isfunction(fn):
        return False
    if fn.__name__.startswith("_"):
        return False
    if getattr(fn, "__module__", None) != module_name:
        return False
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    if len(sig.parameters) != 1:
        return False
    ret = sig.return_annotation
    if ret is inspect.Signature.empty:
        return True
    ret_str = ret if isinstance(ret, str) else getattr(ret, "__name__", str(ret))
    return "Series" in ret_str


def _default_catalog() -> dict[str, FactorFn]:
    """Discover factor functions from ``genetics/alpha/factors.py``.

    The return-annotation match is string-based because
    ``from __future__ import annotations`` leaves annotations as
    strings — ``pl.Series`` may appear as ``'pl.Series'``, ``'Series'``,
    or the actual class object depending on import order.
    """
    from genetics.alpha import factors as fmod

    return {name: fn for name, fn in inspect.getmembers(fmod) if _is_factor_fn(fn, fmod.__name__)}


__all__ = ["FactorRanking", "FactorTimingEngine"]
