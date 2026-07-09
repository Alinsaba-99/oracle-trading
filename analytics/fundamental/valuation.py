"""Valuation models — Discounted Cash Flow (DCF) and Graham Number.

All functions guard division-by-zero and invalid inputs by returning *None*.
"""

from __future__ import annotations

import math


def dcf(
    free_cash_flows: list[float], growth_rate: float, discount_rate: float, terminal_growth: float
) -> float | None:
    """Two-stage DCF valuation.

    Stage 1 — project each FCF forward at *growth_rate* and discount back
    to present value using *discount_rate*.

    Stage 2 — compute a terminal value using the Gordon Growth Model:

        terminal_value = last_fcf * (1 + terminal_growth)
                       / (discount_rate - terminal_growth)

    Parameters
    ----------
    free_cash_flows : list[float]
        Historical or base-year free cash flows, one per period.
    growth_rate : float
        Per-period growth rate during the projection stage (e.g. 0.05).
    discount_rate : float
        Weighted-average cost of capital (e.g. 0.10).
    terminal_growth : float
        Perpetual growth rate for the terminal value (e.g. 0.02).

    Returns
    -------
    float | None
        Sum of discounted FCFs + discounted terminal value, or *None*
        if inputs are invalid.
    """
    if not free_cash_flows:
        return None

    if discount_rate <= terminal_growth:
        return None

    try:
        dr = float(discount_rate)
        gr = float(growth_rate)
        tg = float(terminal_growth)
    except (ValueError, TypeError):
        return None

    if dr <= tg or math.isnan(dr) or math.isinf(dr):
        return None

    try:
        fcf_vals = [float(f) for f in free_cash_flows]
    except (ValueError, TypeError):
        return None

    if any(math.isnan(f) or math.isinf(f) for f in fcf_vals):
        return None
    if math.isnan(gr) or math.isinf(gr):
        return None
    if math.isnan(tg) or math.isinf(tg):
        return None

    # Stage 1: discount each projected FCF
    pv_fcfs = 0.0
    for i, fcf in enumerate(fcf_vals):
        projected = fcf * (1.0 + gr) ** (i + 1)
        pv_fcfs += projected / (1.0 + dr) ** (i + 1)

    # Stage 2: terminal value based on last PROJECTED FCF, discounted back
    last_projected = fcf_vals[-1] * (1.0 + gr) ** len(fcf_vals)
    terminal_value = last_projected * (1.0 + tg) / (dr - tg)
    pv_terminal = terminal_value / (1.0 + dr) ** len(fcf_vals)

    return pv_fcfs + pv_terminal


def graham_number(eps: float, book_value_per_share: float) -> float | None:
    """Graham Number = sqrt(22.5 * EPS * BVPS).

    The 22.5 multiplier comes from Graham's rule of thumb: P/E ≤ 15 and
    P/B ≤ 1.5 → product ceiling of 22.5.

    Returns *None* if either input is non-positive or invalid.
    """
    try:
        e = float(eps)
        b = float(book_value_per_share)
    except (ValueError, TypeError):
        return None

    if e <= 0.0 or b <= 0.0:
        return None
    if math.isnan(e) or math.isinf(e) or math.isnan(b) or math.isinf(b):
        return None

    return math.sqrt(22.5 * e * b)
