"""Futures contract specifications — deterministic, point-in-time.

ContractSpec defines the canonical properties of a tradable futures
contract.  Every sizing, P&L, and risk calculation uses these values —
there are no generic fallbacks.

Sources: CME Group product specifications (verified 2026-07-19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ContractSettlement(StrEnum):
    """Settlement method for a futures contract."""

    PHYSICAL = "physical"
    CASH = "cash"


class ContractUnit(StrEnum):
    """Unit of trading volume."""

    CONTRACTS = "contracts"
    LOTS = "lots"


@dataclass(frozen=True)
class ContractSpec:
    """Immutable specification for a single futures contract product.

    All numeric values are ``Decimal`` for deterministic precision
    in P&L and sizing calculations.

    **Naming convention:** ``{root_symbol}{month_code}{year}``
    for tradable contracts (e.g. ``ESU26``), ``{root_symbol}``
    for continuous contracts (e.g. ``ES``).
    """

    # ── Identity ────────────────────────────────────────────────────────
    root_symbol: str
    """Root symbol (e.g. ES, NQ, GC, CL).  Same across all expiries."""

    exchange: str
    """CME, ICE, EUREX, etc."""

    asset_class: str
    """equity_index, commodity, interest_rate, currency, energy"""

    currency: str
    """Settlement currency (USD, EUR, GBP, JPY)."""

    # ── Contract mechanics ───────────────────────────────────────────────
    multiplier: Decimal
    """Contract multiplier: notional = price × multiplier.
    Example: ES has multiplier 50 (one point = $50 per contract)."""

    point_value: Decimal
    """Dollar value of a one-point move in the contract price.
    For most CME futures this equals ``multiplier``."""

    tick_size: Decimal
    """Minimum price increment (e.g. 0.25 for ES)."""

    tick_value: Decimal
    """Dollar value of one tick = tick_size × point_value."""

    contract_size: Decimal
    """Units of the underlying per contract (e.g. 100 oz for GC)."""

    # ── Mini / micro equivalence ────────────────────────────────────────
    mini_symbol: str | None = None
    """Symbol of the mini version (e.g. ES → MES)."""

    mini_ratio: Decimal | None = None
    """How many mini contracts equal one full contract (e.g. 10 for ES/MES)."""

    micro_symbol: str | None = None
    """Symbol of the micro version, if different from mini."""

    micro_ratio: Decimal | None = None
    """How many micro contracts equal one full contract."""

    # ── Margin (approximate, verify with broker) ─────────────────────────
    initial_margin: Decimal | None = None
    maintenance_margin: Decimal | None = None

    # ── Settlement ───────────────────────────────────────────────────────
    settlement: ContractSettlement = ContractSettlement.CASH
    unit: ContractUnit = ContractUnit.CONTRACTS

    # ── Expiry schedule ──────────────────────────────────────────────────
    listing_months: tuple[int, ...] = field(default_factory=lambda: (3, 6, 9, 12))
    """Months in which new contracts are listed (CME standard: Mar/Jun/Sep/Dec)."""

    first_trade_date: date | None = None
    last_trade_date: date | None = None
    first_notice_date: date | None = None

    # ── Metadata ─────────────────────────────────────────────────────────
    source: str = "CME Group product specifications"
    source_checked_at: str = "2026-07-19"

    # ── Computed helpers ─────────────────────────────────────────────────

    def pnl_per_point(self, contracts: Decimal) -> Decimal:
        """P&L for a one-point move with ``contracts`` lots."""
        return self.point_value * contracts

    def pnl_per_tick(self, contracts: Decimal) -> Decimal:
        """P&L for a one-tick move with ``contracts`` lots."""
        return self.tick_value * contracts

    def notional_value(self, price: Decimal, contracts: Decimal) -> Decimal:
        """Total notional exposure = price × multiplier × contracts."""
        return price * self.multiplier * contracts

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (useful for config files)."""
        out: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Decimal):
                out[k] = str(v)
            elif isinstance(v, date):
                out[k] = v.isoformat()
            elif isinstance(v, tuple):
                out[k] = list(v)
            elif isinstance(v, ContractSettlement | ContractUnit):
                out[k] = v.value
            else:
                out[k] = v
        return out


# =========================================================================
# Pre-defined catalog — CME equity index futures
# =========================================================================

ES = ContractSpec(
    root_symbol="ES",
    exchange="CME",
    asset_class="equity_index",
    currency="USD",
    multiplier=Decimal("50"),
    point_value=Decimal("50"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("12.50"),
    contract_size=Decimal("1"),
    mini_symbol="MES",
    mini_ratio=Decimal("10"),
    initial_margin=Decimal("12000"),
    maintenance_margin=Decimal("10900"),
    listing_months=(3, 6, 9, 12),
    source="CME E-mini S&P 500 product specifications",
)

MES = ContractSpec(
    root_symbol="MES",
    exchange="CME",
    asset_class="equity_index",
    currency="USD",
    multiplier=Decimal("5"),
    point_value=Decimal("5"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("1.25"),
    contract_size=Decimal("1"),
    initial_margin=Decimal("1200"),
    maintenance_margin=Decimal("1090"),
    listing_months=(3, 6, 9, 12),
    source="CME Micro E-mini S&P 500 product specifications",
)

NQ = ContractSpec(
    root_symbol="NQ",
    exchange="CME",
    asset_class="equity_index",
    currency="USD",
    multiplier=Decimal("20"),
    point_value=Decimal("20"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("5.00"),
    contract_size=Decimal("1"),
    mini_symbol="MNQ",
    mini_ratio=Decimal("10"),
    initial_margin=Decimal("18000"),
    maintenance_margin=Decimal("16360"),
    listing_months=(3, 6, 9, 12),
    source="CME E-mini Nasdaq-100 product specifications",
)

MNQ = ContractSpec(
    root_symbol="MNQ",
    exchange="CME",
    asset_class="equity_index",
    currency="USD",
    multiplier=Decimal("2"),
    point_value=Decimal("2"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("0.50"),
    contract_size=Decimal("1"),
    initial_margin=Decimal("1800"),
    maintenance_margin=Decimal("1636"),
    listing_months=(3, 6, 9, 12),
    source="CME Micro E-mini Nasdaq-100 product specifications",
)

GC = ContractSpec(
    root_symbol="GC",
    exchange="CME",
    asset_class="commodity",
    currency="USD",
    multiplier=Decimal("100"),
    point_value=Decimal("100"),
    tick_size=Decimal("0.10"),
    tick_value=Decimal("10.00"),
    contract_size=Decimal("100"),
    micro_symbol="MGC",
    micro_ratio=Decimal("10"),
    initial_margin=Decimal("9000"),
    maintenance_margin=Decimal("8100"),
    listing_months=(2, 4, 6, 8, 10, 12),
    settlement=ContractSettlement.PHYSICAL,
    source="CME Gold futures product specifications",
)

MGC = ContractSpec(
    root_symbol="MGC",
    exchange="CME",
    asset_class="commodity",
    currency="USD",
    multiplier=Decimal("10"),
    point_value=Decimal("10"),
    tick_size=Decimal("0.10"),
    tick_value=Decimal("1.00"),
    contract_size=Decimal("10"),
    initial_margin=Decimal("900"),
    maintenance_margin=Decimal("810"),
    listing_months=(2, 4, 6, 8, 10, 12),
    settlement=ContractSettlement.PHYSICAL,
    source="CME Micro Gold futures product specifications",
)

CL = ContractSpec(
    root_symbol="CL",
    exchange="CME",
    asset_class="energy",
    currency="USD",
    multiplier=Decimal("1000"),
    point_value=Decimal("1000"),
    tick_size=Decimal("0.01"),
    tick_value=Decimal("10.00"),
    contract_size=Decimal("1000"),
    micro_symbol="MCL",
    micro_ratio=Decimal("10"),
    initial_margin=Decimal("5500"),
    maintenance_margin=Decimal("5000"),
    listing_months=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    settlement=ContractSettlement.PHYSICAL,
    source="CME Crude Oil futures product specifications",
)

MCL = ContractSpec(
    root_symbol="MCL",
    exchange="CME",
    asset_class="energy",
    currency="USD",
    multiplier=Decimal("100"),
    point_value=Decimal("100"),
    tick_size=Decimal("0.01"),
    tick_value=Decimal("1.00"),
    contract_size=Decimal("100"),
    initial_margin=Decimal("550"),
    maintenance_margin=Decimal("500"),
    listing_months=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    settlement=ContractSettlement.PHYSICAL,
    source="CME Micro Crude Oil futures product specifications",
)

# =========================================================================
# Registry
# =========================================================================

# Full catalog: symbol → ContractSpec
CATALOG: dict[str, ContractSpec] = {
    "ES": ES,
    "MES": MES,
    "NQ": NQ,
    "MNQ": MNQ,
    "GC": GC,
    "MGC": MGC,
    "CL": CL,
    "MCL": MCL,
}


def get_contract(symbol: str) -> ContractSpec:
    """Look up a contract spec by symbol.

    Args:
        symbol: Root symbol (e.g. ``ES``, ``NQ``, ``GC``).

    Returns:
        The matching ``ContractSpec``.

    Raises:
        KeyError: If the symbol is not in the catalog.
    """
    if symbol not in CATALOG:
        raise KeyError(
            f"Unknown contract symbol {symbol!r}. Available: {', '.join(sorted(CATALOG))}"
        )
    return CATALOG[symbol]


def pnl_check(symbol: str, contracts: Decimal, points: Decimal) -> Decimal:
    """Quick P&L sanity check: returns P&L for ``contracts`` lots moving ``points``.

    Example::

        >>> pnl_check("ES", contracts=Decimal("1"), points=Decimal("10"))
        Decimal('500')   # 1 ES contract × $50/point × 10 points = $500
    """
    spec = get_contract(symbol)
    return spec.pnl_per_point(contracts) * points
