"""BL-706 — Pre-registered IC screen for factor hypotheses.

Spearman rank IC computed on non-overlapping windows of (factor, forward
return) pairs; significance via moving-block bootstrap over the window-IC
series.  Criteria pre-registered (design spec §6): ICIR > 0.05,
block-bootstrap t > 2.5, with a 30% post-publication haircut applied to
the measured ICIR before the verdict.  Direction is fixed (long-factor):
a negative-IC factor FAILS, it is never sign-flipped post-hoc.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

_MIN_WINDOWS = 4


@dataclass(frozen=True)
class ICResult:
    n_windows: int
    ic_mean: float
    ic_std: float
    icir: float
    t_block: float
    icir_haircut: float
    passes: bool
    haircut_pct: float
    icir_threshold: float
    t_threshold: float


def _forward_returns(prices: pd.Series, horizon: int) -> pd.Series:
    return (prices.shift(-horizon) / prices - 1.0).rename("fwd_ret")


def _window_ics(factor: pd.Series, fwd: pd.Series, window: int) -> list[float]:
    df = pd.concat([factor.rename("factor"), fwd], axis=1).dropna()
    ics: list[float] = []
    for start in range(0, len(df) - window + 1, window):
        chunk = df.iloc[start : start + window]
        if chunk["factor"].nunique() < 3 or chunk["fwd_ret"].nunique() < 3:
            continue
        ic, _ = stats.spearmanr(chunk["factor"], chunk["fwd_ret"])
        ics.append(float(ic))
    return ics


def _block_bootstrap_t(ics: np.ndarray, block_len: int, n_boot: int, seed: int) -> float:
    """t-stat of mean IC under a moving-block bootstrap of the IC series."""
    rng = np.random.default_rng(seed)
    n = len(ics)
    if n < 2 or block_len > n:
        return float("nan")
    n_blocks = int(np.ceil(n / block_len))
    max_start = n - block_len
    starts = rng.integers(0, max_start + 1, size=(n_boot, n_blocks))
    means = np.array(
        [np.concatenate([ics[s : s + block_len] for s in row])[:n].mean() for row in starts]
    )
    denom = means.std(ddof=1)
    if not np.isfinite(denom) or denom == 0.0:
        return float("inf") if ics.mean() > 0 else (float("-inf") if ics.mean() < 0 else 0.0)
    return float(ics.mean() / denom)


def screen_factor(
    factor: pd.Series,
    prices: pd.Series,
    horizon: int = 5,
    window: int = 63,
    block_len: int = 5,
    n_boot: int = 1_000,
    seed: int = 42,
    haircut_pct: float = 30.0,
    icir_threshold: float = 0.05,
    t_threshold: float = 2.5,
) -> ICResult:
    """Pre-registered IC screen (BL-706).

    Non-overlapping Spearman IC windows; verdict from haircut-adjusted ICIR
    and block-bootstrap t.  Fails closed on insufficient data (<4 windows)
    and on negative mean IC (direction fixed, no post-hoc sign flip).
    """
    fwd = _forward_returns(prices, horizon)
    ics = np.asarray(_window_ics(factor, fwd, window), dtype=float)
    if len(ics) < _MIN_WINDOWS:
        return ICResult(
            n_windows=len(ics),
            ic_mean=float("nan"),
            ic_std=float("nan"),
            icir=float("nan"),
            t_block=float("nan"),
            icir_haircut=float("nan"),
            passes=False,
            haircut_pct=haircut_pct,
            icir_threshold=icir_threshold,
            t_threshold=t_threshold,
        )
    ic_mean = float(ics.mean())
    ic_std = float(ics.std(ddof=1))
    icir = ic_mean / ic_std if ic_std > 0 else float("nan")
    t_block = _block_bootstrap_t(ics, block_len, n_boot, seed)
    icir_haircut = icir * (1.0 - haircut_pct / 100.0) if np.isfinite(icir) else float("nan")
    passes = bool(
        np.isfinite(icir_haircut)
        and np.isfinite(t_block)
        and ic_mean > 0  # direction fixed: negative-IC fails, no sign flip
        and icir_haircut > icir_threshold
        and t_block > t_threshold
    )
    return ICResult(
        n_windows=len(ics),
        ic_mean=ic_mean,
        ic_std=ic_std,
        icir=icir,
        t_block=t_block,
        icir_haircut=icir_haircut,
        passes=passes,
        haircut_pct=haircut_pct,
        icir_threshold=icir_threshold,
        t_threshold=t_threshold,
    )


__all__ = ["ICResult", "screen_factor"]
