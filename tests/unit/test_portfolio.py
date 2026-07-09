"""Tests for Portfolio model — initial_capital field."""

from __future__ import annotations

from decimal import Decimal

from core.domain.enums import PortfolioType
from core.domain.portfolio import Portfolio


class TestPortfolioInitialCapital:
    def test_default_initial_capital(self) -> None:
        p = Portfolio()
        assert p.initial_capital == Decimal("100000")

    def test_custom_initial_capital(self) -> None:
        p = Portfolio(initial_capital=Decimal("50000"))
        assert p.initial_capital == Decimal("50000")

    def test_initial_capital_is_decimal(self) -> None:
        p = Portfolio()
        assert isinstance(p.initial_capital, Decimal)

    def test_portfolio_without_initial_capital_still_defaults(self) -> None:
        p = Portfolio(name="Test", type=PortfolioType.backtest)
        assert p.initial_capital == Decimal("100000")

    def test_other_fields_unaffected(self) -> None:
        p = Portfolio(initial_capital=Decimal("200000"))
        assert p.portfolio_id is not None
        assert p.cash == Decimal("0")
        assert p.total_value == Decimal("0")
