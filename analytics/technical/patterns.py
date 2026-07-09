"""Candlestick pattern detection via TA-Lib.

Each TA-Lib candlestick function returns a 1-D numpy array where:
  - ``100`` / ``-100`` indicate the pattern was detected (bullish / bearish)
  - ``0`` indicates no detection

:func:`detect` runs all available CDL* functions and returns the names
of every pattern that is present (non-zero) at the last bar.
"""

from __future__ import annotations

import numpy as np
import polars as pl

# ── TA-Lib candlestick function names ──────────────────────────────────────
# Functions that accept (open, high, low, close) signature.
_PATTERN_FUNCTIONS: list[str] = [
    "CDL2CROWS",
    "CDL3BLACKCROWS",
    "CDL3INSIDE",
    "CDL3LINESTRIKE",
    "CDL3OUTSIDE",
    "CDL3STARSINSOUTH",
    "CDL3WHITESOLDIERS",
    "CDLABANDONEDBABY",
    "CDLADVANCEBLOCK",
    "CDLBELTHOLD",
    "CDLBREAKAWAY",
    "CDLCLOSINGMARUBOZU",
    "CDLCONCEALBABYSWALL",
    "CDLCOUNTERATTACK",
    "CDLDARKCLOUDCOVER",
    "CDLDOJI",
    "CDLDOJISTAR",
    "CDLDRAGONFLYDOJI",
    "CDLENGULFING",
    "CDLEVENINGDOJISTAR",
    "CDLEVENINGSTAR",
    "CDLGAPSIDESIDEWHITE",
    "CDLGRAVESTONEDOJI",
    "CDLHAMMER",
    "CDLHANGINGMAN",
    "CDLHARAMI",
    "CDLHARAMICROSS",
    "CDLHIGHWAVE",
    "CDLHIKKAKE",
    "CDLHIKKAKEMOD",
    "CDLHOMINGPIGEON",
    "CDLIDENTICAL3CROWS",
    "CDLINNECK",
    "CDLINVERTEDHAMMER",
    "CDLKICKING",
    "CDLKICKINGBYLENGTH",
    "CDLLADDERBOTTOM",
    "CDLLONGLINE",
    "CDLMARUBOZU",
    "CDLMATCHINGLOW",
    "CDLMATHOLD",
    "CDLMORNINGDOJISTAR",
    "CDLMORNINGSTAR",
    "CDLONNECK",
    "CDLPIERCING",
    "CDLRICKSHAWMAN",
    "CDLRISEFALL3METHODS",
    "CDLSEPARATINGLINES",
    "CDLSHOOTINGSTAR",
    "CDLSHORTLINE",
    "CDLSPINNINGTOP",
    "CDLSTALLEDPATTERN",
    "CDLSTICKSANDWICH",
    "CDLTAKURI",
    "CDLTASUKIGAP",
    "CDLTHRUSTING",
    "CDLTRISTAR",
    "CDLUNIQUE3RIVER",
    "CDLUPSIDEGAP2CROWS",
    "CDLXSIDEGAP3METHODS",
]

# Some TA-Lib CDL functions have extra parameters — these are the ones
# with a ``penetration`` (or similar) parameter.  We supply defaults.
_EXTRA_ARGS: dict[str, dict[str, float]] = {
    "CDLABANDONEDBABY": {"penetration": 0.3},
    "CDLDARKCLOUDCOVER": {"penetration": 0.5},
    "CDLEVENINGDOJISTAR": {"penetration": 0.3},
    "CDLEVENINGSTAR": {"penetration": 0.3},
    "CDLMORNINGDOJISTAR": {"penetration": 0.3},
    "CDLMORNINGSTAR": {"penetration": 0.3},
}


def _to_numpy_1d(series: pl.Series) -> np.ndarray:
    """Convert a Polars Series to a 1-D float64 numpy array for TA-Lib."""
    return series.to_numpy().astype(np.float64, copy=False)


def detect(open: pl.Series, high: pl.Series, low: pl.Series, close: pl.Series) -> list[str]:
    """Return the names of candlestick patterns present at the *last* bar.

    Args:
        open, high, low, close: OHLC price series.

    Returns:
        Sorted list of detected pattern names (e.g. ``["CDLDOJI", "CDLHAMMER"]``).
    """
    import talib as ta

    o = _to_numpy_1d(open)
    h = _to_numpy_1d(high)
    low_arr = _to_numpy_1d(low)
    c = _to_numpy_1d(close)

    detected: list[str] = []
    for name in _PATTERN_FUNCTIONS:
        func = getattr(ta, name, None)
        if func is None:
            continue

        kwargs = _EXTRA_ARGS.get(name, {})
        try:
            result = func(o, h, low_arr, c, **kwargs)
        except Exception:
            # Skip any pattern function that fails (e.g. missing optional param)
            continue

        # TA-Lib returns an ndarray; non-zero at the last bar → pattern detected
        if len(result) > 0 and result[-1] != 0:
            detected.append(name)

    return sorted(detected)


def detect_all(open: pl.Series, high: pl.Series, low: pl.Series, close: pl.Series) -> list[str]:
    """Alias for :func:`detect`."""
    return detect(open, high, low, close)
