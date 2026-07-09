"""Tests for M6 Fundamental — statements parsing, ratios, valuation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from analytics.fundamental.ratios import current_ratio, de_ratio, pb_ratio, pe_ratio, roe
from analytics.fundamental.statements import (
    parse_balance_sheet,
    parse_cash_flow,
    parse_income_statement,
)
from analytics.fundamental.valuation import dcf, graham_number

# ── Statements ──────────────────────────────────────────────────────────────


class TestParseIncomeStatement:
    """Tests for parse_income_statement."""

    def test_happy_path(self) -> None:
        raw = {
            "Revenue": 1_000_000.0,
            "CostOfGoodsSold": 400_000.0,
            "NetIncomeLoss": 150_000.0,
            "EarningsPerShareBasic": 1.50,
        }
        result = parse_income_statement(raw)
        assert result["revenue"] == 1_000_000.0
        assert result["cogs"] == 400_000.0
        assert result["net_income"] == 150_000.0
        assert result["eps"] == 1.50

    def test_alternative_keys(self) -> None:
        raw = {
            "TotalRevenue": 500_000.0,
            "CostOfRevenue": 200_000.0,
            "NetIncome": 80_000.0,
            "EPS": 0.80,
        }
        result = parse_income_statement(raw)
        assert result["revenue"] == 500_000.0
        assert result["cogs"] == 200_000.0
        assert result["net_income"] == 80_000.0
        assert result["eps"] == 0.80

    def test_nested_facts(self) -> None:
        raw = {
            "facts": {
                "Revenue": 2_000_000.0,
                "COGS": 800_000.0,
                "NetIncomeLoss": 300_000.0,
                "EPS": 3.00,
            }
        }
        result = parse_income_statement(raw)
        assert result["revenue"] == 2_000_000.0

    def test_missing_keys_default_to_zero(self) -> None:
        result = parse_income_statement({})
        assert result["revenue"] == 0.0
        assert result["cogs"] == 0.0
        assert result["net_income"] == 0.0
        assert result["eps"] == 0.0

    def test_nan_is_guarded(self) -> None:
        raw = {
            "Revenue": float("nan"),
            "COGS": float("inf"),
            "NetIncomeLoss": None,
            "EPS": "not-a-number",
        }
        result = parse_income_statement(raw)
        assert result["revenue"] == 0.0
        assert result["cogs"] == 0.0
        assert result["net_income"] == 0.0
        assert result["eps"] == 0.0


class TestParseBalanceSheet:
    """Tests for parse_balance_sheet."""

    def test_happy_path(self) -> None:
        raw = {
            "TotalAssets": 5_000_000.0,
            "TotalLiabilities": 2_000_000.0,
            "StockholdersEquity": 3_000_000.0,
        }
        result = parse_balance_sheet(raw)
        assert result["assets"] == 5_000_000.0
        assert result["liabilities"] == 2_000_000.0
        assert result["equity"] == 3_000_000.0

    def test_alternative_keys(self) -> None:
        raw = {"Assets": 10_000_000.0, "Liabilities": 4_000_000.0, "Equity": 6_000_000.0}
        result = parse_balance_sheet(raw)
        assert result["assets"] == 10_000_000.0
        assert result["liabilities"] == 4_000_000.0
        assert result["equity"] == 6_000_000.0

    def test_missing_keys(self) -> None:
        result = parse_balance_sheet({})
        assert result["assets"] == 0.0
        assert result["liabilities"] == 0.0
        assert result["equity"] == 0.0

    def test_nan_guarded(self) -> None:
        raw = {"Assets": float("nan"), "Liabilities": None, "Equity": float("-inf")}
        result = parse_balance_sheet(raw)
        assert result["assets"] == 0.0
        assert result["liabilities"] == 0.0
        assert result["equity"] == 0.0


class TestParseCashFlow:
    """Tests for parse_cash_flow."""

    def test_happy_path(self) -> None:
        raw = {
            "NetCashProvidedByOperatingActivities": 500_000.0,
            "NetCashUsedForInvestingActivities": -200_000.0,
            "NetCashUsedForFinancingActivities": -100_000.0,
        }
        result = parse_cash_flow(raw)
        assert result["operating"] == 500_000.0
        assert result["investing"] == -200_000.0
        assert result["financing"] == -100_000.0

    def test_alternative_keys(self) -> None:
        raw = {
            "OperatingCashFlow": 300_000.0,
            "InvestingCashFlow": -50_000.0,
            "FinancingCashFlow": -80_000.0,
        }
        result = parse_cash_flow(raw)
        assert result["operating"] == 300_000.0
        assert result["investing"] == -50_000.0
        assert result["financing"] == -80_000.0

    def test_missing_keys(self) -> None:
        result = parse_cash_flow({})
        assert result["operating"] == 0.0
        assert result["investing"] == 0.0
        assert result["financing"] == 0.0


# ── Ratios ──────────────────────────────────────────────────────────────────


class TestPeRatio:
    """Tests for pe_ratio."""

    def test_normal(self) -> None:
        assert pe_ratio(100.0, 5.0) == 20.0

    def test_zero_eps_returns_none(self) -> None:
        assert pe_ratio(100.0, 0.0) is None

    def test_negative_eps(self) -> None:
        result = pe_ratio(100.0, -5.0)
        assert result is not None
        assert result == -20.0


class TestPbRatio:
    """Tests for pb_ratio."""

    def test_normal(self) -> None:
        assert pb_ratio(50.0, 25.0) == 2.0

    def test_zero_bvps_returns_none(self) -> None:
        assert pb_ratio(50.0, 0.0) is None


class TestROE:
    """Tests for roe."""

    def test_normal(self) -> None:
        assert roe(100_000.0, 1_000_000.0) == 0.10

    def test_zero_equity_returns_none(self) -> None:
        assert roe(100_000.0, 0.0) is None

    def test_negative_net_income(self) -> None:
        result = roe(-50_000.0, 1_000_000.0)
        assert result == -0.05


class TestDERatio:
    """Tests for de_ratio."""

    def test_normal(self) -> None:
        result = de_ratio(500_000.0, 1_000_000.0)
        assert result == 0.50

    def test_zero_equity_returns_none(self) -> None:
        assert de_ratio(500_000.0, 0.0) is None

    def test_nan_liabilities_returns_none(self) -> None:
        assert de_ratio(float("nan"), 1_000_000.0) is None


class TestCurrentRatio:
    """Tests for current_ratio."""

    def test_normal(self) -> None:
        assert current_ratio(200_000.0, 100_000.0) == 2.0

    def test_zero_liabilities_returns_none(self) -> None:
        assert current_ratio(200_000.0, 0.0) is None

    def test_inf_liabilities_returns_none(self) -> None:
        assert current_ratio(200_000.0, float("inf")) is None


class TestRatioEdgeCases:
    """Edge cases shared across all ratio functions."""

    @pytest.mark.parametrize(  # type: ignore[untyped-decorator]
        "func, args",
        [
            (pe_ratio, (100.0, 0.0)),
            (pb_ratio, (50.0, 0.0)),
            (roe, (100.0, 0.0)),
            (de_ratio, (100.0, 0.0)),
            (current_ratio, (100.0, 0.0)),
        ],
    )
    def test_zero_denominator(
        self, func: Callable[[float, float], float | None], args: tuple[float, float]
    ) -> None:
        assert func(*args) is None

    @pytest.mark.parametrize(  # type: ignore[untyped-decorator]
        "func, args",
        [
            (pe_ratio, ("bad", 1.0)),
            (pb_ratio, (1.0, "bad")),
            (roe, (None, 1.0)),
            (de_ratio, (1.0, None)),
            (current_ratio, (float("nan"), 1.0)),
        ],
    )
    def test_invalid_input(self, func: Callable[..., float | None], args: tuple[Any, ...]) -> None:
        assert func(*args) is None


# ── Valuation ────────────────────────────────────────────────────────────────


class TestDCF:
    """Tests for dcf."""

    def test_single_period(self) -> None:
        # FCF = 100, growth 0%, discount 10%, terminal 2%
        # PV of FCF = 100 * 1.0 / 1.1 ≈ 90.91
        # Terminal = 100 * 1.02 / (0.10 - 0.02) = 1275
        # PV terminal = 1275 / 1.1 ≈ 1159.09
        # Total ≈ 1250.00
        result = dcf([100.0], 0.0, 0.10, 0.02)
        assert result is not None
        assert result == pytest.approx(1250.0, rel=1e-9)

    def test_multi_period(self) -> None:
        # Two years of FCF 100, growth 5%, discount 10%, terminal 2%
        # Yr 1 projected: 100 * 1.05 = 105, PV = 105 / 1.1 = 95.4545
        # Yr 2 projected: 100 * 1.05^2 = 110.25, PV = 110.25 / 1.1^2 = 91.1157
        # Terminal = 110.25 * 1.02 / (0.10 - 0.02) = 1405.6875
        # PV terminal = 1405.6875 / 1.1^2 ≈ 1161.75
        # Total ≈ 1348.32
        result = dcf([100.0] * 2, 0.05, 0.10, 0.02)
        assert result is not None
        assert result == pytest.approx(1348.32, rel=1e-2)

    def test_empty_fcf_returns_none(self) -> None:
        assert dcf([], 0.05, 0.10, 0.02) is None

    def test_discount_rate_leq_terminal_growth_returns_none(self) -> None:
        assert dcf([100.0], 0.05, 0.02, 0.03) is None
        assert dcf([100.0], 0.05, 0.03, 0.03) is None

    def test_nan_inputs_returns_none(self) -> None:
        assert dcf([100.0], float("nan"), 0.10, 0.02) is None
        assert dcf([100.0], 0.05, 0.10, float("inf")) is None


class TestGrahamNumber:
    """Tests for graham_number."""

    def test_normal(self) -> None:
        # sqrt(22.5 * 5.0 * 20.0) = sqrt(2250) ≈ 47.434
        result = graham_number(5.0, 20.0)
        assert result is not None
        assert result == pytest.approx(47.434, rel=1e-2)

    def test_zero_eps_returns_none(self) -> None:
        assert graham_number(0.0, 20.0) is None

    def test_negative_bvps_returns_none(self) -> None:
        assert graham_number(5.0, -1.0) is None

    def test_nan_eps_returns_none(self) -> None:
        assert graham_number(float("nan"), 20.0) is None

    def test_inf_bvps_returns_none(self) -> None:
        assert graham_number(5.0, float("inf")) is None

    def test_string_input_returns_none(self) -> None:
        val: Any = "bad"
        assert graham_number(val, 20.0) is None
