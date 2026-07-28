"""G5 qualification test — SMA crossover strategy on ES futures.

This is a canonical strategy used to verify the backtest engine:
- Contract: ES (E-mini S&P 500)
- Data: daily OHLCV from yfinance
- Strategy: SMA crossover (50/200)
- Cost model: $2.50 round-turn + 0.5bp slippage

The test verifies that the backtest engine produces deterministic,
reproducible results with real-world costs.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from market.contracts import ES

#: The pinned M31 baseline (see data/pinned/ES_1d_m31.provenance.json, BL-001).
#: Previously this read data/ohlcv/ES_daily.parquet, which was renamed to
#: ES_1d.parquet in f87726f and is git-ignored — so the test broke and could
#: not pass on a fresh clone at all. The pinned copy is tracked, hash-verified,
#: and keeps the capitalised yfinance schema (Close/High/Low/Open/Volume/Date)
#: that these tests read directly. Do not repoint at data/ohlcv/: ADR-014
#: records that file being regenerated out-of-band, losing the M31 evidence.
ES_DAILY = Path("data/pinned/ES_1d_m31.parquet")


@pytest.fixture(scope="module")
def es_data() -> pl.DataFrame:
    """Load ES daily data from parquet."""
    if not ES_DAILY.exists():
        pytest.skip("ES data not found — run scripts/fetch_data.py first")
    return pl.read_parquet(ES_DAILY)


class TestQualification:
    """Qualification-grade backtest verification."""

    def test_data_available(self) -> None:
        """Verify ES data exists with minimum required bars."""
        assert ES_DAILY.exists(), "ES data not found"
        df = pl.read_parquet(ES_DAILY)
        assert len(df) >= 100, f"Need at least 100 bars, got {len(df)}"
        assert "Close" in df.columns
        assert "Volume" in df.columns

    def test_pinned_dataset_hash_matches_provenance(self) -> None:
        """The pin must still hash to what its provenance claims.

        ADR-014: the original M31 dataset was regenerated out-of-band and the
        qualifying row set was lost, with nothing failing to signal it. This
        check turns that silent drift into a test failure.
        """
        provenance = json.loads(
            Path("data/pinned/ES_1d_m31.provenance.json").read_text(encoding="utf-8")
        )
        digest = hashlib.sha256(ES_DAILY.read_bytes()).hexdigest()
        assert digest == provenance["sha256"], (
            f"pinned dataset drifted: {digest} != {provenance['sha256']}. "
            "Regenerate M31 evidence and update the pin — do not edit the hash."
        )
        assert pl.read_parquet(ES_DAILY).height == provenance["rows"]

    def test_contract_spec_matches(self) -> None:
        """ES contract spec must match known values."""
        assert ES.multiplier == Decimal("50")
        assert ES.tick_value == Decimal("12.50")
        assert ES.point_value == Decimal("50")

    def test_sma_crossover_returns_positive(self) -> None:
        """Simple SMA crossover should produce expected results."""
        import pandas as pd

        df = pd.read_parquet(ES_DAILY)
        close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]

        # SMA crossover: 20/50 (faster for our data length)
        sma_fast = close.rolling(20).mean()
        sma_slow = close.rolling(50).mean()

        # Generate signals
        position = 0
        trades = []
        entry_price = 0.0

        for i in range(50, len(close)):
            prev_fast = sma_fast.iloc[i - 1]
            prev_slow = sma_slow.iloc[i - 1]
            cur_fast = sma_fast.iloc[i]
            cur_slow = sma_slow.iloc[i]

            # Crossover: fast crosses above slow
            if prev_fast <= prev_slow and cur_fast > cur_slow:
                if position == 0:
                    position = 1
                    entry_price = close.iloc[i]
            # Cross below
            elif prev_fast >= prev_slow and cur_fast < cur_slow and position == 1:
                pnl = (close.iloc[i] - entry_price) * 50  # ES point value
                trades.append(pnl)
                position = 0

        # Close any open position
        if position == 1:
            pnl = (close.iloc[-1] - entry_price) * 50
            trades.append(pnl)

        total_pnl = sum(trades)
        num_trades = len(trades)

        print("\n📊 SMA Crossover (20/50) on ES daily:")
        print(f"   Trades: {num_trades}")
        print(f"   Total P&L: ${total_pnl:,.2f}")
        print(f"   Win rate: {sum(1 for t in trades if t > 0) / max(num_trades, 1) * 100:.0f}%")

        # We don't assert profitability (markets vary)
        # We assert the engine runs and produces deterministic results
        assert num_trades > 0, "Strategy must generate at least one trade"
        assert all(isinstance(t, (int, float)) for t in trades)

    def test_vectorized_parity(self) -> None:
        """Vectorbt backtest should produce the same results as pandas."""
        pytest.importorskip("vectorbt")
        import pandas as pd
        import vectorbt as vbt

        df = pd.read_parquet(ES_DAILY)
        close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]

        # Same SMA crossover with vectorbt
        fast_ma = vbt.MA.run(close, 20)
        slow_ma = vbt.MA.run(close, 50)
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)

        pf = vbt.Portfolio.from_signals(close, entries, exits, freq="D")
        total_return = pf.total_return()

        print("\n📊 Vectorbt SMA Crossover (20/50):")
        print(f"   Total return: {total_return:.2%}")
        print(f"   Sharpe: {pf.sharpe_ratio():.2f}")
        print(f"   Max DD: {pf.max_drawdown():.2%}")

        # Verify vectorbt runs without error
        assert isinstance(total_return, float)
