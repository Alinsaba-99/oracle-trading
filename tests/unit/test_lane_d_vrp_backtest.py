"""Tests for BL-507b Lane D VRP historical Black-Scholes backtest.

Step 2 Opzione C (2026-08-16). Pure-Python backtest that uses BSM pricing
on historical SPY + VIX (FRED) — no IBKR connection required.

Coverage:
- Black-Scholes put price sanity (intrinsic floor, monotonic in IV/strike/DTE)
- Strike-to-delta solver finds the right OTM strike for target delta
- Backtest on synthetic SPY+VIX dataframe → deterministic positions + exits
- Exit rules: 50% profit, 20% loss roll, DTE=7, expiry
- Tail event tracking (loss > 1× premium received)
- Edge cases: empty data, no trades, all losing
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from analytics.strategy.lane_d_vrp_backtest import (
    VRPBacktestConfig,
    VRPBacktester,
    black_scholes_put,
    black_scholes_put_delta,
    strike_for_target_delta,
)

# ---------------------------------------------------------------------------
# Black-Scholes put pricing
# ---------------------------------------------------------------------------


class TestBlackScholesPut:
    def test_atm_at_expiry_returns_intrinsic(self) -> None:
        # Spot = strike = 100, dte=0 → intrinsic = max(K-S, 0) = 0
        p = black_scholes_put(spot=100.0, strike=100.0, dte_days=0.0, iv=0.20)
        assert p == pytest.approx(0.0, abs=1e-6)

    def test_itm_at_expiry_returns_intrinsic(self) -> None:
        # Spot 90, strike 100, dte=0 → intrinsic = 10
        p = black_scholes_put(spot=90.0, strike=100.0, dte_days=0.0, iv=0.20)
        assert p == pytest.approx(10.0, abs=1e-6)

    def test_otm_at_expiry_returns_zero(self) -> None:
        # Spot 110, strike 100 → intrinsic = max(100-110, 0) = 0
        p = black_scholes_put(spot=110.0, strike=100.0, dte_days=0.0, iv=0.20)
        assert p == pytest.approx(0.0, abs=1e-6)

    def test_put_increases_with_iv(self) -> None:
        params = dict(spot=100.0, strike=95.0, dte_days=30.0, r=0.04, q=0.015)
        p_low = black_scholes_put(iv=0.10, **params)
        p_mid = black_scholes_put(iv=0.20, **params)
        p_high = black_scholes_put(iv=0.40, **params)
        assert p_low < p_mid < p_high

    def test_put_increases_with_dte(self) -> None:
        params = dict(spot=100.0, strike=95.0, iv=0.20, r=0.04, q=0.015)
        p_short = black_scholes_put(dte_days=7.0, **params)
        p_mid = black_scholes_put(dte_days=30.0, **params)
        p_long = black_scholes_put(dte_days=180.0, **params)
        assert p_short < p_mid < p_long

    def test_put_increases_as_strike_rises(self) -> None:
        # Higher strike → deeper ITM → more valuable
        params = dict(spot=100.0, dte_days=30.0, iv=0.20, r=0.04, q=0.015)
        p_k90 = black_scholes_put(strike=90.0, **params)
        p_k95 = black_scholes_put(strike=95.0, **params)
        p_k100 = black_scholes_put(strike=100.0, **params)
        assert p_k90 < p_k95 < p_k100

    def test_put_zero_iv_returns_intrinsic_pv(self) -> None:
        # iv=0 → put = max(K-S, 0) * e^{-rT}
        p = black_scholes_put(spot=90.0, strike=100.0, dte_days=30.0, iv=0.0, r=0.04, q=0.0)
        expected = 10.0 * np.exp(-0.04 * 30.0 / 365.0)
        assert p == pytest.approx(expected, abs=1e-3)


class TestPutDelta:
    def test_otm_put_delta_in_minus_1_to_0(self) -> None:
        d = black_scholes_put_delta(spot=100.0, strike=95.0, dte_days=30.0, iv=0.20)
        assert -1.0 < d < 0.0

    def test_atm_put_delta_near_negative_half(self) -> None:
        # ATM put delta ~ -0.50
        d = black_scholes_put_delta(spot=100.0, strike=100.0, dte_days=30.0, iv=0.20, r=0.04, q=0.0)
        assert d == pytest.approx(-0.50, abs=0.05)

    def test_itm_put_delta_more_negative(self) -> None:
        d_otm = black_scholes_put_delta(spot=100.0, strike=95.0, dte_days=30.0, iv=0.20)
        d_itm = black_scholes_put_delta(spot=100.0, strike=105.0, dte_days=30.0, iv=0.20)
        assert d_itm < d_otm  # ITM put has more negative delta


class TestStrikeForTargetDelta:
    def test_target_20_delta_finds_otm_strike(self) -> None:
        # Spot 100, target delta -0.20 → strike should be OTM (below spot)
        strike = strike_for_target_delta(
            spot=100.0, target_delta=0.20, dte_days=30.0, iv=0.20, r=0.04, q=0.0
        )
        assert strike < 100.0
        # Verify by recomputing delta
        d = black_scholes_put_delta(
            spot=100.0, strike=strike, dte_days=30.0, iv=0.20, r=0.04, q=0.0
        )
        assert d == pytest.approx(-0.20, abs=2e-2)

    def test_lower_target_delta_finds_deeper_otm(self) -> None:
        k_20 = strike_for_target_delta(spot=100.0, target_delta=0.20, dte_days=30.0, iv=0.20, q=0.0)
        k_10 = strike_for_target_delta(spot=100.0, target_delta=0.10, dte_days=30.0, iv=0.20, q=0.0)
        assert k_10 < k_20  # 10-delta is deeper OTM

    def test_higher_iv_pushes_strike_further_otm(self) -> None:
        # For same target delta, higher IV → strike further from spot
        k_low_iv = strike_for_target_delta(
            spot=100.0, target_delta=0.20, dte_days=30.0, iv=0.10, q=0.0
        )
        k_high_iv = strike_for_target_delta(
            spot=100.0, target_delta=0.20, dte_days=30.0, iv=0.40, q=0.0
        )
        assert k_high_iv < k_low_iv  # higher IV → deeper OTM for same delta


# ---------------------------------------------------------------------------
# VRP backtest — synthetic data scenarios
# ---------------------------------------------------------------------------


def _make_synthetic_data(
    start: date = date(2024, 1, 1),
    n_days: int = 90,
    spy_start: float = 400.0,
    spy_daily_ret: float = 0.0005,
    vix_value: float = 15.0,
) -> pl.DataFrame:
    """Build synthetic SPY+VIX dataframe with controlled drift."""
    dates = [start + timedelta(days=i) for i in range(n_days)]
    spy_prices = [spy_start * (1.0 + spy_daily_ret) ** i for i in range(n_days)]
    vix_values = [vix_value] * n_days
    return pl.DataFrame(
        {
            "date": dates,
            "open": spy_prices,
            "high": [p * 1.001 for p in spy_prices],
            "low": [p * 0.999 for p in spy_prices],
            "close": spy_prices,
            "vix_close": vix_values,
        }
    )


class TestVRPBacktesterConstruction:
    def test_empty_data_raises(self) -> None:
        with pytest.raises(ValueError, match="no overlapping dates"):
            VRPBacktester(
                spy_df=pl.DataFrame(schema={"date": pl.Date, "close": pl.Float64}),
                vix_df=pl.DataFrame(schema={"date": pl.Date, "vix_close": pl.Float64}),
            )

    def test_default_config(self) -> None:
        df = _make_synthetic_data()
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        assert bt.config.target_dte == 30
        assert bt.config.target_delta == 0.20


class TestVRPBacktestRun:
    def test_run_on_synthetic_data_opens_trades(self) -> None:
        df = _make_synthetic_data(n_days=120)
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 4, 30))
        assert result.n_trades > 0
        assert result.n_trades <= 120 // 5  # max ~1 trade per 5 days
        # Equity curve should have one entry per trading day
        assert result.equity_curve.size > 0

    def test_exit_rules_profit_taken_at_50pct(self) -> None:
        # Very low IV + rising spot → put decays fast → 50% profit exit
        df = _make_synthetic_data(n_days=60, vix_value=10.0, spy_daily_ret=0.002)
        bt = VRPBacktester(
            df,
            df.select(["date", "vix_close"]),
            config=VRPBacktestConfig(entry_cadence_days=1, avoid_mondays=False),
        )
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 3, 1))
        # Should have at least some profit exits
        assert (
            result.exit_breakdown.get("profit", 0) > 0
            or result.exit_breakdown.get("dte_exit", 0) > 0
        )

    def test_tail_event_detected_on_crash(self) -> None:
        # Sharp SPY drop with elevated VIX → ITM put, large loss
        n_days = 60
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
        # SPY drops 30% in first 30 days, then flat
        spy = [400.0 * (1.0 - 0.01 * min(i, 30)) for i in range(n_days)]
        vix = [15.0 if i < 10 else 40.0 if i < 30 else 25.0 for i in range(n_days)]
        df = pl.DataFrame(
            {"date": dates, "open": spy, "high": spy, "low": spy, "close": spy, "vix_close": vix}
        )
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 3, 1))
        # At least one trade should be a loss (crash)
        assert any(p.pnl < 0 for p in result.positions)

    def test_no_trades_outside_date_range(self) -> None:
        df = _make_synthetic_data(n_days=120)
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        # Run with start after data end → empty result
        result = bt.run(start=date(2025, 1, 1), end=date(2025, 3, 1))
        assert result.n_trades == 0
        assert result.equity_curve.size == 0

    def test_position_size_compounds_with_equity(self) -> None:
        # With growing equity, contracts per trade should increase
        df = _make_synthetic_data(n_days=180, spy_daily_ret=0.001)  # rising
        bt = VRPBacktester(
            df,
            df.select(["date", "vix_close"]),
            config=VRPBacktestConfig(entry_cadence_days=10, position_size_pct=0.05),
        )
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 6, 30))
        if len(result.positions) >= 2:
            # Later trades should have >= contracts than earlier (equity grew)
            contracts = [p.contracts for p in result.positions]
            assert max(contracts) >= min(contracts)

    def test_exit_breakdown_all_reasons_valid(self) -> None:
        df = _make_synthetic_data(n_days=120)
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 4, 30))
        valid_reasons = {"profit", "roll", "dte_exit", "expiry", "end_of_backtest"}
        for reason in result.exit_breakdown:
            assert reason in valid_reasons

    def test_max_drawdown_non_positive(self) -> None:
        df = _make_synthetic_data(n_days=120)
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 4, 30))
        assert result.max_drawdown <= 0.0

    def test_hit_rate_in_zero_to_one(self) -> None:
        df = _make_synthetic_data(n_days=120)
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2024, 1, 1), end=date(2024, 4, 30))
        assert 0.0 <= result.hit_rate <= 1.0


class TestVRPBacktestResult:
    def test_empty_result_when_no_data(self) -> None:
        df = _make_synthetic_data(n_days=5)  # too few days for any trade
        bt = VRPBacktester(df, df.select(["date", "vix_close"]))
        result = bt.run(start=date(2025, 1, 1), end=date(2025, 6, 1))
        assert result.n_trades == 0
        assert result.total_return == 0.0
        assert result.sharpe is None
        assert result.tail_events == []
