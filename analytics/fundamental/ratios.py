"""Financial ratio calculators — P/E, P/B, ROE, D/E, current ratio.

All functions guard division-by-zero by returning *None*.
"""

from __future__ import annotations

import math


def _div_or_none(numerator: float, denominator: float) -> float | None:
    """Return *numerator* / *denominator* or *None* on zero / invalid input."""
    try:
        d = float(denominator)
    except (ValueError, TypeError):
        return None
    if d == 0.0 or math.isnan(d) or math.isinf(d):
        return None
    try:
        n = float(numerator)
    except (ValueError, TypeError):
        return None
    if math.isnan(n) or math.isinf(n):
        return None
    return n / d


def pe_ratio(price: float, eps: float) -> float | None:
    """Price-to-Earnings ratio = price / earnings-per-share."""
    return _div_or_none(price, eps)


def pb_ratio(price: float, book_value_per_share: float) -> float | None:
    """Price-to-Book ratio = price / book-value-per-share."""
    return _div_or_none(price, book_value_per_share)


def roe(net_income: float, equity: float) -> float | None:
    """Return on Equity = net-income / shareholders-equity."""
    return _div_or_none(net_income, equity)


def de_ratio(total_liabilities: float, equity: float) -> float | None:
    """Debt-to-Equity ratio = total-liabilities / shareholders-equity."""
    return _div_or_none(total_liabilities, equity)


def current_ratio(current_assets: float, current_liabilities: float) -> float | None:
    """Current ratio = current-assets / current-liabilities."""
    return _div_or_none(current_assets, current_liabilities)
