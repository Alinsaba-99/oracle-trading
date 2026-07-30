"""Time-series cross-validation splitters — WalkForward, PurgedKFold, CPCV.

Inspired by Inalpha's cv.py (Combinatorial Purged CV with purge + embargo).
Pure index math — orthogonal to the backtest engine.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations
from math import comb

# ── Split ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Split:
    """A single train/test index pair.

    Attributes:
        train_idx: Training bar indices, ascending.
        test_idx: Out-of-sample bar indices, ascending.
        path_id: CPCV path identifier (0 for WalkForward/PurgedKFold).
    """

    train_idx: list[int]
    test_idx: list[int]
    path_id: int = 0


# ── Walk Forward ──────────────────────────────────────────────────────


class WalkForward:
    """Rolling/expanding window walk-forward validation.

    Args:
        test_size: Number of bars per test window.
        train_size: Number of bars per training window.
        expanding: If True, training window expands from 0.
    """

    def __init__(self, test_size: int, train_size: int, *, expanding: bool = False) -> None:
        if test_size < 1 or train_size < 1:
            raise ValueError("test_size and train_size must be >= 1")
        self.test_size = test_size
        self.train_size = train_size
        self.expanding = expanding

    def n_splits(self, n_samples: int) -> int:
        return max(0, (n_samples - self.train_size) // self.test_size)

    def split(self, n_samples: int) -> Iterator[Split]:
        n = self.n_splits(n_samples)
        if n < 1:
            return
        for k in range(n):
            test_end = n_samples - (n - 1 - k) * self.test_size
            test_start = test_end - self.test_size
            train_start = 0 if self.expanding else max(0, test_start - self.train_size)
            yield Split(
                train_idx=list(range(train_start, test_start)),
                test_idx=list(range(test_start, test_end)),
            )


# ── Purged K-Fold ─────────────────────────────────────────────────────


class PurgedKFold:
    """K-fold time-series CV with purge + embargo.

    Args:
        n_splits: Number of folds (>= 2).
        embargo_pct: Fraction of bars to embargo between train/test.
    """

    def __init__(self, n_splits: int, *, embargo_pct: float = 0.05) -> None:
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        self.n_folds = n_splits
        self.embargo_pct = embargo_pct

    def get_n_splits(self) -> int:
        return self.n_folds

    def split(self, n_samples: int) -> Iterator[Split]:
        if n_samples < self.n_folds * 2:
            return
        embargo = int(n_samples * self.embargo_pct)
        fold_size = n_samples // self.n_folds
        for fold in range(self.n_folds):
            test_start = fold * fold_size
            test_end = test_start + fold_size if fold < self.n_folds - 1 else n_samples
            test_idx = list(range(test_start, test_end))
            train_idx = [
                i for i in range(n_samples) if i < test_start - embargo or i >= test_end + embargo
            ]
            yield Split(train_idx=train_idx, test_idx=test_idx)


# ── Combinatorial Purged CV ───────────────────────────────────────────


class CombinatorialPurgedCV:
    """Combinatorial Purged Cross-Validation (López de Prado 2018).

    Splits N bars into K folds, then trains on N-K folds and tests on
    the held-out fold, for all C(N, K) combinations.  Test segments
    sharing the same position across folds are grouped into ``path_id``.

    Args:
        n_folds: Total number of folds (>= 2).
        n_test_folds: Number of folds held out in each combination (>= 1).
        embargo_pct: Fraction of bars to embargo between train/test.
    """

    def __init__(self, n_folds: int, n_test_folds: int = 1, *, embargo_pct: float = 0.05) -> None:
        if n_folds < 2:
            raise ValueError("n_folds must be >= 2")
        if not 1 <= n_test_folds < n_folds:
            raise ValueError("n_test_folds must be in [1, n_folds)")
        self.n_folds = n_folds
        self.n_test_folds = n_test_folds
        self.embargo_pct = embargo_pct

    def n_paths(self) -> int:
        return comb(self.n_folds - 1, self.n_test_folds - 1)

    def split(self, n_samples: int) -> Iterator[Split]:
        if n_samples < self.n_folds * 2:
            return
        embargo = int(n_samples * self.embargo_pct)
        fold_size = n_samples // self.n_folds
        folds = list(range(self.n_folds))

        for combo in combinations(folds, self.n_test_folds):
            test_folds = set(combo)
            path_counters: dict[int, int] = {}
            for test_fold in test_folds:
                t_start = test_fold * fold_size
                t_end = t_start + fold_size if test_fold < self.n_folds - 1 else n_samples
                test_idx = list(range(t_start, t_end))
                train_idx = [
                    i for i in range(n_samples) if i < t_start - embargo or i >= t_end + embargo
                ]
                path_counters[test_fold] = path_counters.get(test_fold - 1, 0) + 1
                yield Split(
                    train_idx=train_idx, test_idx=test_idx, path_id=path_counters[test_fold]
                )


__all__ = ["CombinatorialPurgedCV", "PurgedKFold", "Split", "WalkForward"]
