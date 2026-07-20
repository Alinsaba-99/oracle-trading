"""Timeframe utilities for multi-TF composition (R2.1).

The repo uses string TF codes consistently across providers
(``SUPPORTED_TIMEFRAMES = ("15m", "1h", "4h", "1d")``). This module is the
single source of truth for:

- ``TF_TO_TIMEDELTA``: code → ``datetime.timedelta``
- ``tf_duration``: code → ``timedelta`` (raises on unknown)
- ``is_higher_tf``: True iff the second TF is strictly coarser than the first
- ``validate_pair``: enforce that ``filter_tf`` is strictly higher than
  ``primary_tf`` — the only composition R2 supports
- ``TIMEFRAME_ORDER``: codes ordered finest → coarsest, for sorting
"""

from __future__ import annotations

from datetime import timedelta

#: Ordered finest → coarsest. Index in this list defines "higher".
TIMEFRAME_ORDER: tuple[str, ...] = ("15m", "1h", "4h", "1d")

#: Duration of one bar per TF.
TF_TO_TIMEDELTA: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


def tf_duration(tf: str) -> timedelta:
    """Return the bar duration for ``tf``. Raises ``ValueError`` on unknown."""
    try:
        return TF_TO_TIMEDELTA[tf]
    except KeyError as exc:
        raise ValueError(f"unknown timeframe {tf!r}; supported: {list(TF_TO_TIMEDELTA)}") from exc


def tf_index(tf: str) -> int:
    """Position of ``tf`` in ``TIMEFRAME_ORDER`` (0 = finest). Raises on unknown."""
    try:
        return TIMEFRAME_ORDER.index(tf)
    except ValueError as exc:
        raise ValueError(f"unknown timeframe {tf!r}; supported: {list(TIMEFRAME_ORDER)}") from exc


def is_higher_tf(primary_tf: str, filter_tf: str) -> bool:
    """True iff ``filter_tf`` is strictly coarser than ``primary_tf``.

    Equal TFs return False — a same-TF "filter" is just another signal on
    the same frame, not a multi-TF composition.
    """
    return tf_index(filter_tf) > tf_index(primary_tf)


def validate_pair(primary_tf: str, filter_tf: str) -> None:
    """Raise ``ValueError`` unless ``filter_tf`` is strictly higher than
    ``primary_tf``. Use this at composition/spec-validation time.
    """
    if not is_higher_tf(primary_tf, filter_tf):
        raise ValueError(
            f"filter_tf must be strictly higher than primary_tf "
            f"(got primary={primary_tf!r}, filter={filter_tf!r}); "
            f"order finest→coarsest is {TIMEFRAME_ORDER}"
        )


def bars_per_filter_bar(primary_tf: str, filter_tf: str) -> int:
    """Number of primary bars that fit inside one filter bar (rounded).

    E.g. ``bars_per_filter_bar("1h", "1d") == 24``;
    ``bars_per_filter_bar("15m", "4h") == 16``.
    """
    validate_pair(primary_tf, filter_tf)
    ratio = tf_duration(filter_tf) / tf_duration(primary_tf)
    return round(ratio)
