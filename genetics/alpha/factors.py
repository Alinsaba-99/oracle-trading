"""50 curated alpha factors organized by category.

Each factor is a standalone function operating on OHLCV data
represented as a Polars DataFrame with columns:
    timestamp, open, high, low, close, volume

All functions handle edge cases: NaN/Inf → 0.0, constant series → zeros,
short series → zeros.
"""

from __future__ import annotations

import numpy as np
import polars as pl

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_fill(series: pl.Series) -> pl.Series:
    """Replace NaN/Inf with 0.0."""
    s = series.fill_nan(0.0).to_numpy().astype(np.float64, copy=True)
    s[~np.isfinite(s)] = 0.0
    return pl.Series(series.name, s)


def _constant_or_short(series: pl.Series, min_periods: int = 2) -> bool:
    """Return True if the series is constant or shorter than min_periods."""
    if len(series) < min_periods:
        return True
    # Check if all values are the same (within float tolerance)
    arr = series.to_numpy()
    if len(arr) == 0:
        return True
    return bool(np.nanmax(arr) == np.nanmin(arr)) if np.all(np.isfinite(arr)) else False


def _returns(close: pl.Series) -> pl.Series:
    """Daily log returns."""
    return close.log() - close.shift(1).log()


def _sma(series: pl.Series, period: int) -> pl.Series:
    """Simple moving average."""
    return series.rolling_mean(window_size=period)


def _rolling_std(series: pl.Series, period: int) -> pl.Series:
    """Rolling standard deviation (ddof=1)."""
    return series.rolling_std(window_size=period, ddof=1)


def _rolling_cov(s1: pl.Series, s2: pl.Series, window: int) -> pl.Series:
    """Rolling sample covariance using the variance identity.

    cov(X, Y) = (Var(X+Y) - Var(X) - Var(Y)) / 2
    Uses ddof=1 for sample covariance.
    """
    var_sum = (s1 + s2).rolling_var(window_size=window, ddof=1)
    var_1 = s1.rolling_var(window_size=window, ddof=1)
    var_2 = s2.rolling_var(window_size=window, ddof=1)
    return (var_sum - var_1 - var_2) / 2.0


def _rolling_corr(s1: pl.Series, s2: pl.Series, window: int) -> pl.Series:
    """Rolling sample correlation.

    corr(X, Y) = cov(X, Y) / (std(X) * std(Y))
    Uses ddof=1 for sample statistics.
    """
    cov = _rolling_cov(s1, s2, window)
    std_1 = s1.rolling_std(window_size=window, ddof=1)
    std_2 = s2.rolling_std(window_size=window, ddof=1)
    return cov / (std_1 * std_2)


# ---------------------------------------------------------------------------
# Momentum (10)
# ---------------------------------------------------------------------------


def roc_1m(data: pl.DataFrame) -> pl.Series:
    """Rate of change over 1 month (~21 trading days).

    ROC = (close / shift(close, 21)) - 1
    """
    close = data["close"]
    if _constant_or_short(close, 22):
        return pl.Series("roc_1m", [0.0] * len(close))
    result = close / close.shift(21) - 1.0
    return _safe_fill(result)


def roc_3m(data: pl.DataFrame) -> pl.Series:
    """Rate of change over 3 months (~63 trading days)."""
    close = data["close"]
    if _constant_or_short(close, 64):
        return pl.Series("roc_3m", [0.0] * len(close))
    result = close / close.shift(63) - 1.0
    return _safe_fill(result)


def roc_6m(data: pl.DataFrame) -> pl.Series:
    """Rate of change over 6 months (~126 trading days)."""
    close = data["close"]
    if _constant_or_short(close, 127):
        return pl.Series("roc_6m", [0.0] * len(close))
    result = close / close.shift(126) - 1.0
    return _safe_fill(result)


def roc_12m(data: pl.DataFrame) -> pl.Series:
    """Rate of change over 12 months (~252 trading days)."""
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("roc_12m", [0.0] * len(close))
    result = close / close.shift(252) - 1.0
    return _safe_fill(result)


def mom_1m_exc_last(data: pl.DataFrame) -> pl.Series:
    """1-month momentum excluding the last trading day.

    ROC computed over shift(2)..shift(22) — i.e., skip the most recent day.
    Equivalent to: close[-22:-1] / close[-1] but as a lookback from
    shift(22) to shift(2).
    """
    close = data["close"]
    if _constant_or_short(close, 23):
        return pl.Series("mom_1m_exc_last", [0.0] * len(close))
    # Close 22 days ago divided by close 2 days ago -> exclude last day
    result = close.shift(22) / close.shift(2) - 1.0
    return _safe_fill(result)


def mom_reversal(data: pl.DataFrame) -> pl.Series:
    """Short-term reversal factor.

    Negative of 1-day return.  When today's return is positive,
    the signal is negative (expect reversal), and vice versa.
    """
    close = data["close"]
    if _constant_or_short(close, 2):
        return pl.Series("mom_reversal", [0.0] * len(close))
    ret_1d = close.pct_change()
    result = -ret_1d
    return _safe_fill(result)


def weighted_mom(data: pl.DataFrame) -> pl.Series:
    """Weighted average of multiple momentum horizons.

    Combines 1m, 3m, 6m, 12m ROC with linearly decaying weights
    (4, 3, 2, 1) — more weight on shorter horizons.
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("weighted_mom", [0.0] * len(close))
    r1 = close / close.shift(21) - 1.0
    r3 = close / close.shift(63) - 1.0
    r6 = close / close.shift(126) - 1.0
    r12 = close / close.shift(252) - 1.0
    w_sum = (
        4.0 * r1.fill_nan(0.0)
        + 3.0 * r3.fill_nan(0.0)
        + 2.0 * r6.fill_nan(0.0)
        + 1.0 * r12.fill_nan(0.0)
    )
    result = w_sum / 10.0
    return _safe_fill(result)


def exponential_mom(data: pl.DataFrame) -> pl.Series:
    """Exponentially-weighted momentum.

    Uses an EWMA of daily returns with halflife=21, then sums
    the weighted returns over the lookback.
    """
    close = data["close"]
    if _constant_or_short(close, 2):
        return pl.Series("exponential_mom", [0.0] * len(close))
    ret = close.pct_change().fill_nan(0.0)
    # EWMA of returns
    alpha = 2.0 / (21.0 + 1.0)
    arr = ret.to_numpy().astype(np.float64, copy=True)
    out = np.full_like(arr, np.nan)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    result = pl.Series("_ewma_ret", out)
    return _safe_fill(result)


def momentum_trend(data: pl.DataFrame) -> pl.Series:
    """Momentum of momentum — acceleration of trend.

    Change in 21-day ROC over the last 5 days.
    Positive when momentum is accelerating upward.
    """
    close = data["close"]
    if _constant_or_short(close, 27):
        return pl.Series("momentum_trend", [0.0] * len(close))
    roc_21d = close / close.shift(21) - 1.0
    result = roc_21d - roc_21d.shift(5)
    return _safe_fill(result)


def momentum_stability(data: pl.DataFrame) -> pl.Series:
    """Stability of positive momentum.

    Ratio of positive return days to total days over the last 63 days.
    Range [0, 1]; higher = more consistent upward moves.
    """
    close = data["close"]
    if _constant_or_short(close, 64):
        return pl.Series("momentum_stability", [0.0] * len(close))
    ret = close.pct_change()
    pos = ret > 0.0
    pos_count = pos.cast(pl.Float64).rolling_mean(window_size=63).fill_nan(0.0)
    result = pos_count
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Mean-reversion (8)
# ---------------------------------------------------------------------------


def rsi_14(data: pl.DataFrame) -> pl.Series:
    """Relative Strength Index (Wilder smoothing, period=14).

    RSI = 100 - 100 / (1 + RS)
    where RS = average gain / average loss over 14 periods.
    Uses Wilder's smoothed averaging.
    """
    close = data["close"]
    if _constant_or_short(close, 15):
        return pl.Series("rsi_14", [0.0] * len(close))

    arr = close.to_numpy().astype(np.float64, copy=False)
    deltas = np.diff(arr, prepend=np.nan)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    period = 14
    avg_gain = np.full_like(arr, np.nan)
    avg_loss = np.full_like(arr, np.nan)

    avg_gain[period] = np.mean(gains[1 : period + 1])
    avg_loss[period] = np.mean(losses[1 : period + 1])

    for i in range(period + 1, len(arr)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = np.full_like(avg_gain, np.nan)
    # When avg_loss is 0 (pure uptrend), RS is effectively infinite -> RSI=100
    zero_loss = avg_loss == 0.0
    zero_gain = avg_gain == 0.0
    # Both zero -> neutral RSI=50
    rs[zero_loss & zero_gain] = 1.0
    # Only loss zero -> infinite RS, clamp to 999 -> RSI ~99.9
    rs[zero_loss & ~zero_gain] = 999.0
    # Normal case
    normal = ~zero_loss
    rs[normal] = avg_gain[normal] / avg_loss[normal]
    rsi_values = 100.0 - (100.0 / (1.0 + rs))
    result = pl.Series("rsi_14", rsi_values)
    return _safe_fill(result)


def bb_position(data: pl.DataFrame) -> pl.Series:
    """Position within Bollinger Bands.

    (close - sma_20) / (2 * std_20)
    Normalised: +1 = at upper band, -1 = at lower band, 0 = at midline.
    """
    close = data["close"]
    if _constant_or_short(close, 21):
        return pl.Series("bb_position", [0.0] * len(close))
    sma_20 = close.rolling_mean(window_size=20)
    std_20 = close.rolling_std(window_size=20, ddof=1)
    result = (close - sma_20) / (2.0 * std_20)
    return _safe_fill(result)


def distance_from_sma_20(data: pl.DataFrame) -> pl.Series:
    """Percentage distance from 20-day SMA.

    (close - sma_20) / sma_20
    Positive when price is above the moving average.
    """
    close = data["close"]
    if _constant_or_short(close, 21):
        return pl.Series("distance_from_sma_20", [0.0] * len(close))
    sma_20 = close.rolling_mean(window_size=20)
    result = (close - sma_20) / sma_20
    return _safe_fill(result)


def distance_from_sma_50(data: pl.DataFrame) -> pl.Series:
    """Percentage distance from 50-day SMA."""
    close = data["close"]
    if _constant_or_short(close, 51):
        return pl.Series("distance_from_sma_50", [0.0] * len(close))
    sma_50 = close.rolling_mean(window_size=50)
    result = (close - sma_50) / sma_50
    return _safe_fill(result)


def zscore_20(data: pl.DataFrame) -> pl.Series:
    """20-day z-score of close price.

    (close - sma_20) / std_20
    Measures how many standard deviations price is from its mean.
    """
    close = data["close"]
    if _constant_or_short(close, 21):
        return pl.Series("zscore_20", [0.0] * len(close))
    sma_20 = close.rolling_mean(window_size=20)
    std_20 = close.rolling_std(window_size=20, ddof=1)
    result = (close - sma_20) / std_20
    return _safe_fill(result)


def mean_reversion_speed(data: pl.DataFrame) -> pl.Series:
    """Speed of mean reversion.

    Half-life of the autocorrelation of daily returns estimated
    over a 60-day window.  Shorter half-life → faster mean reversion.
    Approximated as: -log(2) / log(|rho_1|)
    where rho_1 is the lag-1 autocorrelation of returns.
    """
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("mean_reversion_speed", [0.0] * len(close))

    ret = close.pct_change()
    # Rolling lag-1 autocorrelation via corr(ret, lag(ret))
    rho_1 = _rolling_corr(ret, ret.shift(1), window=60).fill_nan(0.0)
    # Clip to avoid log(0) or log(|r|>1)
    abs_rho = rho_1.abs().clip(1e-10, 0.9999)
    half_life = -np.log(2.0) / abs_rho.log()
    # Invert: faster reversion → higher factor value
    result = 1.0 / half_life
    return _safe_fill(result)


def serial_correlation(data: pl.DataFrame) -> pl.Series:
    """Serial correlation of daily returns (lag-1) over 20 days.

    Positive serial correlation → trend; negative → mean reversion.
    """
    close = data["close"]
    if _constant_or_short(close, 22):
        return pl.Series("serial_correlation", [0.0] * len(close))
    ret = close.pct_change()
    result = _rolling_corr(ret, ret.shift(1), window=20)
    return _safe_fill(result)


def idiosyncratic_reversion(data: pl.DataFrame) -> pl.Series:
    """Idiosyncratic mean reversion.

    Residual from a rolling market-model regression (close ~ equal-weight
    market proxy).  Negative of the residual — stocks that overshot
    downward are expected to revert up.
    """
    close = data["close"]
    if _constant_or_short(close, 22):
        return pl.Series("idiosyncratic_reversion", [0.0] * len(close))

    # Use equal-weight cross-sectional mean as market proxy
    # (when only one series, use smoothed close as proxy)
    sma_20 = close.rolling_mean(window_size=20).fill_nan(0.0)
    # Residual: actual minus smooth trend
    residual = close - sma_20
    # Negative because we expect overshoots to revert
    result = -residual / close
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Volatility (6)
# ---------------------------------------------------------------------------


def atr_14(data: pl.DataFrame) -> pl.Series:
    """Average True Range (Wilder smoothing, period=14), normalised by close.

    ATR_14 / close — gives a percentage measure of volatility.
    """
    high = data["high"]
    low = data["low"]
    close = data["close"]
    if _constant_or_short(high, 15) or _constant_or_short(close, 15):
        return pl.Series("atr_14", [0.0] * len(close))
    low_arr = low.to_numpy().astype(np.float64, copy=False)
    h = high.to_numpy().astype(np.float64, copy=False)
    c = close.to_numpy().astype(np.float64, copy=False)

    prev_c = np.roll(c, 1)
    prev_c[0] = np.nan

    tr = np.maximum(h - low_arr, np.maximum(np.abs(h - prev_c), np.abs(low_arr - prev_c)))
    out = np.full_like(tr, np.nan)

    period = 14
    out[period - 1] = np.nanmean(tr[:period])
    for i in range(period, len(tr)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period

    atr_series = pl.Series("_atr", out)
    result = atr_series / close
    return _safe_fill(result)


def bb_width(data: pl.DataFrame) -> pl.Series:
    """Bollinger Band width.

    (upper_band - lower_band) / sma_20
    Measures relative volatility — wider bands = more volatile.
    """
    close = data["close"]
    if _constant_or_short(close, 21):
        return pl.Series("bb_width", [0.0] * len(close))
    sma_20 = close.rolling_mean(window_size=20)
    std_20 = close.rolling_std(window_size=20, ddof=1)
    upper = sma_20 + 2.0 * std_20
    lower = sma_20 - 2.0 * std_20
    result = (upper - lower) / sma_20
    return _safe_fill(result)


def historical_vol_20(data: pl.DataFrame) -> pl.Series:
    """20-day historical volatility (annualized).

    std(log_returns) * sqrt(252)
    """
    close = data["close"]
    if _constant_or_short(close, 21):
        return pl.Series("historical_vol_20", [0.0] * len(close))
    log_ret = close.log() - close.shift(1).log()
    result = log_ret.rolling_std(window_size=20, ddof=1) * np.sqrt(252.0)
    return _safe_fill(result)


def historical_vol_60(data: pl.DataFrame) -> pl.Series:
    """60-day historical volatility (annualized)."""
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("historical_vol_60", [0.0] * len(close))
    log_ret = close.log() - close.shift(1).log()
    result = log_ret.rolling_std(window_size=60, ddof=1) * np.sqrt(252.0)
    return _safe_fill(result)


def parkinson_vol(data: pl.DataFrame) -> pl.Series:
    """Parkinson's volatility estimator (20-day).

    sigma = sqrt(1 / (4 * ln(2)) * mean((ln(high/low))^2))
    Uses high/low range, more efficient than close-to-close.
    Reference: Parkinson (1980).
    """
    high = data["high"]
    low = data["low"]
    if _constant_or_short(high, 21):
        return pl.Series("parkinson_vol", [0.0] * len(high))

    hl_ratio = (high / low).log()
    hl_sq = hl_ratio.pow(2)
    mean_hl_sq = hl_sq.rolling_mean(window_size=20)
    factor = 1.0 / (4.0 * np.log(2.0))
    result = (mean_hl_sq * factor).sqrt()
    return _safe_fill(result)


def yang_zhang_vol(data: pl.DataFrame) -> pl.Series:
    """Yang-Zhang volatility estimator (20-day).

    Combines overnight, open-close, and high-low volatility.
    sigma^2 = sigma_overnight^2 + k * sigma_openclose^2 + (1-k) * sigma_parkinson^2
    where k = 0.34 / (1.34 + (n+1)/(n-1))
    Reference: Yang & Zhang (2000).
    """
    open_p = data["open"]
    high = data["high"]
    low = data["low"]
    close = data["close"]
    if _constant_or_short(close, 22):
        return pl.Series("yang_zhang_vol", [0.0] * len(close))

    n = 20.0
    k = 0.34 / (1.34 + (n + 1.0) / (n - 1.0))

    # Overnight volatility: ln(open / prev_close)
    overnight_ret = open_p.log() - close.shift(1).log()
    sigma_overnight_sq = overnight_ret.pow(2).rolling_mean(window_size=20)

    # Open-close volatility: ln(close / open)
    oc_ret = close.log() - open_p.log()
    sigma_oc_sq = oc_ret.pow(2).rolling_mean(window_size=20)

    # Parkinson volatility
    hl_ratio = (high / low).log()
    parkinson_var = hl_ratio.pow(2).rolling_mean(window_size=20) / (4.0 * np.log(2.0))

    result = (sigma_overnight_sq + k * sigma_oc_sq + (1.0 - k) * parkinson_var).sqrt()
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Correlation (6)
# ---------------------------------------------------------------------------


def corr_to_spy(data: pl.DataFrame) -> pl.Series:
    """Rolling 60-day correlation of returns to a market proxy.

    Uses the equal-weight cross-sectional average of returns as proxy
    (when only one instrument, uses smoothed returns).
    """
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("corr_to_spy", [0.0] * len(close))

    ret = close.pct_change()
    # Market proxy: smoothed returns (SMA(5) of returns)
    market_ret = ret.rolling_mean(window_size=5)
    result = _rolling_corr(ret, market_ret, window=60)
    return _safe_fill(result)


def corr_to_sector(data: pl.DataFrame) -> pl.Series:
    """Rolling 60-day correlation to a sector proxy.

    Similar to corr_to_spy but uses a longer smoothing for the sector proxy.
    """
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("corr_to_sector", [0.0] * len(close))

    ret = close.pct_change()
    # Sector proxy: slower smoothed returns (SMA(20))
    sector_ret = ret.rolling_mean(window_size=20)
    result = _rolling_corr(ret, sector_ret, window=60)
    return _safe_fill(result)


def corr_stability(data: pl.DataFrame) -> pl.Series:
    """Stability of market correlation.

    Standard deviation of 60-day rolling correlation over the last year.
    Lower values mean more stable correlation (more reliable beta).
    """
    close = data["close"]
    if _constant_or_short(close, 252):
        return pl.Series("corr_stability", [0.0] * len(close))

    ret = close.pct_change()
    market_ret = ret.rolling_mean(window_size=5)
    rolling_corr = _rolling_corr(ret, market_ret, window=60)
    # Volatility of the correlation itself
    corr_vol = rolling_corr.rolling_std(window_size=252, ddof=1)
    # Negative -> stable correlation = higher factor value
    result = -corr_vol
    return _safe_fill(result)


def beta_60(data: pl.DataFrame) -> pl.Series:
    """60-day market beta.

    Covariance(returns, market_returns) / variance(market_returns)
    Uses SMA(5) of returns as market proxy.
    """
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("beta_60", [0.0] * len(close))

    ret = close.pct_change()
    market_ret = ret.rolling_mean(window_size=5)

    cov = _rolling_cov(ret, market_ret, window=60)
    var = market_ret.rolling_var(window_size=60, ddof=1)
    result = cov / var
    return _safe_fill(result)


def beta_120(data: pl.DataFrame) -> pl.Series:
    """120-day market beta."""
    close = data["close"]
    if _constant_or_short(close, 121):
        return pl.Series("beta_120", [0.0] * len(close))

    ret = close.pct_change()
    market_ret = ret.rolling_mean(window_size=5)

    cov = _rolling_cov(ret, market_ret, window=120)
    var = market_ret.rolling_var(window_size=120, ddof=1)
    result = cov / var
    return _safe_fill(result)


def idiosyncratic_vol(data: pl.DataFrame) -> pl.Series:
    """Idiosyncratic volatility — residual vol after market adjustment.

    Standard deviation of the residual from a rolling market regression
    (returns ~ market returns) over 60 days.
    """
    close = data["close"]
    if _constant_or_short(close, 61):
        return pl.Series("idiosyncratic_vol", [0.0] * len(close))

    ret = close.pct_change()
    market_ret = ret.rolling_mean(window_size=5)

    cov = _rolling_cov(ret, market_ret, window=60)
    var = market_ret.rolling_var(window_size=60, ddof=1)
    beta = cov / var

    # Residual returns
    residual = ret - beta * market_ret
    result = residual.rolling_std(window_size=60, ddof=1) * np.sqrt(252.0)
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Volume (5)
# ---------------------------------------------------------------------------


def volume_zscore_20(data: pl.DataFrame) -> pl.Series:
    """20-day volume z-score.

    (volume - sma_20(volume)) / std_20(volume)
    High positive = unusually high volume.
    """
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(volume, 21):
        return pl.Series("volume_zscore_20", [0.0] * len(volume))

    sma_v = volume.rolling_mean(window_size=20)
    std_v = volume.rolling_std(window_size=20, ddof=1)
    result = (volume - sma_v) / std_v
    return _safe_fill(result)


def volume_trend(data: pl.DataFrame) -> pl.Series:
    """Volume trend — slope of log-volume over 20 days.

    Positive = volume increasing over time (accumulation).
    """
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(volume, 21):
        return pl.Series("volume_trend", [0.0] * len(volume))

    log_vol = volume.log()
    # Simple linear trend: 20-day ROC of log-volume divided by 20
    result = (log_vol - log_vol.shift(20)) / 20.0
    return _safe_fill(result)


def dollar_volume(data: pl.DataFrame) -> pl.Series:
    """Dollar volume (close * volume), normalized by SMA(20).

    Proxy for liquidity — higher = more liquid.
    """
    close = data["close"]
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(close, 21) or _constant_or_short(volume, 21):
        return pl.Series("dollar_volume", [0.0] * len(close))

    dv = close * volume
    sma_dv = dv.rolling_mean(window_size=20)
    result = dv / sma_dv
    return _safe_fill(result)


def turnover(data: pl.DataFrame) -> pl.Series:
    """Turnover — volume divided by rolling average volume.

    (volume / sma_60(volume))
    High turnover relative to normal indicates unusual activity.
    """
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(volume, 61):
        return pl.Series("turnover", [0.0] * len(volume))

    sma_v = volume.rolling_mean(window_size=60)
    result = volume / sma_v
    return _safe_fill(result)


def volume_vs_avg(data: pl.DataFrame) -> pl.Series:
    """Volume vs average — ratio of current volume to 20-day average.

    Similar to turnover but shorter horizon.
    """
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(volume, 21):
        return pl.Series("volume_vs_avg", [0.0] * len(volume))

    sma_v = volume.rolling_mean(window_size=20)
    result = volume / sma_v
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Seasonality (5)
# ---------------------------------------------------------------------------


def month_effect(data: pl.DataFrame) -> pl.Series:
    """Month-of-year effect (causal expanding window — no look-ahead bias).

    For each bar, assigns the average return of that calendar month computed
    from all *previous* occurrences of the same month.
    """
    close = data["close"]
    ts = data["timestamp"]
    if _constant_or_short(close, 2) or len(ts) == 0:
        return pl.Series("month_effect", [0.0] * len(close))

    ret = close.pct_change().fill_nan(0.0).to_numpy()
    month_arr = ts.dt.month().to_numpy()
    n = len(ret)
    out = np.zeros(n)
    month_sum: dict[int, float] = {}
    month_cnt: dict[int, int] = {}
    for i in range(n):
        m = int(month_arr[i])
        s = month_sum.get(m, 0.0)
        c = month_cnt.get(m, 0)
        out[i] = s / c if c > 0 else 0.0
        month_sum[m] = s + ret[i]
        month_cnt[m] = c + 1
    return _safe_fill(pl.Series("month_effect", out))


def day_of_week(data: pl.DataFrame) -> pl.Series:
    """Day-of-week effect (causal expanding window — no look-ahead bias).

    For each bar, assigns the average return of that weekday computed
    from all *previous* occurrences of the same weekday.
    """
    close = data["close"]
    ts = data["timestamp"]
    if _constant_or_short(close, 2) or len(ts) == 0:
        return pl.Series("day_of_week", [0.0] * len(close))

    ret = close.pct_change().fill_nan(0.0).to_numpy()
    dow_arr = ts.dt.weekday().to_numpy()
    n = len(ret)
    out = np.zeros(n)
    dow_sum: dict[int, float] = {}
    dow_cnt: dict[int, int] = {}
    for i in range(n):
        d = int(dow_arr[i])
        s = dow_sum.get(d, 0.0)
        c = dow_cnt.get(d, 0)
        out[i] = s / c if c > 0 else 0.0
        dow_sum[d] = s + ret[i]
        dow_cnt[d] = c + 1
    return _safe_fill(pl.Series("day_of_week", out))


def quarter_effect(data: pl.DataFrame) -> pl.Series:
    """Quarter-of-year effect (causal expanding window — no look-ahead bias).

    For each bar, assigns the average return of that calendar quarter computed
    from all *previous* occurrences of the same quarter.
    """
    close = data["close"]
    ts = data["timestamp"]
    if _constant_or_short(close, 2) or len(ts) == 0:
        return pl.Series("quarter_effect", [0.0] * len(close))

    ret = close.pct_change().fill_nan(0.0).to_numpy()
    quarter_arr = ((ts.dt.month().cast(pl.Int64) - 1) // 3 + 1).to_numpy()
    n = len(ret)
    out = np.zeros(n)
    q_sum: dict[int, float] = {}
    q_cnt: dict[int, int] = {}
    for i in range(n):
        q = int(quarter_arr[i])
        s = q_sum.get(q, 0.0)
        c = q_cnt.get(q, 0)
        out[i] = s / c if c > 0 else 0.0
        q_sum[q] = s + ret[i]
        q_cnt[q] = c + 1
    return _safe_fill(pl.Series("quarter_effect", out))


def turning_month(data: pl.DataFrame) -> pl.Series:
    """Turning-of-the-month effect.

    Indicator: +1 for the last 3 and first 3 trading days of each month,
    0 otherwise.
    """
    close = data["close"]
    ts = data["timestamp"]
    if len(close) == 0 or len(ts) == 0:
        return pl.Series("turning_month", [0.0] * len(close))

    month = ts.dt.month()
    month_arr = month.to_numpy()
    out = np.zeros(len(close))

    # Find month boundaries
    for i in range(len(close)):
        # First 3 days of month
        if i < 3 or month_arr[i] != month_arr[i - 1]:
            # Mark this and next 2 days if same month
            out[i] = 1.0
            if i + 1 < len(close) and month_arr[i + 1] == month_arr[i]:
                out[i + 1] = 1.0
            if i + 2 < len(close) and month_arr[i + 2] == month_arr[i]:
                out[i + 2] = 1.0
        # Last 3 days of month
        if i >= len(close) - 1 or month_arr[i] != (month_arr[i + 1] if i + 1 < len(close) else -1):
            out[i] = 1.0
            if i - 1 >= 0 and month_arr[i - 1] == month_arr[i]:
                out[i - 1] = 1.0
            if i - 2 >= 0 and month_arr[i - 2] == month_arr[i]:
                out[i - 2] = 1.0

    result = pl.Series("turning_month", out.clip(0.0, 1.0))
    return _safe_fill(result)


def january_effect(data: pl.DataFrame) -> pl.Series:
    """January effect indicator.

    +1 in January, 0 otherwise.  Based on the well-known January effect
    anomaly (small caps tend to outperform in January).
    """
    ts = data["timestamp"]
    close = data["close"]
    if len(ts) == 0 or len(close) == 0:
        return pl.Series("january_effect", [0.0] * len(close))

    month = ts.dt.month()
    result = (month == 1).cast(pl.Float64)
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Fundamental proxies (5) — price-derived proxies
# ---------------------------------------------------------------------------


def div_yield(data: pl.DataFrame) -> pl.Series:
    """Dividend yield proxy.

    Estimated from price drops on ex-dividend dates.
    Uses 252-day rolling sum of negative daily returns capped at 0
    as a rough proxy.  In practice, dividend yield = dividends / price.
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("div_yield", [0.0] * len(close))

    ret = close.pct_change()
    # Negative returns as proxy for dividend drops
    neg_ret = ret.clip(upper_bound=0.0)
    # Rolling sum of negative returns over 1 year
    result = -neg_ret.rolling_sum(window_size=252)
    return _safe_fill(result)


def earnings_yield(data: pl.DataFrame) -> pl.Series:
    """Earnings yield proxy.

    Proxy: 1 / (price / sma_252(price)) i.e., inverse of trailing P/E.
    When price is above its 1-year average, earnings yield is low (expensive).
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("earnings_yield", [0.0] * len(close))

    sma_252 = close.rolling_mean(window_size=252)
    pe_ratio = close / sma_252
    result = 1.0 / pe_ratio
    return _safe_fill(result)


def book_to_price(data: pl.DataFrame) -> pl.Series:
    """Book-to-price proxy.

    Proxy: sma_252(close) / close = 1 / (price / book)
    where book value is proxied by 1-year average price.
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("book_to_price", [0.0] * len(close))

    sma_252 = close.rolling_mean(window_size=252)
    result = sma_252 / close
    return _safe_fill(result)


def cash_flow_yield(data: pl.DataFrame) -> pl.Series:
    """Cash flow yield proxy.

    Proxy: (close - sma_252(close)) / sma_252(close)
    relative to rolling price — approximates cash flow generation.
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("cash_flow_yield", [0.0] * len(close))

    sma_252 = close.rolling_mean(window_size=252)
    # Cash flow proxy: deviation from average price
    result = (close - sma_252) / sma_252
    return _safe_fill(result)


def payout_ratio(data: pl.DataFrame) -> pl.Series:
    """Payout ratio proxy.

    Proxy: dividend_yield / earnings_yield
    Ratio of dividend proxy to earnings proxy.
    """
    close = data["close"]
    if _constant_or_short(close, 253):
        return pl.Series("payout_ratio", [0.0] * len(close))

    ret = close.pct_change()
    neg_ret = ret.clip(upper_bound=0.0)
    div_proxy = -neg_ret.rolling_sum(window_size=252)

    sma_252 = close.rolling_mean(window_size=252)
    earnings_proxy = 1.0 / (close / sma_252)

    result = div_proxy / earnings_proxy
    return _safe_fill(result)


# ---------------------------------------------------------------------------
# Microstructure (5)
# ---------------------------------------------------------------------------


def bid_ask_spread_est(data: pl.DataFrame) -> pl.Series:
    """Bid-ask spread estimate using Roll's model (1984).

    Spread = 2 * sqrt(-cov(delta_price, delta_price_lag_1))
    where delta_price = close - previous close.
    Uses 20-day rolling covariance.
    """
    close = data["close"]
    if _constant_or_short(close, 22):
        return pl.Series("bid_ask_spread_est", [0.0] * len(close))

    dp = close.diff()
    cov = _rolling_cov(dp, dp.shift(1), window=20)
    # Roll spread estimate: 2 * sqrt(max(0, -cov))
    pos_cov = cov.clip(upper_bound=0.0)  # only negative covariances
    result = 2.0 * (-pos_cov).sqrt()
    return _safe_fill(result)


def amihud_illiquidity(data: pl.DataFrame) -> pl.Series:
    """Amihud illiquidity ratio (2002).

    Average of |return| / dollar_volume over a 20-day window.
    Higher values = more illiquid.
    Reference: Amihud (2002), "Illiquidity and stock returns".
    """
    close = data["close"]
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(close, 21) or _constant_or_short(volume, 21):
        return pl.Series("amihud_illiquidity", [0.0] * len(close))

    ret = close.pct_change().abs()
    dollar_vol = close * volume
    # Avoid division by zero
    dollar_vol_safe = dollar_vol.clip(lower_bound=1e-8)
    illiq = ret / dollar_vol_safe
    result = illiq.rolling_mean(window_size=20) * 1e6  # scale for readability
    return _safe_fill(result)


def roll_impact(data: pl.DataFrame) -> pl.Series:
    """Roll impact measure.

    Price impact proxy: absolute return / dollar volume (similar to
    Amihud but using a single-day measure rather than rolling average).
    """
    close = data["close"]
    volume = data["volume"].cast(pl.Float64)
    if _constant_or_short(close, 2) or _constant_or_short(volume, 2):
        return pl.Series("roll_impact", [0.0] * len(close))

    ret = close.pct_change().abs()
    dollar_vol = (close * volume).clip(lower_bound=1e-8)
    result = ret / dollar_vol * 1e6
    return _safe_fill(result)


def lot_size_adj(data: pl.DataFrame) -> pl.Series:
    """Lot size adjustment factor.

    Inverse of price — lower-priced stocks typically have larger
    lot sizes (more shares per unit of capital).
    """
    close = data["close"]
    if _constant_or_short(close, 2):
        return pl.Series("lot_size_adj", [0.0] * len(close))

    result = 1.0 / close.clip(lower_bound=0.01)
    return _safe_fill(result)


def price_reversal_1d(data: pl.DataFrame) -> pl.Series:
    """One-day price reversal.

    Today's return minus yesterday's return.
    Measures short-term reversal patterns in microstructure.
    """
    close = data["close"]
    if _constant_or_short(close, 3):
        return pl.Series("price_reversal_1d", [0.0] * len(close))

    ret = close.pct_change()
    result = ret - ret.shift(1)
    return _safe_fill(result)
