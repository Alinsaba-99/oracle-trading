"""Cross-engine regression: VectorizedEngine vs NautilusEngine on SMA crossover.

Both engines should produce broadly similar results on the same signal
and data within the tolerances defined below:

*   Sharpe ratio agrees within +/-10 % (relative).
*   Final equity agrees within +/-5 % (relative).
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.nautilus import NautilusEngine
from analytics.backtest.engines.vectorized import VectorizedEngine, sma_crossover_signal
from analytics.backtest.result import BacktestResult

# ── helpers ─────────────────────────────────────────────────────────────────


def _n_dates(n: int, start: datetime | None = None) -> pl.Series:
    """Return a Polars datetime series with *n* daily intervals."""
    if start is None:
        start = datetime(2020, 1, 1, tzinfo=UTC)
    from datetime import timedelta

    end = start + timedelta(days=n)
    return pl.datetime_range(
        start=start,
        end=end,
        interval="1d",
        eager=True,
        closed="left",  # type: ignore[arg-type]
    )


def _synthetic_equity_data(n: int = 500, seed: int = 42) -> pl.DataFrame:
    """Synthetic OHLCV data compatible with the test_nautilus_engine pattern.

    Uses ``np.random.seed`` / ``np.random.randn`` (legacy NumPy RNG) to
    produce exactly the same series as the existing cross-engine test in
    ``test_nautilus_engine.py``.

    OHLCV consistency: low <= open <= high, low <= close <= high is
    guaranteed (open/high/low are monotonic offsets of close).
    """
    np.random.seed(seed)
    close = 100.0 * np.exp(np.random.randn(n).cumsum() * 0.02)

    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": pl.Series(close * 0.99),
            "high": pl.Series(close * 1.02),
            "low": pl.Series(close * 0.98),
            "close": pl.Series(close),
            "volume": pl.Series(np.random.randint(1_000_000, 5_000_000, n)),
        }
    )


# ── cross-engine regression tests ───────────────────────────────────────────


class TestCrossEngineConsistency:
    """VectorizedEngine and NautilusEngine must agree on SMA crossover.

    Zero commission/slippage is used because the two engines apply
    costs differently (vectorbt subtracts from returns, nautilus
    deducts from cash), which introduces systematic divergence.
    The core execution logic (entry/exit timing, position sizing)
    is what we want to validate.

    With n=1000 the engines converge more closely than n=500 because
    the slow SMA (200) leaves 800 active bars, generating multiple
    signal flips whose differences average out.
    """

    def test_sharpe_within_tolerance(self) -> None:
        """Sharpe ratio between engines agrees within +/-10 %."""
        data = _synthetic_equity_data(n=1000)
        signal = sma_crossover_signal(fast=50, slow=200)
        cfg = BacktestConfig(initial_capital=100_000, commission_pct=0.0, slippage_bps=0.0)

        vect_result = VectorizedEngine().run(data, signal, cfg)
        naut_result = NautilusEngine().run(data, signal, cfg)

        assert vect_result.total_trades > 0, "Vectorized produced zero trades"
        assert naut_result.total_trades > 0, "Nautilus produced zero trades"

        if vect_result.sharpe_ratio != 0:
            diff_pct = abs(naut_result.sharpe_ratio - vect_result.sharpe_ratio) / abs(
                vect_result.sharpe_ratio
            )
            assert diff_pct <= 0.10, (
                f"Sharpe ratio differs by {diff_pct * 100:.2f}% "
                f"(nautilus={naut_result.sharpe_ratio:.4f}, "
                f"vectorized={vect_result.sharpe_ratio:.4f})"
            )
        elif naut_result.sharpe_ratio == 0:
            pass
        else:
            assert abs(naut_result.sharpe_ratio) <= 0.10

    def test_final_equity_within_tolerance(self) -> None:
        """Final equity between engines agrees within +/-5 %."""
        data = _synthetic_equity_data(n=1000)
        signal = sma_crossover_signal(fast=50, slow=200)
        cfg = BacktestConfig(initial_capital=100_000, commission_pct=0.0, slippage_bps=0.0)

        vect_result = VectorizedEngine().run(data, signal, cfg)
        naut_result = NautilusEngine().run(data, signal, cfg)

        if vect_result.final_equity != 0:
            diff_pct = abs(naut_result.final_equity - vect_result.final_equity) / abs(
                vect_result.final_equity
            )
            assert diff_pct <= 0.05, (
                f"Final equity differs by {diff_pct * 100:.2f}% "
                f"(nautilus={naut_result.final_equity:.4f}, "
                f"vectorized={vect_result.final_equity:.4f})"
            )

    def test_both_return_types(self) -> None:
        """Both engines produce valid BacktestResult objects."""
        data = _synthetic_equity_data(n=1000)
        signal = sma_crossover_signal(fast=50, slow=200)
        cfg = BacktestConfig()

        vect_result = VectorizedEngine().run(data, signal, cfg)
        naut_result = NautilusEngine().run(data, signal, cfg)

        for label, r in [("vectorized", vect_result), ("nautilus", naut_result)]:
            assert isinstance(r, BacktestResult), f"{label} result type"
            assert r.total_trades >= 0, f"{label} trades"
            assert len(r.equity_curve) == len(data), f"{label} equity curve length"
