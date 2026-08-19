"""Lane D VRP backtest — historical Black-Scholes premium simulation.

Step 2 Opzione C (2026-08-16). Pure-Python backtest of short-put VRP strategy
on historical SPY + VIX data, NO IBKR connection required.

Strategy (BL-507 spec):
1. Each trading day t (Mon-Wed only to avoid event risk):
   - VIX_t (FRED ^VIX close, free, 1990+) = implied vol proxy
   - RV_forward_30d = realised vol of SPY from t to t+30 calendar days
   - VRP_t = VIX_t/100 - RV_forward_30d
2. Open short put position:
   - Strike = SPY_t × (1 - OTM_pct)  where OTM_pct derived from target delta
   - DTE = 30 calendar days
   - Premium = Black-Scholes put price (BSM formula) with IV=VIX_t/100
3. Exit rules (Tastytrade / 50%-profit-15%-loss standard):
   - Close at 50% of max profit (premium decayed to 50% of initial)
   - Roll at 20% loss (premium doubled)
   - Hard exit at DTE=7 (avoid pin risk)
4. Track P&L per position + portfolio equity curve
5. Compute Sharpe, return, max DD, hit rate, tail-risk scenarios

Why this backtest matters
- Live Lane D (`lane_d_vrip.py`) only generates signals — no P&L tracking
- This module answers: "If I had run the VRP strategy 2010-2025, what would
  the Sharpe have been?" — with realistic BS-estimated premiums, exit rules,
  and tail events.

References
- Carr & Wu (2009) — Variance Risk Premiums, Rev. Financial Studies
- Bollerslev, Tauchen, Zhou (2009) — Expected Stock Returns and VRP
- Hull (2018) ch.15 — Black-Scholes-Merton formula
- AQR "Selling Volatility" white paper
- Deep-research synthesis 2026-08-15 §2.7
- ADR-019 §3 (Lane D as part of personal portfolio blend)

Limitations (v1)
- BS assumes log-normal returns (no jump-diffusion) → underestimates tail
- VIX as IV proxy is index-level, not strike-specific (real IV is skewed)
- No transaction costs (real: ~$0.65/contract IBKR paper, negligible for SPY)
- No early-exercise / assignment risk (American-style options rarely optimal early)
- Backtest is monthly-roll, not daily (premium captured once per 30-DTE cycle)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import polars as pl

# Constants for Black-Scholes
_SQRT_2PI = math.sqrt(2.0 * math.pi)


# ---------------------------------------------------------------------------
# Black-Scholes put pricing
# ---------------------------------------------------------------------------


def _norm_cdf(x: float) -> float:
    """Cumulative distribution function of standard normal.

    Abramowitz & Stegun 7.1.26 approximation (max error 7.5e-8).
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def black_scholes_put(
    spot: float, strike: float, dte_days: float, iv: float, r: float = 0.04, q: float = 0.015
) -> float:
    """Black-Scholes put price (no dividends if q=0).

    Parameters
    ----------
    spot : float
        Current underlying price S.
    strike : float
        Strike price K.
    dte_days : float
        Days to expiration (calendar). Converted to T = dte/365.
    iv : float
        Implied volatility as fraction (0.20 = 20%).
    r : float
        Risk-free rate (default 4% — 10y Treasury average).
    q : float
        Dividend yield (default 1.5% — SPY long-run average).

    Returns
    -------
    float
        Put option price in same units as spot/strike.
    """
    if dte_days <= 0.0:
        # At expiry: max(K-S, 0)
        return max(strike - spot, 0.0)
    T = dte_days / 365.0
    if iv <= 0.0:
        # No vol → put = discounted intrinsic
        return max(strike - spot, 0.0) * math.exp(-r * T)
    vol_sqrt_t = iv * math.sqrt(T)
    if vol_sqrt_t < 1e-10:
        return max(strike - spot, 0.0) * math.exp(-r * T)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    # Put = K e^{-rT} N(-d2) - S e^{-qT} N(-d1)
    put = strike * math.exp(-r * T) * _norm_cdf(-d2) - spot * math.exp(-q * T) * _norm_cdf(-d1)
    return max(put, 0.0)


def black_scholes_put_delta(
    spot: float, strike: float, dte_days: float, iv: float, r: float = 0.04, q: float = 0.015
) -> float:
    """Put delta in [-1, 0]."""
    if dte_days <= 0.0 or iv <= 0.0:
        return -1.0 if spot < strike else 0.0
    T = dte_days / 365.0
    vol_sqrt_t = iv * math.sqrt(T)
    if vol_sqrt_t < 1e-10:
        return -1.0 if spot < strike else 0.0
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * T) / vol_sqrt_t
    return math.exp(-q * T) * (_norm_cdf(d1) - 1.0)


def strike_for_target_delta(
    spot: float, target_delta: float, dte_days: float, iv: float, r: float = 0.04, q: float = 0.015
) -> float:
    """Find strike K such that put delta = -target_delta (negative).

    Bisection on [0.5*spot, 0.999*spot]. Returns the strike.
    Target delta is given as positive magnitude (e.g. 0.20 → put delta -0.20).
    """
    target = -abs(target_delta)
    lo, hi = spot * 0.50, spot * 0.999
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        d = black_scholes_put_delta(spot, mid, dte_days, iv, r, q)
        if d < target:
            # delta too negative → strike too close to spot, move strike DOWN
            hi = mid
        else:
            # delta not negative enough → strike too deep OTM, move strike UP
            lo = mid
        if abs(d - target) < 1e-3:
            break
    return 0.5 * (lo + hi)


def _put_delta_at_strike(
    spot: float, strike: float, dte_days: float, iv: float, r: float, q: float
) -> float:
    return black_scholes_put_delta(spot, strike, dte_days, iv, r, q)


# ---------------------------------------------------------------------------
# Data loading — FRED VIX + yfinance SPY
# ---------------------------------------------------------------------------


def _load_vix(start: date, end: date) -> pl.DataFrame:
    """Load VIX daily close from FRED (series VIXCLS, free, 1990+).

    Returns DataFrame with columns: date (Date), vix_close (Float64).
    """
    try:
        from analytics.macro.fred import FREDClient
    except ImportError as exc:
        raise RuntimeError(
            "FRED client not available; install with: uv add httpx (analytics.macro.fred)"
        ) from exc

    import asyncio

    async def _fetch() -> pl.DataFrame:
        async with FREDClient() as c:
            df = await c.fetch_series("VIXCLS", start=start, end=end)
        return df

    try:
        df = asyncio.run(_fetch())
    except (RuntimeError, Exception):
        # Fallback: try yfinance ^VIX (limited to 730 days intraday but full daily)
        # Covers RuntimeError (asyncio), MacroError (FRED_API_KEY unset), ImportError.
        return _load_vix_yfinance(start, end)
    if df is None or df.height == 0:
        return _load_vix_yfinance(start, end)

    # Normalise column names + filter dates
    df = df.rename({col: col.lower() for col in df.columns})
    if "value" in df.columns:
        df = df.rename({"value": "vix_close"})
    if "date" not in df.columns:
        # Try first column
        df = df.rename({df.columns[0]: "date"})
    df = df.with_columns(pl.col("date").cast(pl.Date))
    df = df.filter((pl.col("date") >= start) & (pl.col("date") <= end))
    df = df.filter(pl.col("vix_close").is_not_null())
    return df.select(["date", "vix_close"])


def _load_vix_yfinance(start: date, end: date) -> pl.DataFrame:
    """Fallback VIX via yfinance (^VIX index, free, full daily history)."""
    import yfinance as yf

    t = yf.Ticker("^VIX")
    df_pd = t.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    if df_pd is None or df_pd.empty:
        return pl.DataFrame(schema={"date": pl.Date, "vix_close": pl.Float64})
    df_pd = df_pd.reset_index()
    df_pd["date"] = df_pd["Date"].dt.date if "Date" in df_pd.columns else df_pd.index.date
    return pl.DataFrame(
        {"date": df_pd["date"].tolist(), "vix_close": df_pd["Close"].astype(float).tolist()}
    )


def _load_spy(start: date, end: date) -> pl.DataFrame:
    """Load SPY daily OHLCV from yfinance (free, 1993+)."""
    import yfinance as yf

    t = yf.Ticker("SPY")
    df_pd = t.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    if df_pd is None or df_pd.empty:
        return pl.DataFrame(schema={"date": pl.Date, "close": pl.Float64})
    df_pd = df_pd.reset_index()
    df_pd["date"] = df_pd["Date"].dt.date if "Date" in df_pd.columns else df_pd.index.date
    return pl.DataFrame(
        {
            "date": df_pd["date"].tolist(),
            "open": df_pd["Open"].astype(float).tolist(),
            "high": df_pd["High"].astype(float).tolist(),
            "low": df_pd["Low"].astype(float).tolist(),
            "close": df_pd["Close"].astype(float).tolist(),
        }
    )


# ---------------------------------------------------------------------------
# VRP backtest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VRPBacktestConfig:
    """Configuration for the VRP historical backtest."""

    target_dte: int = 30
    target_delta: float = 0.20
    otm_pct: float = 0.05  # Fallback: 5% OTM if delta-to-strike fails
    position_size_pct: float = 0.02  # 2% of equity per trade (cash-secured)
    max_concurrent: int = 5
    exit_dte: int = 7  # Hard exit before pin risk
    take_profit_pct: float = 0.50  # Close at 50% of max profit
    roll_loss_pct: float = 0.20  # Roll at 20% loss (premium doubled)
    risk_free_rate: float = 0.04
    dividend_yield: float = 0.015
    # Trade entry cadence: every N trading days (1 = daily, 5 = weekly)
    entry_cadence_days: int = 5
    # Avoid trading on Mondays (event risk, weekend gap)
    avoid_mondays: bool = True


@dataclass
class VRPPosition:
    """One open short-put position."""

    open_date: date
    expiry_date: date
    strike: float
    premium_received: float
    spot_at_open: float
    iv_at_open: float
    dte_at_open: int
    contracts: int = 1
    close_date: date | None = None
    close_reason: str = ""  # "profit", "roll", "dte_exit", "expiry", "tail"
    pnl: float = 0.0
    premium_at_close: float = 0.0


@dataclass
class VRPBacktestResult:
    """Aggregated result of a VRP backtest run."""

    n_trades: int
    n_open_trades_at_end: int
    positions: list[VRPPosition]
    equity_curve: np.ndarray
    trade_returns: np.ndarray  # per-trade fractional return
    total_return: float
    annual_return: float
    sharpe: float | None
    max_drawdown: float
    hit_rate: float
    avg_premium_pct: float  # avg premium / spot at open
    avg_dte_held: float
    exit_breakdown: dict[str, int]
    tail_events: list[VRPPosition]  # trades with pnl < -1× premium (100% loss)


class VRPBacktester:
    """Backtester for short-put VRP strategy on historical SPY + VIX.

    Algorithm (per entry day):
        1. Read VIX close → IV
        2. Compute strike for target_delta (or OTM_pct fallback)
        3. BS put price = premium received (×100 for 1 contract)
        4. Hold day-by-day, recompute BS put with remaining DTE
        5. Exit on first of: 50% profit / 20% loss / DTE=7 / expiry
        6. P&L = (premium_received - premium_at_close) × 100 × contracts

    Risk model:
        - 1 contract = 100 shares → collateral = strike × 100
        - Position size: position_size_pct × equity / collateral_per_contract
        - This means more contracts when equity grows (compounding)
    """

    def __init__(
        self, spy_df: pl.DataFrame, vix_df: pl.DataFrame, config: VRPBacktestConfig | None = None
    ) -> None:
        self.config = config or VRPBacktestConfig()
        # Inner join SPY + VIX on date — both must be present for trade day
        self.spy = spy_df.sort("date").unique(subset=["date"])
        self.vix = vix_df.sort("date").unique(subset=["date"])
        self.data = self.spy.join(self.vix, on="date", how="inner").sort("date")
        if self.data.height == 0:
            raise ValueError("VRPBacktester: SPY and VIX have no overlapping dates")

    def run(self, start: date, end: date, initial_capital: float = 100_000.0) -> VRPBacktestResult:
        """Run the backtest from start to end (inclusive)."""
        cfg = self.config
        dates = self.data.filter((pl.col("date") >= start) & (pl.col("date") <= end))[
            "date"
        ].to_list()
        if not dates:
            return self._empty_result()

        # Build lookup: date → (spy_close, vix_close)
        rows: dict[date, tuple[float, float]] = {
            r["date"]: (float(r["close"]), float(r["vix_close"]))
            for r in self.data.filter(
                (pl.col("date") >= start) & (pl.col("date") <= end)
            ).iter_rows(named=True)
        }

        equity = initial_capital
        peak = equity
        max_dd = 0.0
        open_positions: list[VRPPosition] = []
        closed_positions: list[VRPPosition] = []
        equity_curve: list[float] = []
        # Track equity for charting (per trading day)
        last_trade_day_i = -cfg.entry_cadence_days  # ensure first eligible day trades

        for i, d in enumerate(dates):
            spy_close, vix_close = rows[d]
            iv = vix_close / 100.0  # VIX is in vol points (e.g. 15.5 = 15.5%)

            # Mark-to-market open positions
            for pos in open_positions:
                remaining_dte = (pos.expiry_date - d).days
                if remaining_dte < 0:
                    remaining_dte = 0
                # Re-price the put with current spot + IV + remaining DTE
                # Note: IV at close uses current VIX (simplification — real IV
                # is strike-specific and would require historical options chain)
                cur_premium = (
                    black_scholes_put(
                        spot=spy_close,
                        strike=pos.strike,
                        dte_days=float(remaining_dte),
                        iv=iv,
                        r=cfg.risk_free_rate,
                        q=cfg.dividend_yield,
                    )
                    * 100.0
                    * pos.contracts
                )
                pos.premium_at_close = cur_premium

                # Exit rules
                profit_pct = (
                    1.0 - (cur_premium / pos.premium_received) if pos.premium_received > 0 else 0.0
                )
                loss_pct = (
                    (cur_premium / pos.premium_received) - 1.0 if pos.premium_received > 0 else 0.0
                )

                if profit_pct >= cfg.take_profit_pct:
                    pos.close_date = d
                    pos.close_reason = "profit"
                    pos.pnl = pos.premium_received - cur_premium
                elif loss_pct >= cfg.roll_loss_pct:
                    pos.close_date = d
                    pos.close_reason = "roll"
                    pos.pnl = pos.premium_received - cur_premium
                elif remaining_dte <= cfg.exit_dte:
                    pos.close_date = d
                    pos.close_reason = "dte_exit"
                    pos.pnl = pos.premium_received - cur_premium
                elif remaining_dte == 0:
                    # Expiry: payoff = max(K - S, 0) × 100 × contracts
                    intrinsic = max(pos.strike - spy_close, 0.0) * 100.0 * pos.contracts
                    pos.close_date = d
                    pos.close_reason = "expiry"
                    pos.pnl = pos.premium_received - intrinsic

            # Settle closed positions → equity
            newly_closed = [p for p in open_positions if p.close_date == d]
            for p in newly_closed:
                equity += p.pnl
                closed_positions.append(p)
            open_positions = [p for p in open_positions if p.close_date is None]

            # Tail event tracking: loss > 1× premium received
            # (i.e. we lost more than 100% of premium)
            for p in newly_closed:
                if p.pnl < -p.premium_received:
                    pass  # tracked below after we collect all

            # Open new position if cadence + weekday + max_concurrent satisfied
            weekday = d.weekday()  # 0=Mon, 6=Sun
            if cfg.avoid_mondays and weekday == 0:
                eligible_today = False
            else:
                eligible_today = (i - last_trade_day_i) >= cfg.entry_cadence_days
            if eligible_today and len(open_positions) < cfg.max_concurrent and d < end:
                # Compute strike for target delta
                try:
                    strike = strike_for_target_delta(
                        spot=spy_close,
                        target_delta=cfg.target_delta,
                        dte_days=float(cfg.target_dte),
                        iv=iv,
                        r=cfg.risk_free_rate,
                        q=cfg.dividend_yield,
                    )
                except Exception:
                    strike = spy_close * (1.0 - cfg.otm_pct)

                premium_per_share = black_scholes_put(
                    spot=spy_close,
                    strike=strike,
                    dte_days=float(cfg.target_dte),
                    iv=iv,
                    r=cfg.risk_free_rate,
                    q=cfg.dividend_yield,
                )
                if premium_per_share <= 0:
                    # Skip pathological cases
                    pass
                else:
                    premium_received = premium_per_share * 100.0  # 1 contract
                    collateral_per_contract = strike * 100.0
                    # Position sizing: % of equity per contract
                    target_notional = cfg.position_size_pct * equity
                    contracts = max(1, int(target_notional // collateral_per_contract))
                    expiry = d + timedelta(days=cfg.target_dte)
                    pos = VRPPosition(
                        open_date=d,
                        expiry_date=expiry,
                        strike=strike,
                        premium_received=premium_received * contracts,
                        spot_at_open=spy_close,
                        iv_at_open=iv,
                        dte_at_open=cfg.target_dte,
                        contracts=contracts,
                    )
                    open_positions.append(pos)
                    last_trade_day_i = i
                    # Premium received is a credit; equity unchanged at open
                    # (collateral reserved, not deducted from equity for simplicity)

            # Track equity (mark-to-market)
            mtm_pnl = sum(p.pnl for p in closed_positions if p.close_date == d)
            unrealised = sum(
                p.premium_received - p.premium_at_close
                for p in open_positions
                if p.premium_at_close > 0
            )
            equity_today = equity + unrealised
            equity_curve.append(equity_today)
            peak = max(peak, equity_today)
            dd = (equity_today - peak) / peak if peak > 0 else 0.0
            max_dd = min(max_dd, dd)

        # Close any remaining open positions at last date
        last_d = dates[-1]
        spy_close, _ = rows[last_d]
        for p in open_positions:
            remaining = max((p.expiry_date - last_d).days, 0)
            cur_premium = (
                black_scholes_put(
                    spot=spy_close,
                    strike=p.strike,
                    dte_days=float(remaining),
                    iv=0.20,  # flat IV at end
                    r=cfg.risk_free_rate,
                    q=cfg.dividend_yield,
                )
                * 100.0
                * p.contracts
            )
            p.close_date = last_d
            p.close_reason = "end_of_backtest"
            p.pnl = p.premium_received - cur_premium
            closed_positions.append(p)

        # Aggregate
        n_trades = len(closed_positions)
        trade_returns = np.array(
            [
                (p.pnl / p.premium_received) if p.premium_received > 0 else 0.0
                for p in closed_positions
            ]
        )
        total_return = float(equity / initial_capital - 1.0) if initial_capital > 0 else 0.0
        n_days = len(dates)
        years = n_days / 252.0 if n_days > 0 else 0.0
        annual_return = float((1.0 + total_return) ** (1.0 / years) - 1.0) if years > 0 else 0.0
        if trade_returns.size > 1 and trade_returns.std() > 0:
            sharpe = float(
                trade_returns.mean()
                / trade_returns.std(ddof=1)
                * math.sqrt(252.0 / cfg.entry_cadence_days)
            )
        else:
            sharpe = None
        hit_rate = (
            float(np.mean([1.0 if r > 0 else 0.0 for r in trade_returns]))
            if trade_returns.size > 0
            else 0.0
        )
        avg_premium_pct = (
            float(
                np.mean(
                    [
                        (p.premium_received / (p.strike * 100.0 * p.contracts))
                        if p.contracts > 0
                        else 0.0
                        for p in closed_positions
                    ]
                )
            )
            if closed_positions
            else 0.0
        )
        avg_dte_held = (
            float(
                np.mean(
                    [
                        (p.close_date - p.open_date).days if p.close_date else 0
                        for p in closed_positions
                    ]
                )
            )
            if closed_positions
            else 0.0
        )
        exit_breakdown: dict[str, int] = {}
        for p in closed_positions:
            exit_breakdown[p.close_reason] = exit_breakdown.get(p.close_reason, 0) + 1
        tail_events = [p for p in closed_positions if p.pnl < -p.premium_received]

        return VRPBacktestResult(
            n_trades=n_trades,
            n_open_trades_at_end=0,
            positions=closed_positions,
            equity_curve=np.array(equity_curve),
            trade_returns=trade_returns,
            total_return=total_return,
            annual_return=annual_return,
            sharpe=sharpe,
            max_drawdown=max_dd,
            hit_rate=hit_rate,
            avg_premium_pct=avg_premium_pct,
            avg_dte_held=avg_dte_held,
            exit_breakdown=exit_breakdown,
            tail_events=tail_events,
        )

    def _empty_result(self) -> VRPBacktestResult:
        return VRPBacktestResult(
            n_trades=0,
            n_open_trades_at_end=0,
            positions=[],
            equity_curve=np.array([]),
            trade_returns=np.array([]),
            total_return=0.0,
            annual_return=0.0,
            sharpe=None,
            max_drawdown=0.0,
            hit_rate=0.0,
            avg_premium_pct=0.0,
            avg_dte_held=0.0,
            exit_breakdown={},
            tail_events=[],
        )


__all__ = [
    "VRPBacktestConfig",
    "VRPBacktestResult",
    "VRPBacktester",
    "VRPPosition",
    "black_scholes_put",
    "black_scholes_put_delta",
    "strike_for_target_delta",
]
