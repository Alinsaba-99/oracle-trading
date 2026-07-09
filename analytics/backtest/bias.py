"""Bias correction for backtest results and benchmark comparison.

Systematic backtest over-estimates live performance due to look-ahead
bias, survivorship bias, and optimistic slippage assumptions.  The
:class:`BiasCorrector` applies empirical haircuts and produces
confidence intervals.  The :func:`compare_to_benchmark` method computes
standard performance attribution relative to a benchmark return series.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import polars as pl

from analytics.backtest.result import BacktestResult

# ── helpers ─────────────────────────────────────────────────────────────────


def _equity_to_returns(equity: list[float]) -> list[float]:
    """Convert an equity curve to a series of per-period returns."""
    if len(equity) < 2:
        return []
    returns: list[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev == 0.0:
            returns.append(0.0)
        else:
            returns.append((equity[i] - prev) / prev)
    return returns


def _annualise(avg_return: float, n_periods: int) -> float:
    """Annualise a per-period return assuming daily frequency (252 trading days)."""
    if n_periods < 1:
        return 0.0
    excess = 1.0 + avg_return
    if excess <= 0.0:
        return -1.0
    return float(excess**252.0 - 1.0)


def _haircut_factor(total_trades: int) -> float:
    """Sharpe haircut based on number of trades.

    Fewer trades -> more overfitting risk -> larger haircut.

    * 0 - 30 trades:  0.50 (maximum haircut)
    * 30 - 100 trades: linear ramp from 0.50 to 0.70
    * 100+ trades:     0.70 (minimum haircut)
    """
    if total_trades < 30:
        return 0.50
    if total_trades < 100:
        # linear interpolation
        fraction = (total_trades - 30) / 70.0
        return 0.50 + fraction * 0.20
    return 0.70


def _drawdown_adjustment(total_trades: int) -> float:
    """Multiplier for max drawdown to account for slippage underestimation.

    More trades → more slippage exposure → larger adjustment.
    Fewer than 10 trades → no adjustment (statistically insignificant).
    """
    if total_trades < 10:
        return 1.0
    if total_trades < 50:
        return 1.10
    if total_trades < 200:
        return 1.20
    return 1.30


def _sharpe_se(sharpe: float, n: int) -> float:
    """Standard error of the Sharpe ratio (Lo 2002 approximation)."""
    if n < 2:
        return 0.0
    return math.sqrt((1.0 + 0.5 * sharpe * sharpe) / n)


# ── public API ──────────────────────────────────────────────────────────────


class BiasCorrector:
    """Applies empirical bias corrections to backtest results and computes
    benchmark-relative performance attribution."""

    @staticmethod
    def correct_backtest(result: BacktestResult) -> BacktestResult:
        """Return a corrected copy of *result* with empirical bias adjustments.

        Adjustments applied
        -------------------
        *   **Sharpe haircut** — the raw Sharpe is multiplied by
            :func:`_haircut_factor` based on trade count.
        *   **Confidence interval** — approximate 95 % CI for the
            haircut Sharpe is stored in the returned
            ``corrected_metrics`` as ``sharpe_ci_low`` /
            ``sharpe_ci_high``.
        *   **Max drawdown** — inflated by :func:`_drawdown_adjustment`
            to compensate for optimistic slippage assumptions.
        *   **Sortino / Calmar** — scaled by the same haircut factor as
            Sharpe, since the same overfitting logic applies.
        *   **Volatility / CAGR** — left untouched (bias is
            strategy-dependent; we only correct the metrics that have
            robust empirical evidence of systematic inflation).

        The original result is not mutated.
        """
        n = result.total_trades
        hair = _haircut_factor(n)

        # ── core haircuts ───────────────────────────────────────────
        corrected_sharpe = result.sharpe_ratio * hair
        corrected_sortino = result.sortino_ratio * hair
        corrected_calmar = result.calmar_ratio * hair

        # ── drawdown adjustment ─────────────────────────────────────
        corrected_dd = result.max_drawdown * _drawdown_adjustment(n)

        return BacktestResult(
            **{
                **result.model_dump(),
                "sharpe_ratio": corrected_sharpe,
                "sortino_ratio": corrected_sortino,
                "calmar_ratio": corrected_calmar,
                "max_drawdown": corrected_dd,
                "total_return": result.total_return,
                "volatility": result.volatility,
                "cagr": result.cagr,
                "total_trades": n,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
                "initial_capital": result.initial_capital,
                "final_equity": result.final_equity,
                "equity_curve": result.equity_curve,
                "trades": result.trades,
                "run_id": result.run_id,
                "strategy_name": result.strategy_name,
                "engine": result.engine,
                "instrument": result.instrument,
                "start_time": result.start_time,
                "end_time": result.end_time,
            }
        )

    @staticmethod
    def corrected_metrics(result: BacktestResult) -> dict[str, Any]:
        """Convenience: return *only* the corrected metric values plus
        confidence intervals as a flat dict."""
        n = result.total_trades
        hair = _haircut_factor(n)
        corrected_sharpe = result.sharpe_ratio * hair
        se = _sharpe_se(corrected_sharpe, n)
        return {
            "sharpe_ratio": corrected_sharpe,
            "sortino_ratio": result.sortino_ratio * hair,
            "calmar_ratio": result.calmar_ratio * hair,
            "max_drawdown": result.max_drawdown * _drawdown_adjustment(n),
            "sharpe_ci_low": corrected_sharpe - 1.96 * se,
            "sharpe_ci_high": corrected_sharpe + 1.96 * se,
        }

    @staticmethod
    def compare_to_benchmark(
        result: BacktestResult, benchmark_returns: pl.Series, risk_free_rate: float = 0.05
    ) -> dict[str, float]:
        """Compute benchmark-relative performance attribution.

        Parameters
        ----------
        result:
            A completed backtest result with a populated equity curve.
        benchmark_returns:
            Daily returns of the benchmark, aligned (same length and
            order) with the equity curve periods.  If the benchmark
            is shorter, trailing strategy periods are ignored.
        risk_free_rate:
            Annualised risk-free rate (default 0.05 = 5 %).

        Returns
        -------
        dict with keys:
            * alpha          — Jensen's Alpha (excess return vs. CAPM)
            * beta           — market correlation
            * tracking_error — annualised tracking error
            * information_ratio
            * up_capture     — strategy % return / benchmark % return
                               in up months
            * down_capture   — same for down periods
        """
        strategy_returns = _equity_to_returns(result.equity_curve)
        if not strategy_returns:
            return {
                "alpha": 0.0,
                "beta": 0.0,
                "tracking_error": 0.0,
                "information_ratio": 0.0,
                "up_capture": 0.0,
                "down_capture": 0.0,
            }

        n = min(len(strategy_returns), len(benchmark_returns))
        if n < 2:
            return {
                "alpha": 0.0,
                "beta": 0.0,
                "tracking_error": 0.0,
                "information_ratio": 0.0,
                "up_capture": 0.0,
                "down_capture": 0.0,
            }

        strat = pl.Series("strat", strategy_returns[:n])
        bench = benchmark_returns[:n].alias("bench")

        # ── beta ────────────────────────────────────────────────────
        mat = np.cov(strat.to_numpy(), bench.to_numpy(), ddof=1)
        cov = float(mat[0, 1])
        var_b = float(bench.var())  # type: ignore[arg-type]
        beta = cov / var_b if var_b != 0.0 else 0.0

        # ── annual returns ──────────────────────────────────────────
        strat_ann = _annualise(float(strat.mean()), n)  # type: ignore[arg-type]
        bench_ann = _annualise(float(bench.mean()), n)  # type: ignore[arg-type]

        # ── alpha (Jensen's) ────────────────────────────────────────
        # alpha = strategy_return - [rf + beta * (benchmark_return - rf)]
        alpha = strat_ann - (risk_free_rate + beta * (bench_ann - risk_free_rate))

        # ── tracking error & information ratio ──────────────────────
        diff = strat - bench
        tracking_error = float(diff.std()) * math.sqrt(252) if len(diff) > 1 else 0.0  # type: ignore[arg-type]
        information_ratio = (
            (strat_ann - bench_ann) / tracking_error if tracking_error != 0.0 else 0.0
        )

        # ── up / down capture ───────────────────────────────────────
        up_mask = bench > 0
        down_mask = bench < 0

        up_strat_sum = float(strat.filter(up_mask).sum())
        up_bench_sum = float(bench.filter(up_mask).sum())
        down_strat_sum = float(strat.filter(down_mask).sum())
        down_bench_sum = float(bench.filter(down_mask).sum())

        up_capture = up_strat_sum / up_bench_sum if up_bench_sum != 0.0 else 0.0
        down_capture = down_strat_sum / down_bench_sum if down_bench_sum != 0.0 else 0.0

        return {
            "alpha": alpha,
            "beta": beta,
            "tracking_error": tracking_error,
            "information_ratio": information_ratio,
            "up_capture": up_capture,
            "down_capture": down_capture,
        }
