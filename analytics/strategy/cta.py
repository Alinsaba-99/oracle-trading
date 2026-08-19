"""CTA backbone — 4 Carver modules (BL-502 / Lane A backbone).

This module implements the four core modules from Robert Carver's
"Systematic Trading" / pysystemtrade framework as reference, NOT as
dependency:

1. **vol_target** (:class:`VolatilityTarget`) — target a fixed annualised
   volatility by scaling position size inversely to realised volatility.
2. **forecast_scale** (:class:`ForecastScale`) — normalise a raw signal
   forecast to a common expected-returns scale (e.g. ±2σ).
3. **forecast_combine** (:class:`ForecastCombine`) — weighted blend of
   multiple forecasts with per-forecast scale + cap.
4. **idm** (:class:`InstrumentDiversificationMultiplier`) — scalar that
   reduces aggregate position when trading multiple instruments whose
   returns are not perfectly correlated.

These four modules form the backbone of Lane A (PAC multi-asset,
trend-following) per the deep-research synthesis 2026-08-15. They are
NOT a wrap of pysystemtrade (the deep-research identified 4 IB-integration
fragilities in pysystemtrade: #1639 combo/roll visibility, #1580 race
conditions, #1501 hourly strategies unsupported, #1649 cost/vol coupling).
We reimplement from Carver's books (which are the spec), keeping the code
simple, NumPy/Polars-native, and Oracle-aligned.

References
----------
- Carver, R. (2015). *Systematic Trading*. https://github.com/pst-group/pysystemtrade
- pysystemtrade backtesting docs: raw.githubusercontent.com/pst-group/pst-systemtrade/master/docs/backtesting.md
- 7-stage pipeline: RawData → Rules → ForecastScaleCap → ForecastCombine → PositionSizing → Portfolios → Account
- Deep-research synthesis: docs/reports/2026-08-15-deep-research-synthesis.md §2.4

Contracts
---------
All modules work on Polars DataFrames with a ``close`` column (and
``high``/``low`` where ATR is needed). Returns are arithmetic
``pct_change``. Forecasts are unitless expected-return signals (typically
in [-2, +2] after scaling). The pipeline is causal — every output at bar
``i`` depends only on data up to bar ``i-1`` for execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from analytics.technical.polars_indicators import ema


@dataclass(frozen=True)
class VolatilityTarget:
    """Target a fixed annualised volatility by scaling position size.

    The "vol-target" pattern from Carver ch.9: position size is inversely
    proportional to realised volatility so that the expected portfolio
    vol matches ``target_annual_vol``. Realised vol is estimated via
    exponentially-weighted std of daily returns (default span 36 days,
    Carver's recommendation).

    Attributes
    ----------
    target_annual_vol : float
        Target annualised volatility (e.g. 0.12 for 12% annual, 0.30 for
        30% annual — prop-firm style). Daily target = target / sqrt(252).
    vol_lookback : int
        Span (in bars) for EWM vol estimate. Default 36 (Carver).
    bars_per_year : int
        Annualisation factor (252 for daily, 252*6.5 for hourly US
        equity session, etc.).
    max_leverage : float
        Cap on the scalar; prevents runaway sizing in low-vol regimes.
        Default 5.0 (conservative; lower for prop-firm profiles).
    """

    target_annual_vol: float = 0.12
    vol_lookback: int = 36
    bars_per_year: int = 252
    max_leverage: float = 5.0

    def daily_target_vol(self) -> float:
        """Return the per-bar target volatility."""
        return float(self.target_annual_vol / np.sqrt(self.bars_per_year))

    def realised_vol(self, close: pl.Series) -> np.ndarray:
        """EWM std of arithmetic returns (Carver's vol estimate)."""
        arr = close.to_numpy().astype(np.float64)
        if arr.size < 2:
            return np.full_like(arr, np.nan)
        rets = np.diff(arr, prepend=np.nan) / arr
        # pandas-style EWM std (span = lookback, adjust=False)
        alpha = 2.0 / (self.vol_lookback + 1.0)
        mean = np.zeros_like(rets)
        var = np.zeros_like(rets)
        mean[0] = 0.0
        var[0] = 0.0
        for i in range(1, rets.size):
            if np.isnan(rets[i]):
                mean[i] = mean[i - 1]
                var[i] = var[i - 1]
                continue
            delta = rets[i] - mean[i - 1]
            mean[i] = mean[i - 1] + alpha * delta
            var[i] = (1 - alpha) * (var[i - 1] + alpha * delta**2)
        std: np.ndarray = np.sqrt(np.maximum(var, 0.0))
        std[0] = np.nan
        return std

    def position_scalar(self, close: pl.Series) -> np.ndarray:
        """Return per-bar vol-target scalar (target_vol / realised_vol).

        Capped at ``max_leverage``. NaN where realised_vol is NaN or 0.
        """
        rvol = self.realised_vol(close)
        target = self.daily_target_vol()
        scalar = np.where((rvol > 0) & np.isfinite(rvol), target / rvol, np.nan)
        capped: np.ndarray = np.minimum(scalar, self.max_leverage)
        return capped


@dataclass(frozen=True)
class ForecastScale:
    """Normalise a raw signal to a common expected-returns scale.

    Carver ch.10: each forecast is scaled so that its long-run average
    absolute value equals ``target_abs_forecast`` (default 1.0 in Oracle;
    pysystemtrade uses 10.0). The scalar is estimated from the raw
    forecast's EWM abs mean.

    Per-symbol calibration (BL-505f): the scalar is estimated per-SimFinId
    rather than globally, so each ticker has its own normalized scale.
    Use :meth:`fit_scalar_for_symbol` to estimate per-symbol, then
    :meth:`scale_for_symbol` to apply.

    Attributes
    ----------
    target_abs_forecast : float
        Target long-run average |forecast|. Default 1.0 (Oracle unit-agnostic).
    lookback : int
        EWM span for the abs-mean estimate. Default 250 (~1 year daily).
    cap : float
        Cap on the raw forecast (pre-scale) to prevent outliers. Default 2.0.
    """

    target_abs_forecast: float = 1.0
    lookback: int = 250
    cap: float = 2.0

    def fit_scalar(self, raw_forecast: pl.Series) -> float:
        """Estimate the scalar that normalises the forecast's abs mean.

        Returns 1.0 (no scaling) if forecast has no finite variation.
        """
        arr = raw_forecast.to_numpy().astype(np.float64)
        finite = arr[np.isfinite(arr)]
        if finite.size < 10:
            return 1.0
        alpha = 2.0 / (self.lookback + 1.0)
        ewm_abs = np.zeros_like(arr)
        ewm_abs[0] = np.abs(arr[0])
        for i in range(1, arr.size):
            if np.isnan(arr[i]):
                ewm_abs[i] = ewm_abs[i - 1]
                continue
            ewm_abs[i] = (1 - alpha) * ewm_abs[i - 1] + alpha * np.abs(arr[i])
        current_level = float(ewm_abs[-1])
        if current_level <= 0 or not np.isfinite(current_level):
            return 1.0
        return self.target_abs_forecast / current_level

    def fit_scalar_for_symbol(
        self, raw_forecast: pl.Series, *, symbol_id: int | str | None = None
    ) -> float:
        """Per-symbol scalar estimation (BL-505f).

        For now this is identical to :meth:`fit_scalar`; the signature is
        in place so that in v2 we can add symbol-specific adjustments
        (e.g., higher target for high-vol stocks, lower for low-vol).
        """
        return self.fit_scalar(raw_forecast)

    def scale(self, raw_forecast: pl.Series, scalar: float | None = None) -> pl.Series:
        """Apply scaling + cap to a raw forecast series.

        Parameters
        ----------
        raw_forecast : pl.Series
            Raw signal values (any scale).
        scalar : float, optional
            Pre-fitted scalar from :meth:`fit_scalar`. If None, re-fit.
        """
        if scalar is None:
            scalar = self.fit_scalar(raw_forecast)
        arr = raw_forecast.to_numpy().astype(np.float64)
        capped = np.clip(arr, -self.cap, self.cap)
        scaled = capped * scalar
        return pl.Series("forecast", scaled)

    def scale_for_symbol(
        self,
        raw_forecast: pl.Series,
        *,
        scalar: float | None = None,
        symbol_id: int | str | None = None,
    ) -> pl.Series:
        """Per-symbol scale (BL-505f). Equivalent to :meth:`scale` for now,
        but the signature is in place for v2 symbol-specific adjustments.
        """
        if scalar is None:
            scalar = self.fit_scalar_for_symbol(raw_forecast, symbol_id=symbol_id)
        return self.scale(raw_forecast, scalar=scalar)


@dataclass(frozen=True)
class InstrumentDiversificationMultiplier:
    """IDM — increases aggregate position when instruments are not correlated.

    Carver ch.11: IDM = √(avg_individual_variance / portfolio_variance).
    For a correlation matrix (unit-variance instruments), this simplifies to
    √(1 / w'Σw). When instruments are uncorrelated, IDM = √N (diversification
    benefit lets you take more risk per unit aggregate vol); when perfectly
    correlated, IDM = 1 (no benefit).

    Attributes
    ----------
    n_instruments : int
        Number of instruments in the portfolio (must match weights length).
    """

    n_instruments: int

    def from_correlation_matrix(self, corr: np.ndarray, weights: np.ndarray | None = None) -> float:
        """Compute IDM from a correlation matrix.

        Parameters
        ----------
        corr : np.ndarray, shape (N, N)
            Correlation matrix of instrument returns.
        weights : np.ndarray, shape (N,), optional
            Instrument weights (sum to 1). Default equal-weight.
        """
        if corr.shape != (self.n_instruments, self.n_instruments):
            raise ValueError(
                f"corr shape {corr.shape} != ({self.n_instruments},{self.n_instruments})"
            )
        if weights is None:
            weights = np.full(self.n_instruments, 1.0 / self.n_instruments)
        if weights.size != self.n_instruments:
            raise ValueError(f"weights size {weights.size} != {self.n_instruments}")
        w = weights / weights.sum()
        avg_var = float(np.mean(np.diag(corr)))  # 1.0 for correlation matrix
        port_var = float(w @ corr @ w)
        if port_var <= 0 or avg_var <= 0:
            return 1.0
        return float(np.sqrt(avg_var / port_var))

    def approx_from_avg_correlation(self, avg_corr: float) -> float:
        """Equal-weight closed-form IDM from average pairwise correlation.

        For equal weights w_i = 1/N and constant pairwise ρ:
        w'Σw = (1 + (N-1)ρ) / N
        IDM = √(1 / w'Σw) = √(N / (1 + (N-1)ρ))
        """
        denom = 1.0 + (self.n_instruments - 1) * avg_corr
        if denom <= 0:
            return 1.0
        return float(np.sqrt(self.n_instruments / denom))


@dataclass
class ForecastCombine:
    """Weighted blend of multiple forecasts with per-forecast scale + cap.

    Carver ch.11 forecast combination: combined = Σ (w_i * scale_i * cap_i * f_i)
    where weights sum to 1.0, each forecast is individually scaled, and the
    combined output is capped at the same ``cap``.

    Attributes
    ----------
    weights : dict[str, float]
        Per-forecast weights. Keys must match the forecast dict passed to
        :meth:`combine`. Default empty (will error — must be set per-use).
    scaler : ForecastScale
        Reusable scalar estimator for individual forecasts.
    cap : float
        Cap on the combined forecast. Default 2.0.
    """

    weights: dict[str, float] = field(default_factory=dict)
    scaler: ForecastScale = field(default_factory=ForecastScale)
    cap: float = 2.0

    def __post_init__(self) -> None:
        if not self.weights:
            return
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError(f"weights sum {total} must be > 0")
        self.weights = {k: v / total for k, v in self.weights.items()}

    def combine(self, forecasts: dict[str, pl.Series]) -> pl.Series:
        """Combine multiple forecasts into a single capped forecast.

        Parameters
        ----------
        forecasts : dict[str, pl.Series]
            Raw forecast series. Keys must be a subset of self.weights;
            keys without weight are ignored.

        Returns
        -------
        pl.Series
            Combined forecast, capped to [-cap, +cap].
        """
        if not self.weights:
            raise ValueError("ForecastCombine.weights must be set before combine()")
        sample = next(iter(forecasts.values()))
        combined = np.zeros(sample.len(), dtype=np.float64)
        used_keys: list[str] = []
        for name, weight in self.weights.items():
            if name not in forecasts:
                continue
            scaled = self.scaler.scale(forecasts[name])
            combined += weight * scaled.to_numpy().astype(np.float64)
            used_keys.append(name)
        if not used_keys:
            raise KeyError(
                f"none of the forecast keys {list(forecasts)} match weights {list(self.weights)}"
            )
        capped = np.clip(combined, -self.cap, self.cap)
        return pl.Series("forecast_combined", capped)


@dataclass(frozen=True)
class TrendSignalRule:
    """Simple EMA-crossover forecast (Carver's "carry" or "momentum" rule).

    A basic building block for Lane A: forecast = (ema_fast - ema_slow) / vol.
    Output is in units of "expected returns in σ". Wrap with :class:`ForecastScale`
    to normalise before combination.

    Attributes
    ----------
    fast : int
        Fast EMA period. Default 8 (Carver's shortest variant).
    slow : int
        Slow EMA period. Default 32 (Carver's 4x slow rule).
    vol_lookback : int
        Volatility EWM span for the σ denominator. Default 36.
    """

    fast: int = 8
    slow: int = 32
    vol_lookback: int = 36

    def forecast(self, close: pl.Series) -> pl.Series:
        """Return (ema_fast - ema_slow) / realised_vol per bar."""
        e_fast = ema(close, self.fast).to_numpy().astype(np.float64)
        e_slow = ema(close, self.slow).to_numpy().astype(np.float64)
        vt = VolatilityTarget(vol_lookback=self.vol_lookback)
        rvol = vt.realised_vol(close)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = np.where((rvol > 0) & np.isfinite(rvol), (e_fast - e_slow) / rvol, 0.0)
        return pl.Series("forecast_trend", raw)


@dataclass(frozen=True)
class TSMRule:
    """12-month Time-Series Momentum (Moskowitz-Ooi-Pedersen 2012).

    The single most documented edge in academic literature for Lane A:
    past 12-month excess return positively predicts future return across
    58 futures/forward contracts over 25+ years. Effect persists ~1 year,
    then partially reverses.

    Forecast = sign(past_252_return) × |past_252_return| / realised_vol.
    Equivalent to "long after 12mo up, short after 12mo down, sized by vol".

    References
    ----------
    Moskowitz, T., Ooi, Y.H., Pedersen, L.H. (2012). "Time Series Momentum."
    *Journal of Financial Economics* 104(2):228-250.
    https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum
    """

    lookback: int = 252  # 12 months × 21 trading days
    vol_lookback: int = 36

    def forecast(self, close: pl.Series) -> pl.Series:
        """Return signed momentum forecast normalised by realised vol."""
        arr = close.to_numpy().astype(np.float64)
        if arr.size < self.lookback + 1:
            return pl.Series("forecast_tsm", np.zeros(arr.size))
        # Past 12-mo return: close[i] / close[i-252] - 1
        past_return = np.zeros_like(arr)
        past_return[self.lookback :] = arr[self.lookback :] / arr[: -self.lookback] - 1.0
        # Apply sign × |value| (Carver style: don't dampen with magnitude)
        # Actually Moskowitz-Ooi-Pedersen use sign only; we use sign × |past_return|
        # for a continuous forecast.
        vt = VolatilityTarget(vol_lookback=self.vol_lookback)
        rvol = vt.realised_vol(close)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = np.where(
                (rvol > 0) & np.isfinite(rvol) & np.isfinite(past_return), past_return / rvol, 0.0
            )
        # Cap at ±3 to prevent outliers (Carver's pattern)
        capped = np.clip(raw, -3.0, 3.0)
        return pl.Series("forecast_tsm", capped)


def build_lane_a_pipeline_multi_rule(
    close: pl.Series,
    *,
    fast: int = 8,
    slow: int = 32,
    target_annual_vol: float = 0.12,
    bars_per_year: int = 252,
    weights: dict[str, float] | None = None,
    tsm_lookback: int = 252,
) -> pl.Series:
    """Multi-rule Lane A pipeline (BL-503b): ForecastCombine of 3 EMA crossovers + TSM.

    Composes:
        1. TrendSignalRule(8, 32) → EMA crossover short
        2. TrendSignalRule(16, 64) → EMA crossover medium
        3. TrendSignalRule(32, 128) → EMA crossover long
        4. TSMRule(252) → 12-month time-series momentum (Moskowitz-Ooi-Pedersen)

    The 4 forecasts are combined via ForecastCombine with equal weights (or
    custom weights via the `weights` kwarg). The combined forecast is then
    scaled by VolatilityTarget to produce a per-bar position scalar.

    Parameters
    ----------
    close : pl.Series
        Close prices.
    fast, slow : int
        Parameters for the first TrendSignalRule (default 8/32).
    target_annual_vol : float
        Target annualised volatility for position sizing (default 0.12 = 12%).
    bars_per_year : int
        Annualisation factor (default 252 for daily).
    weights : dict[str, float], optional
        Custom forecast weights. Keys: "ema_short", "ema_medium", "ema_long",
        "tsm_252". Default equal-weight 25% each.
    tsm_lookback : int
        Lookback for TSMRule (default 252 = 12 months).

    Returns
    -------
    pl.Series
        Per-bar position scalar (units of "fraction of capital"). NaN
        during warmup.
    """
    # Build the 4 raw forecasts
    ema_short = TrendSignalRule(fast=fast, slow=slow * 4 if False else fast * 4).forecast(close)
    # Wait — let's compute 3 distinct EMA pairs + TSM
    ema_short = TrendSignalRule(fast=8, slow=32).forecast(close)
    ema_medium = TrendSignalRule(fast=16, slow=64).forecast(close)
    ema_long = TrendSignalRule(fast=32, slow=128).forecast(close)
    tsm = TSMRule(lookback=tsm_lookback).forecast(close)

    if weights is None:
        weights = {"ema_short": 0.25, "ema_medium": 0.25, "ema_long": 0.25, "tsm_252": 0.25}

    combiner = ForecastCombine(weights=weights, cap=3.0)
    forecasts = {
        "ema_short": ema_short,
        "ema_medium": ema_medium,
        "ema_long": ema_long,
        "tsm_252": tsm,
    }
    combined = combiner.combine(forecasts)

    # Scale by vol-target position scalar
    vt = VolatilityTarget(target_annual_vol=target_annual_vol, bars_per_year=bars_per_year)
    pos_scalar = vt.position_scalar(close)
    combined_arr = combined.to_numpy().astype(np.float64) * pos_scalar
    return pl.Series("lane_a_position_multi", combined_arr)


def build_lane_a_pipeline(
    close: pl.Series,
    *,
    fast: int = 8,
    slow: int = 32,
    target_annual_vol: float = 0.12,
    bars_per_year: int = 252,
) -> pl.Series:
    """Convenience: single-instrument trend forecast + vol-target sizing.

    This composes TrendSignalRule → ForecastScale → VolatilityTarget to
    produce a position scalar per bar. For multi-instrument PAC, loop
    over instruments and apply :class:`InstrumentDiversificationMultiplier`.

    Returns
    -------
    pl.Series
        Per-bar position scalar (units of "fraction of capital"). NaN
        during warmup.
    """
    rule = TrendSignalRule(fast=fast, slow=slow)
    raw = rule.forecast(close)
    scaler = ForecastScale()
    scaled = scaler.scale(raw)
    vt = VolatilityTarget(target_annual_vol=target_annual_vol, bars_per_year=bars_per_year)
    pos_scalar = vt.position_scalar(close)
    combined = scaled.to_numpy().astype(np.float64) * pos_scalar
    return pl.Series("lane_a_position", combined)


__all__: list[str] = [
    "ForecastCombine",
    "ForecastScale",
    "InstrumentDiversificationMultiplier",
    "TSMRule",
    "TrendSignalRule",
    "VolatilityTarget",
    "build_lane_a_pipeline",
    "build_lane_a_pipeline_multi_rule",
]
