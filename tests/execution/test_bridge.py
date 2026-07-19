"""Tests for PortfolioBridge — PortfolioDecision to OrderRequest conversion."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from agents.protocol import PortfolioDecision
from execution.order_manager.bridge import PortfolioBridge

# =========================================================================
# Helpers
# =========================================================================


def make_decision(**overrides: object) -> PortfolioDecision:
    """Build a PortfolioDecision with test defaults."""
    data = {
        "direction": "buy",
        "instrument": "AAPL",
        "position_size": 100.0,
        "confidence": 0.8,
        "reasoning": "Test bridge conversion",
        "agents_contributing": ["test-agent"],
        "regime_at_decision": "neutral",
        "risk_approved": True,
        "escalated": False,
    }
    data.update(overrides)
    return PortfolioDecision(**data)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def bridge() -> PortfolioBridge:
    risk = MagicMock()
    risk.check_order.return_value = True
    return PortfolioBridge(risk_manager=risk)


@pytest.fixture
def risk_bridge() -> PortfolioBridge:
    risk = MagicMock()
    risk.check_order.return_value = True
    return PortfolioBridge(risk_manager=risk)


# =========================================================================
# Happy path — direction conversion
# =========================================================================


class TestDirectionConversion:
    """PortfolioDecision direction maps to correct OrderRequest side."""

    def test_buy_decision(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(direction="buy")
        req = bridge.to_order_request(decision)

        assert req is not None
        assert req.side == "buy"
        assert req.instrument_id == "AAPL"

    def test_sell_decision(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(direction="sell")
        req = bridge.to_order_request(decision)

        assert req is not None
        assert req.side == "sell"
        assert req.instrument_id == "AAPL"

    def test_hold_returns_none(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(direction="hold")
        assert bridge.to_order_request(decision) is None

    def test_no_trade_returns_none(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(direction="no_trade")
        assert bridge.to_order_request(decision) is None

    def test_invalid_direction_raises_value_error(self, bridge: PortfolioBridge) -> None:
        decision = MagicMock()
        decision.direction = "invalid"
        decision.instrument = "AAPL"
        decision.position_size = 100.0
        decision.confidence = 0.8
        with pytest.raises(ValueError, match="Invalid direction"):
            bridge.to_order_request(decision)

    def test_edge_direction_empty_string(self, bridge: PortfolioBridge) -> None:
        decision = MagicMock()
        decision.direction = ""
        decision.instrument = "AAPL"
        decision.position_size = 100.0
        decision.confidence = 0.8
        with pytest.raises(ValueError, match="Invalid direction"):
            bridge.to_order_request(decision)


# =========================================================================
# Decimal conversion
# =========================================================================


class TestDecimalConversion:
    """float position_size is treated as fraction-of-portfolio.

    Default bridge uses portfolio_value=100000 and fallback price=$100,
    so quantity = (100000 * fraction) / 100 = fraction * 1000.
    """

    def test_quantity_is_decimal(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=0.25)  # 25% of portfolio
        req = bridge.to_order_request(decision)

        assert isinstance(req.quantity, Decimal)

    def test_quantize_four_places(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=0.25)
        req = bridge.to_order_request(decision)
        # 0.25 * 100000 / 100 = 250.0000 shares
        assert str(req.quantity) == "250.0000"

    def test_large_position(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=1.0)  # 100% of portfolio
        req = bridge.to_order_request(decision)
        # 1.0 * 100000 / 100 = 1000.0000 shares
        assert req.quantity == Decimal("1000.0000")

    def test_integer_position(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=0.05)  # 5% of portfolio
        req = bridge.to_order_request(decision)
        # 0.05 * 100000 / 100 = 50.0000 shares
        assert str(req.quantity) == "50.0000"

    def test_small_fraction(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=0.001)  # 0.1% of portfolio
        req = bridge.to_order_request(decision)
        # 0.001 * 100000 / 100 = 1.0000 share
        assert req.quantity == Decimal("1.0000")

    def test_zero_position(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(position_size=0.0)
        req = bridge.to_order_request(decision)

        assert str(req.quantity) == "0.0000"


# =========================================================================
# Confidence to algo mapping
# =========================================================================


class TestConfidenceToAlgo:
    """Confidence thresholds map to correct execution algorithm."""

    def test_high_confidence_market(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(confidence=0.8)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "market"

    @pytest.mark.parametrize("confidence", [0.7, 0.75, 0.99, 1.0])
    def test_market_threshold(self, bridge: PortfolioBridge, confidence: float) -> None:
        decision = make_decision(confidence=confidence)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "market"

    def test_mid_confidence_vwap(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(confidence=0.5)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "vwap"

    @pytest.mark.parametrize("confidence", [0.4, 0.55, 0.69])
    def test_vwap_threshold(self, bridge: PortfolioBridge, confidence: float) -> None:
        decision = make_decision(confidence=confidence)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "vwap"

    def test_low_confidence_twap(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(confidence=0.3)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "twap"

    @pytest.mark.parametrize("confidence", [0.0, 0.1, 0.39])
    def test_twap_threshold(self, bridge: PortfolioBridge, confidence: float) -> None:
        decision = make_decision(confidence=confidence)
        req = bridge.to_order_request(decision)

        assert req.execution_algo == "twap"


# =========================================================================
# Metadata passthrough
# =========================================================================


class TestMetadata:
    """Additional fields are passed through correctly."""

    def test_source_is_mas(self, bridge: PortfolioBridge) -> None:
        decision = make_decision()
        req = bridge.to_order_request(decision)

        assert req.source == "mas"

    def test_algo_config_has_confidence_and_target_value(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(confidence=0.75, position_size=0.1)  # 10% -> 10k target
        req = bridge.to_order_request(decision)

        assert req.algo_config["confidence"] == 0.75
        assert "target_value" in req.algo_config

    def test_instrument_id_maps(self, bridge: PortfolioBridge) -> None:
        decision = make_decision(instrument="BTC/USD")
        req = bridge.to_order_request(decision)

        assert req.instrument_id == "BTC/USD"


# =========================================================================
# Risk gate #1
# =========================================================================


class TestRiskGate:
    """RiskManager pre-check integration."""

    def test_risk_rejects_returns_none(self) -> None:
        risk = MagicMock()
        risk.check_order.return_value = False
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="buy")
        result = bridge.to_order_request_with_risk_check(decision)

        assert result is None
        risk.check_order.assert_called_once()

    def test_risk_approves_returns_order(self) -> None:
        risk = MagicMock()
        risk.check_order.return_value = True
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="buy")
        req = bridge.to_order_request_with_risk_check(decision)

        assert req is not None
        assert req.side == "buy"
        risk.check_order.assert_called_once()

    def test_risk_approves_through_bridge(self) -> None:
        risk = MagicMock()
        risk.check_order.return_value = True
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="buy")
        req = bridge.to_order_request_with_risk_check(decision)

        assert req is not None
        assert req.side == "buy"
        risk.check_order.assert_called_once()

    def test_risk_hold_decision_skips_check(self) -> None:
        risk = MagicMock()
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="hold")
        result = bridge.to_order_request_with_risk_check(decision)

        assert result is None
        risk.check_order.assert_not_called()

    def test_risk_no_trade_skips_check(self) -> None:
        risk = MagicMock()
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="no_trade")
        result = bridge.to_order_request_with_risk_check(decision)

        assert result is None
        risk.check_order.assert_not_called()

    def test_risk_check_receives_order_request(self) -> None:
        risk = MagicMock()
        bridge = PortfolioBridge(risk_manager=risk)

        decision = make_decision(direction="buy", instrument="ETH/USD")
        bridge.to_order_request_with_risk_check(decision)

        risk.check_order.assert_called_once()
        req = risk.check_order.call_args[0][0]
        assert req.instrument_id == "ETH/USD"
        assert req.side == "buy"
