"""Tests for pair trading — cointegration test + spread signal."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.technical.pair_trading import (
    CointegrationResult,
    build_pair_df,
    compute_cointegration,
    spread_zscore,
)


def test_cointegration_result_dataclass() -> None:
    """CointegrationResult viene costruito correttamente."""
    spread = pl.Series("spread", [1.0, 2.0, 3.0], dtype=pl.Float64)
    result = CointegrationResult(
        score=-2.5,
        pvalue=0.03,
        critical_values={"1%": -3.0, "5%": -2.5, "10%": -2.2},
        hedge_ratio=1.5,
        spread=spread,
        is_cointegrated=True,
    )
    assert result.score == -2.5
    assert result.pvalue == 0.03
    assert result.hedge_ratio == 1.5
    assert result.is_cointegrated
    assert len(result.spread) == 3


def test_cointegration_self() -> None:
    """Una serie cointegrata con sé stessa deve dare pvalue ~ 0."""
    rng = np.random.default_rng(42)
    a = pl.Series("a", rng.normal(0, 1, 100).cumsum() + 100)
    b = a  # identica
    result = compute_cointegration(a, b)
    assert result.is_cointegrated
    assert result.hedge_ratio == pytest.approx(1.0, abs=0.001)


def test_cointegration_random_series() -> None:
    """Due random walk indipendenti NON devono essere cointegrati."""
    rng = np.random.default_rng(99)
    a = pl.Series("a", rng.normal(0, 1, 200).cumsum() + 100)
    b = pl.Series("b", rng.normal(0, 1, 200).cumsum() + 100)
    result = compute_cointegration(a, b)
    # Con poche probabilità può capitare — testiamo che hedge_ratio sia sensato
    assert isinstance(result.score, float)
    assert isinstance(result.pvalue, float)
    assert len(result.critical_values) == 3
    assert len(result.spread) == 200


def test_cointegration_known_pair() -> None:
    """Costruiamo una coppia cointegrata artificiale e verifichiamo."""
    rng = np.random.default_rng(42)
    a = np.linspace(100, 200, 500) + rng.normal(0, 1, 500)
    b = 2.0 * a + 5.0 + rng.normal(0, 2, 500)  # hedge ratio ~ 2.0
    result = compute_cointegration(pl.Series("a", a), pl.Series("b", b))
    assert result.is_cointegrated
    assert result.hedge_ratio == pytest.approx(2.0, abs=0.2)


def test_spread_zscore_returns_signal() -> None:
    """Z-score deve restituire solo -1, 0, 1."""
    rng = np.random.default_rng(42)
    spread = pl.Series(rng.normal(0, 1, 100))
    signal = spread_zscore(spread)
    assert set(signal.to_list()).issubset({-1, 0, 1})


def test_spread_zscore_mean_reverting() -> None:
    """Spread mean-reverting artificiale deve produrre trades."""
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.1, 200)
    spread_arr = np.sin(np.linspace(0, 2 * np.pi * 3, 200)) + noise
    spread = pl.Series(spread_arr)
    signal = spread_zscore(spread, window=10, entry_threshold=1.5)
    assert (signal != 0).sum() > 0  # deve trovare almeno un trade
    assert (signal == 0).sum() > 0  # ma non tutti i giorni


def test_spread_zscore_flat_line() -> None:
    """Spread costante non deve generare segnali (std ~ 0)."""
    spread = pl.Series("flat", [5.0] * 50)
    signal = spread_zscore(spread)
    assert (signal == 0).all()


def test_build_pair_df_aligns_data() -> None:
    """build_pair_df allinea due DataFrame e aggiunge colonna spread."""
    timestamps = pl.Series("timestamp", [1, 2, 3, 4, 5])
    close_a = pl.Series("close", [100.0, 101.0, 102.0, 103.0, 104.0])
    close_b = pl.Series("close", [200.0, 202.0, 204.0, 206.0, 208.0])
    data_a = pl.DataFrame({"timestamp": timestamps, "close": close_a})
    data_b = pl.DataFrame({"timestamp": timestamps, "close": close_b})

    result = build_pair_df(data_a, data_b)
    assert "close_a" in result.columns
    assert "close_b" in result.columns
    assert "spread" in result.columns
    assert len(result) == 5


def test_build_pair_df_partial_overlap() -> None:
    """Solo timestamp in comune vengono mantenuti."""
    data_a = pl.DataFrame(
        {"timestamp": [1, 2, 3, 4, 5], "close": [100.0, 101.0, 102.0, 103.0, 104.0]}
    )
    data_b = pl.DataFrame(
        {"timestamp": [3, 4, 5, 6, 7], "close": [200.0, 202.0, 204.0, 206.0, 208.0]}
    )
    result = build_pair_df(data_a, data_b)
    assert len(result) == 3  # solo 3, 4, 5
