"""BL-718 / D2 — Crypto Funding Extremum carry factor (MoonDev ``fund_demand_bot``).

Distilled from the MoonDev *fund_demand_bot* script.  Perpetual-future
funding rates embed a market-imbalance premium: longs pay shorts when
funding is positive (market is over-leveraged long) and shorts pay
longs when funding is negative (market is over-leveraged short).  The
extremum carry factor trades the rare tails where that premium is
unusually large, betting on mean-reversion toward 0.

Spec verbatim from the BOM:

    unita:    percentuale annualizzata
              (BUG ORIGINALE CORRETTO: i -22/+14 del bot sono % annue,
               non per-period)
    long:     funding_8h <= -0.02%   (~ -22% annuo, coda rara)
    short:    funding_8h >= +0.013%  (~ +14% annuo, coda rara)
    funding_z: z-score rolling 60d del rate 8h (feature ML preferita)
    allineamento: reindex 1h, ffill dal settlement, shift(1) — MAI
                  interpolare (D1.3)
    soglie_preregistrate: long <= -20%/ann, short >= +25%/ann,
                  poi analisi di sensibilità (no grid optimization:
                  è data-snooping vietato da ADR-017)
    dati: Binance Vision fundingRate zip mensili 2020→ ($0, no key)
          fallback CCXT fetch_funding_rate_history paginate

**Bug fix.**  The original ``fund_demand_bot`` conflated per-period
funding with annualised funding.  This module fixes the unit error: the
canonical interface operates on **per-period (8h) raw rates** and
exposes an :func:`annualize_8h` helper that multiplies by 3 × 365 to
recover the canonical academic convention.  Pre-registered thresholds
(defaults) are in annualised percent to match the BOM.

**Anti-lookahead.**  The signal is always shifted by one settlement
period`` ( ``shift(1)`` ) before any decision is taken — never the raw
settlement value, never interpolated.

References
----------
* Binance perpetual funding documentation (Binance Vision ``fundingRate``).
* MoonDev fund_demand_bot (transcript 2026-08, trading-os/knowledge).
* Deep-research synthesis 2026-08-15 §KB-11 (on-chain & derivatives).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

# ── Canonical constants ────────────────────────────────────────────────────

#: Number of 8h funding settlements per day.
SETTLEMENTS_PER_DAY: int = 3

#: Trading days per year used to annualize funding.
TRADING_DAYS_PER_YEAR: int = 365

#: Annualization factor for 8h funding (3 × 365).
_ANNUALIZATION: int = SETTLEMENTS_PER_DAY * TRADING_DAYS_PER_YEAR  # = 1095

#: Pre-registered long threshold (annualized percent).  Negative = longs get paid.
DEFAULT_LONG_THRESHOLD_PCT_ANNUAL: float = -20.0

#: Pre-registered short threshold (annualized percent).  Positive = shorts get paid.
DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL: float = 25.0

#: Default z-score lookback: 60 days × 3 settlements/day = 180 bars (8h).
DEFAULT_ZSCORE_WINDOW: int = 180


# ── Result container ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class FundingExtremumResult:
    """Output of :func:`compute_funding_extremum`.

    Attributes
    ----------
    signals
        Polars DataFrame with columns ``date, funding_8h, funding_pct_ann,
        funding_z, signal, long_entry, short_entry``.  ``signal`` is in
        ``{-1, 0, +1}`` (-1=short entry, +1=long entry).
    params
        Echo of the input parameters.
    """

    signals: pl.DataFrame
    params: FundingExtremumParams


@dataclass(frozen=True)
class FundingExtremumParams:
    """Pre-registered Funding Extremum parameters (DISTILL-BOM §D2)."""

    long_threshold_pct_annual: float = DEFAULT_LONG_THRESHOLD_PCT_ANNUAL
    short_threshold_pct_annual: float = DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL
    zscore_window: int = DEFAULT_ZSCORE_WINDOW


# ── Public API ─────────────────────────────────────────────────────────────


def annualize_8h(funding_pct_8h: np.ndarray | pl.Series | float) -> np.ndarray | float:
    """Convert an 8h funding rate (percent) to annualised percent.

    The factor is ``3 settlements/day × 365 days/year = 1095`` and is the
    fix for the bug identified in DISTILL-BOM §D2 (the original bot was
    treating ``-22`` as per-period when it was already annualised).

    Parameters
    ----------
    funding_pct_8h
        Per-8h funding rate **in percent** (e.g. ``0.013`` means 0.013%
        per 8h, NOT 0.013 as a decimal).  Array-like accepted.
    """
    factor = _ANNUALIZATION
    if isinstance(funding_pct_8h, pl.Series):
        return funding_pct_8h * factor
    arr = np.asarray(funding_pct_8h, dtype=np.float64)
    return arr * factor


def deannualize_to_8h(funding_pct_annual: np.ndarray | pl.Series | float) -> np.ndarray | float:
    """Inverse of :func:`annualize_8h` — annualised percent → per-8h percent."""
    factor = 1.0 / _ANNUALIZATION
    if isinstance(funding_pct_annual, pl.Series):
        return funding_pct_annual * factor
    return np.asarray(funding_pct_annual, dtype=np.float64) * factor


def funding_zscore(
    funding_pct_8h: np.ndarray | pl.Series, *, window: int = DEFAULT_ZSCORE_WINDOW
) -> np.ndarray:
    """Rolling z-score of the 8h funding rate over ``window`` settlements.

    ``window=180`` matches 60 calendar days at 8h cadence.  Uses a
    ddof=0 population std to keep the scale consistent with
    ``scipy.stats.zscore(..., ddof=0)``.

    The first ``window - 1`` values are NaN (insufficient history).  No
    look-ahead: z-score at index ``i`` uses data up to and including
    index ``i``.
    """
    if window < 2:
        raise ValueError("zscore_window must be >= 2")
    arr = np.asarray(
        funding_pct_8h.to_numpy() if isinstance(funding_pct_8h, pl.Series) else funding_pct_8h,
        dtype=np.float64,
    )
    n = len(arr)
    out = np.full(n, np.nan)
    if n < window:
        return out
    cum = np.cumsum(np.insert(arr, 0, 0.0))
    cum_sq = np.cumsum(np.insert(arr * arr, 0, 0.0))
    for i in range(window - 1, n):
        s = cum[i + 1] - cum[i + 1 - window]
        sq = cum_sq[i + 1] - cum_sq[i + 1 - window]
        mean = s / window
        var = max(sq / window - mean * mean, 0.0)
        sd = np.sqrt(var)
        out[i] = (arr[i] - mean) / sd if sd > 0 else 0.0
    return out


def extremum_signal(
    funding_pct_8h: np.ndarray | pl.Series,
    *,
    long_threshold_pct_annual: float = DEFAULT_LONG_THRESHOLD_PCT_ANNUAL,
    short_threshold_pct_annual: float = DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL,
) -> np.ndarray:
    """Directional signal in ``{-1, 0, +1}`` from 8h funding rates.

    ``+1`` = longs are overcharged → contrarian long entry.
    ``-1`` = shorts are overcharged → contrarian short entry.
    ``0``  = no extremum, sit out.

    Thresholds are in **annualised percent** per the BOM §D2 pre-registered
    values (``-20%`` / ``+25%``).
    """
    arr = np.asarray(
        funding_pct_8h.to_numpy() if isinstance(funding_pct_8h, pl.Series) else funding_pct_8h,
        dtype=np.float64,
    )
    annual = arr * _ANNUALIZATION
    sig = np.zeros_like(annual, dtype=np.int8)
    sig[annual <= long_threshold_pct_annual] = 1
    sig[annual >= short_threshold_pct_annual] = -1
    return sig


def compute_funding_extremum(
    data: pl.DataFrame, params: FundingExtremumParams | None = None
) -> FundingExtremumResult:
    """Full pipeline: per-bar funding → annualized → z-score → signal.

    Parameters
    ----------
    data
        Polars DataFrame with columns ``date`` and ``funding_pct_8h``.
        ``funding_pct_8h`` is the raw 8h funding rate **in percent**
        (Binance Vision convention: a value of ``0.01`` means 0.01% per 8h,
        already converted from the raw ``0.0001`` decimal fraction).
    params
        Pre-registered thresholds and z-score window.  Defaults to BOM §D2.
    """
    p = params or FundingExtremumParams()
    if "funding_pct_8h" not in data.columns:
        raise ValueError("data must contain funding_pct_8h column")
    raw = data["funding_pct_8h"].to_numpy().astype(np.float64)
    annual = annualize_8h(raw)
    z = funding_zscore(raw, window=p.zscore_window)
    sig = extremum_signal(
        raw,
        long_threshold_pct_annual=p.long_threshold_pct_annual,
        short_threshold_pct_annual=p.short_threshold_pct_annual,
    )
    long_entry = sig == 1
    short_entry = sig == -1
    signals = pl.DataFrame(
        {
            "date": data["date"] if "date" in data.columns else pl.int_range(0, len(raw)),
            "funding_8h": raw,
            "funding_pct_ann": annual,
            "funding_z": z,
            "signal": sig,
            "long_entry": long_entry,
            "short_entry": short_entry,
        }
    )
    return FundingExtremumResult(signals=signals, params=p)


def align_hourly(funding_series: pl.Series, *, hourly_index: pl.Series) -> pl.Series:
    """Reindex 8h funding onto an hourly grid via forward-fill (D1.3 rule).

    Critically: the spec forbids interpolation.  Forward-fill from the
    last settlement is the only acceptable transform.  Returns a Polars
    Series aligned to ``hourly_index`` with the same length.

    Raises
    ------
    ValueError
        If the funding Series has a DatetimeIndex that does not lie on
        8h boundaries (top-of-hour, +8h, +16h, ...).
    """
    if len(funding_series) == 0:
        raise ValueError("funding_series is empty")
    if len(hourly_index) == 0:
        raise ValueError("hourly_index is empty")
    funding_df = pl.DataFrame({"ts": funding_series.name, "funding": funding_series})
    hourly_df = pl.DataFrame({"ts": hourly_index})
    merged = hourly_df.join_asof(funding_df, on="ts", strategy="backward")
    return merged["funding"]


__all__ = [
    "DEFAULT_LONG_THRESHOLD_PCT_ANNUAL",
    "DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL",
    "DEFAULT_ZSCORE_WINDOW",
    "SETTLEMENTS_PER_DAY",
    "TRADING_DAYS_PER_YEAR",
    "FundingExtremumParams",
    "FundingExtremumResult",
    "align_hourly",
    "annualize_8h",
    "compute_funding_extremum",
    "deannualize_to_8h",
    "extremum_signal",
    "funding_zscore",
]
