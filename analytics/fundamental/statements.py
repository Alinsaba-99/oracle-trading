"""Financial statements parser — income statement, balance sheet, cash flow.

Each function accepts an edgartools-style dict and returns a clean numeric
dict with NaN guards (missing / None / NaN keys → 0.0).
"""

from __future__ import annotations

import math
from typing import Any


def _safe_float(value: Any) -> float:
    """Return a float from *value*, guarding NaN, None, and missing data."""
    if value is None:
        return 0.0
    try:
        v = float(value)
    except (ValueError, TypeError):
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return v


def parse_income_statement(raw: dict[str, Any]) -> dict[str, float]:
    """Parse an income statement dict into cleaned numeric values.

    Expected keys (case-insensitive top-level or nested under *facts*):
        Revenue / TotalRevenue / Revenues
        CostOfGoodsSold / CostOfRevenue / COGS
        NetIncomeLoss / NetIncome
        EarningsPerShareBasic / EarningsPerShareDiluted / EPS

    Returns
    -------
    dict with keys *revenue*, *cogs*, *net_income*, *eps*.
    """
    data = raw.get("facts", raw) if isinstance(raw, dict) else {}
    return {
        "revenue": _safe_float(
            data.get("Revenue") or data.get("TotalRevenue") or data.get("Revenues")
        ),
        "cogs": _safe_float(
            data.get("CostOfGoodsSold") or data.get("CostOfRevenue") or data.get("COGS")
        ),
        "net_income": _safe_float(data.get("NetIncomeLoss") or data.get("NetIncome")),
        "eps": _safe_float(
            data.get("EarningsPerShareBasic")
            or data.get("EarningsPerShareDiluted")
            or data.get("EPS")
        ),
    }


def parse_balance_sheet(raw: dict[str, Any]) -> dict[str, float]:
    """Parse a balance sheet dict into cleaned numeric values.

    Expected keys:
        TotalAssets / Assets
        TotalLiabilities / TotalLiabilitiesNetMinorityInterest / Liabilities
        StockholdersEquity / TotalEquity / TotalStockholdersEquity / Equity

    Returns
    -------
    dict with keys *assets*, *liabilities*, *equity*.
    """
    data = raw.get("facts", raw) if isinstance(raw, dict) else {}
    return {
        "assets": _safe_float(data.get("TotalAssets") or data.get("Assets")),
        "liabilities": _safe_float(
            data.get("TotalLiabilities")
            or data.get("TotalLiabilitiesNetMinorityInterest")
            or data.get("Liabilities")
        ),
        "equity": _safe_float(
            data.get("StockholdersEquity")
            or data.get("TotalEquity")
            or data.get("TotalStockholdersEquity")
            or data.get("Equity")
        ),
    }


def parse_cash_flow(raw: dict[str, Any]) -> dict[str, float]:
    """Parse a cash-flow statement dict into cleaned numeric values.

    Expected keys:
        NetCashProvidedByOperatingActivities / OperatingCashFlow
        NetCashUsedForInvestingActivities / InvestingCashFlow
        NetCashUsedForFinancingActivities / FinancingCashFlow

    Returns
    -------
    dict with keys *operating*, *investing*, *financing*.
    """
    data = raw.get("facts", raw) if isinstance(raw, dict) else {}
    return {
        "operating": _safe_float(
            data.get("NetCashProvidedByOperatingActivities") or data.get("OperatingCashFlow")
        ),
        "investing": _safe_float(
            data.get("NetCashUsedForInvestingActivities") or data.get("InvestingCashFlow")
        ),
        "financing": _safe_float(
            data.get("NetCashUsedForFinancingActivities") or data.get("FinancingCashFlow")
        ),
    }
