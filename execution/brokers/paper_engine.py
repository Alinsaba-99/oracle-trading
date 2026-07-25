"""Realistic paper broker — models real-world fill conditions.

Extends the basic PaperBroker with:
- Bid/ask spread modeling
- Fill probability (market vs limit orders)
- Latency simulation
- Partial fills
- Real commission/fee schedules
- Market impact for large orders
- Exchange reject scenarios

Based on M27 atomic backlog spec.  Calibratable against broker sandbox.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

logger = logging.getLogger("oracle.execution.paper")


# ── Fill model configuration ────────────────────────────────────────


@dataclass
class FillModelConfig:
    """Parameters controlling paper fill realism.

    All values are configurable for calibration against broker sandbox.
    """

    # Spread (fraction of mid-price)
    spread_bps: float = 0.5
    """Typical bid-ask spread in basis points (ES ≈ 0.25-1.0 bps)."""

    # Market order fill probability
    market_fill_prob: float = 0.95
    """Probability a market order fills immediately (remainder = partial/skip)."""

    # Limit order fill parameters
    limit_fill_base_prob: float = 0.3
    """Base probability a limit order fills per evaluation tick."""

    limit_fill_improvement: float = 0.1
    """Extra fill probability per tick price improvement."""

    # Latency
    latency_ms_mean: float = 50.0
    """Mean simulated latency in milliseconds."""

    latency_ms_std: float = 20.0
    """Standard deviation of simulated latency."""

    # Partial fills
    partial_fill_prob: float = 0.15
    """Probability a fill is partial rather than complete."""

    partial_fill_min_pct: float = 0.1
    """Minimum size of a partial fill as fraction of order."""

    partial_fill_max_pct: float = 0.5
    """Maximum size of a partial fill as fraction of order."""

    # Market impact (for large orders relative to volume)
    impact_enabled: bool = True
    impact_bps_per_pct_volume: float = 0.5
    """Price impact in bps per 1% of estimated daily volume."""

    # Reject scenarios
    reject_prob: float = 0.01
    """Probability any order is rejected (simulate exchange/risk reject)."""

    # Commissions (approximate real rates)
    commission_per_contract: float = 2.50
    """Commission per contract round-turn (ES ≈ $2.50)."""
    commission_min: float = 1.50
    """Minimum commission per order."""

    # Slippage
    slippage_bps_mean: float = 0.3
    """Average slippage in bps for market orders."""
    slippage_bps_std: float = 0.2
    """Slippage variability."""

    def __post_init__(self) -> None:
        if self.spread_bps < 0:
            raise ValueError("spread_bps must be non-negative")
        if not 0 <= self.market_fill_prob <= 1:
            raise ValueError("market_fill_prob must be between 0 and 1")


# ── Default configs for different asset classes ─────────────────────


FUTURES_CONFIG = FillModelConfig(
    spread_bps=0.5,
    market_fill_prob=0.98,
    limit_fill_base_prob=0.4,
    latency_ms_mean=30,
    latency_ms_std=10,
    commission_per_contract=2.50,
    commission_min=1.50,
    impact_bps_per_pct_volume=0.3,
)

CRYPTO_CONFIG = FillModelConfig(
    spread_bps=2.0,
    market_fill_prob=0.95,
    limit_fill_base_prob=0.3,
    latency_ms_mean=100,
    latency_ms_std=50,
    commission_per_contract=0.0,
    commission_min=0.0,
    impact_bps_per_pct_volume=0.8,
)

EQUITY_CONFIG = FillModelConfig(
    spread_bps=1.0,
    market_fill_prob=0.90,
    limit_fill_base_prob=0.25,
    latency_ms_mean=50,
    latency_ms_std=20,
    commission_per_contract=0.005,
    commission_min=1.00,
    impact_bps_per_pct_volume=0.5,
)

# Map common symbols to configs
ASSET_CONFIGS: dict[str, FillModelConfig] = {
    "ES": FUTURES_CONFIG,
    "MES": FUTURES_CONFIG,
    "NQ": FUTURES_CONFIG,
    "MNQ": FUTURES_CONFIG,
    "GC": FUTURES_CONFIG,
    "CL": FUTURES_CONFIG,
    "BTC": CRYPTO_CONFIG,
    "ETH": CRYPTO_CONFIG,
    "SPY": EQUITY_CONFIG,
    "QQQ": EQUITY_CONFIG,
    "AAPL": EQUITY_CONFIG,
}


def _get_config(symbol: str) -> FillModelConfig:
    """Return the appropriate fill model config for a symbol."""
    base = symbol.split("/")[0].split(":")[0].split("=")[0]
    return ASSET_CONFIGS.get(base, EQUITY_CONFIG)


# ── Fill result ─────────────────────────────────────────────────────


@dataclass
class PaperFillResult:
    """Result of a paper fill simulation."""

    filled: bool
    fill_quantity: Decimal = Decimal("0")
    fill_price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    slippage_bps: float = 0.0
    latency_ms: float = 0.0
    rejection_reason: str = ""
    partial: bool = False
    remaining: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── Paper fill engine ───────────────────────────────────────────────


class RealisticPaperFillEngine:
    """Simulates realistic order fills based on configurable models.

    Usage::

        engine = RealisticPaperFillEngine()
        result = engine.simulate_fill("ES", 5500.0, 2, "market")
        if result.filled:
            print(f"Filled {result.fill_quantity} @ {result.fill_price}")
    """

    def __init__(self, config: FillModelConfig | None = None, seed: int = 42) -> None:
        self._config = config
        self._rng = random.Random(seed)

    def simulate_fill(
        self,
        symbol: str,
        mid_price: float,
        quantity: int,
        order_type: str = "market",
        limit_price: float | None = None,
        side: str = "buy",
        estimated_daily_volume: float = 1_000_000,
    ) -> PaperFillResult:
        """Simulate fill for an order.

        Args:
            symbol: Instrument symbol (used for asset-specific config).
            mid_price: Current mid-price.
            quantity: Order quantity.
            order_type: ``market``, ``limit``, ``stop``.
            limit_price: Limit price (required for limit orders).
            side: ``buy`` or ``sell``.
            estimated_daily_volume: For market impact calculation.

        Returns:
            PaperFillResult with fill details.
        """
        config = self._config or _get_config(symbol)

        # 1. Simulate latency
        latency = max(0.0, self._rng.gauss(config.latency_ms_mean, config.latency_ms_std))
        # Note: in async context, use await asyncio.sleep(latency / 1000)

        # 2. Check for exchange reject
        if self._rng.random() < config.reject_prob:
            reject_reasons = [
                "Price band violation",
                "Session not open",
                "Order rate exceeded",
                "Market order too large",
            ]
            return PaperFillResult(
                filled=False, rejection_reason=self._rng.choice(reject_reasons), latency_ms=latency
            )

        # 3. Compute spread and bid/ask
        half_spread = mid_price * config.spread_bps / 10_000
        bid = mid_price - half_spread
        ask = mid_price + half_spread
        ask - bid

        # 4. Determine fill price and probability
        fill_price = mid_price
        fill_prob = 0.0
        slippage = 0.0

        if order_type == "market":
            # Market order fills at ask (buy) or bid (sell) with slippage
            base_price = ask if side == "buy" else bid

            # Slippage
            slippage = abs(self._rng.gauss(config.slippage_bps_mean, config.slippage_bps_std))
            if side == "buy":
                fill_price = base_price * (1 + slippage / 10_000)
            else:
                fill_price = base_price * (1 - slippage / 10_000)

            # Market impact for large orders
            if config.impact_enabled and quantity > 10:
                volume_pct = quantity / max(estimated_daily_volume, 1)
                impact = volume_pct * config.impact_bps_per_pct_volume
                if side == "buy":
                    fill_price *= 1 + impact / 10_000
                else:
                    fill_price *= 1 - impact / 10_000

            fill_prob = config.market_fill_prob

        elif order_type == "limit":
            # Limit order fills only if price is at or better than limit
            if limit_price is not None:
                if (side == "buy" and limit_price >= ask) or (
                    side == "sell" and limit_price <= bid
                ):
                    fill_prob = config.limit_fill_base_prob
                    fill_price = limit_price
                else:
                    # Limit price not crossed — unlikely to fill
                    fill_prob = config.limit_fill_base_prob * 0.1
                    fill_price = limit_price or mid_price

        # 5. Roll for fill
        if self._rng.random() >= fill_prob:
            return PaperFillResult(filled=False, rejection_reason="No fill", latency_ms=latency)

        # 6. Partial fill?
        partial = self._rng.random() < config.partial_fill_prob
        fill_qty = quantity

        if partial:
            pct = self._rng.uniform(config.partial_fill_min_pct, config.partial_fill_max_pct)
            fill_qty = max(1, int(quantity * pct))

        # 7. Compute commission
        commission = max(config.commission_min, config.commission_per_contract * fill_qty)

        return PaperFillResult(
            filled=True,
            fill_quantity=Decimal(str(fill_qty)),
            fill_price=Decimal(str(round(fill_price, 2))),
            commission=Decimal(str(round(commission, 2))),
            slippage_bps=slippage,
            latency_ms=latency,
            partial=partial,
            remaining=Decimal(str(quantity - fill_qty)),
        )
