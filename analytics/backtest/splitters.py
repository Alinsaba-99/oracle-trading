"""Cross-validation splitters for walk-forward backtesting.

Provides Combinatorial Purged Cross-Validation (CPCV) and time-series
CV splitters with configurable purge windows to prevent data leakage
between train and test folds.
"""

from __future__ import annotations

from itertools import combinations

import polars as pl


def cpcv_split(
    n_instances: int, n_splits: int, n_test_splits: int, purge_window: int = 0
) -> list[tuple[list[int], list[int]]]:
    """Combinatorial Purged Cross-Validation splitter.

    Divides *n_instances* into *n_splits* contiguous chronological groups,
    then forms all combinations of *n_test_splits* groups as test sets.
    A *purge_window* (in sample units) is removed from the training
    groups that neighbour each test group boundary, preventing leakage
    from the test period into the training set.

    Parameters
    ----------
    n_instances:
        Total number of data points (rows).
    n_splits:
        Number of chronological groups to divide the data into.
    n_test_splits:
        Number of groups to combine into each test fold.
    purge_window:
        Number of samples to exclude from training on each side of a
        test group boundary.  ``0`` disables purging.

    Returns
    -------
    list of (train_indices, test_indices) tuples, one per combination.
    """
    if n_test_splits >= n_splits:
        raise ValueError(f"n_test_splits ({n_test_splits}) must be less than n_splits ({n_splits})")

    # Build contiguous group boundaries
    bounds: list[tuple[int, int]] = []
    for i in range(n_splits):
        start = i * n_instances // n_splits
        end = (i + 1) * n_instances // n_splits if i < n_splits - 1 else n_instances
        bounds.append((start, end))

    splits: list[tuple[list[int], list[int]]] = []
    for test_groups in combinations(range(n_splits), n_test_splits):
        test_set = set(test_groups)

        test_indices: list[int] = []
        for g in test_groups:
            s, e = bounds[g]
            test_indices.extend(range(s, e))

        train_indices: list[int] = []
        for g in range(n_splits):
            if g in test_set:
                continue
            s, e = bounds[g]

            # Purge the beginning of this group if it follows a test group
            purge_from_start = 0
            if purge_window > 0 and (g - 1) in test_set:
                purge_from_start = min(purge_window, e - s)

            # Purge the end of this group if it precedes a test group
            purge_from_end = 0
            if purge_window > 0 and (g + 1) in test_set:
                purge_from_end = min(purge_window, e - s)

            train_indices.extend(range(s + purge_from_start, e - purge_from_end))

        splits.append((train_indices, test_indices))

    return splits


def time_series_split(
    dates: pl.Series, n_splits: int, purge_window: int = 0
) -> list[tuple[list[int], list[int]]]:
    """Time-series cross-validation splitter with expanding window and purge gap.

    For split ``i`` in ``range(n_splits)``:

        Train = ``[0, (i+1) * step - purge_window)``
        Test  = ``[(i+1) * step, (i+2) * step)``

    where ``step = len(dates) // (n_splits + 1)``.  The *purge_window*
    creates a gap between the training and test sets so that no recent
    data leaks into the test evaluation.

    Parameters
    ----------
    dates:
        Datetime series (used only for its length).
    n_splits:
        Number of train/test folds.
    purge_window:
        Number of samples to exclude from the end of each training
        window.

    Returns
    -------
    list of (train_indices, test_indices) tuples.
    """
    n = len(dates)
    step = n // (n_splits + 1)
    if step == 0:
        raise ValueError(
            f"n_splits={n_splits} produces zero-length step from {n} samples; "
            f"reduce n_splits or provide more data."
        )

    splits: list[tuple[list[int], list[int]]] = []
    for i in range(n_splits):
        train_end = (i + 1) * step
        test_start = train_end
        test_end = min(n, test_start + step)

        train_effective_end = max(0, train_end - purge_window)
        train_indices = list(range(train_effective_end))
        test_indices = list(range(test_start, test_end))

        if len(train_indices) > 0 and len(test_indices) > 0:
            splits.append((train_indices, test_indices))

    return splits


class CombinatorialPurgedCV:
    """Combinatorial Purged Cross-Validation splitter (scikit-learn style).

    Parameters
    ----------
    n_splits:
        Number of chronological groups to divide the data into.
    n_test_splits:
        Number of groups to use for testing in each combination.
    purge_window:
        Number of samples to exclude from training on each side of a
        test group boundary.
    """

    def __init__(self, n_splits: int = 5, n_test_splits: int = 2, purge_window: int = 0) -> None:
        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.purge_window = purge_window

    def split(self, n_instances: int) -> list[tuple[list[int], list[int]]]:
        """Generate CPCV train/test index pairs.

        Parameters
        ----------
        n_instances:
            Total number of data points.

        Returns
        -------
        list of (train_indices, test_indices) tuples.
        """
        return cpcv_split(n_instances, self.n_splits, self.n_test_splits, self.purge_window)
