"""Fundamental Analyst — SimFin bulk fundamentals + Piotroski + Greenblatt.

Wraps the existing analytics.strategy.catalog.value (BL-505) to compute
Piotroski F-Score, Greenblatt Magic Formula rank, and 12-month past
return for the target ticker. Returns a FundamentalReport for the
Synthesizer.

This analyst DOES NOT call any LLM — it's purely deterministic. The
LLM Synthesizer consumes this report alongside the other analysts'
reports to form the final thesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from analytics.fundamental.simfin_loader import SimFinLoader
from analytics.strategy.catalog.value import PiotroskiFScore


@dataclass
class FundamentalReport:
    """Fundamental analysis for one ticker.

    Attributes
    ----------
    ticker : str
        Target ticker (SimFin SimFinId resolved).
    simfin_id : int
        SimFin ID for the company.
    company_name : str
        Company name.
    f_score : int
        Piotroski F-Score (0-9).
    magic_formula_rank : int | None
        Greenblatt Magic Formula rank within the universe.
    return_12m : float
        12-month past return.
    pb_ratio : float | None
        Price-to-book ratio (if available).
    pe_ratio : float | None
        Price-to-earnings ratio (if available).
    revenue_growth_yoy : float | None
        Year-over-year revenue growth.
    net_income_growth_yoy : float | None
        YoY net income growth.
    gross_margin : float | None
        Current gross margin.
    gross_margin_trend : str
        "expanding", "stable", "contracting".
    evidence : list[str]
        Bullet-point evidence for the synthesizer.
    """

    ticker: str
    simfin_id: int = 0
    company_name: str = ""
    f_score: int = 0
    magic_formula_rank: int | None = None
    return_12m: float = 0.0
    pb_ratio: float | None = None
    pe_ratio: float | None = None
    revenue_growth_yoy: float | None = None
    net_income_growth_yoy: float | None = None
    gross_margin: float | None = None
    gross_margin_trend: str = "stable"
    evidence: list[str] = field(default_factory=list)


class FundamentalAnalyst:
    """Fundamental analyst using SimFin bulk data.

    Computes Piotroski F-Score + Greenblatt Magic Formula rank + 12-mo
    past return for a target ticker. Mirrors the existing Lane B value
    catalog (BL-505) but per-ticker for the AI swarm.
    """

    def __init__(self, loader: SimFinLoader) -> None:
        self.loader = loader
        self._income: pl.DataFrame | None = None
        self._balance: pl.DataFrame | None = None
        self._cashflow: pl.DataFrame | None = None
        self._prices: pl.DataFrame | None = None
        self._companies: pl.DataFrame | None = None

    def _load_all(self) -> None:
        if self._income is None:
            self._income = self.loader.income_statements()
        if self._balance is None:
            self._balance = self.loader.balance_sheets()
        if self._cashflow is None:
            self._cashflow = self.loader.cash_flows()
        if self._prices is None:
            self._prices = self.loader.daily_prices()
        if self._companies is None:
            self._companies = self.loader.companies()

    def find_simfin_id(self, ticker_or_name: str) -> tuple[int, str] | None:
        """Find SimFinId by company name (SimFin bulk doesn't expose ticker)."""
        self._load_all()
        assert self._companies is not None
        needle = ticker_or_name.upper()
        mask = self._companies["Company Name"].str.to_uppercase().str.contains(needle)
        matches = self._companies.filter(mask).head(3)
        if matches.height == 0:
            return None
        # Return the first match
        row = matches.row(0, named=True)
        return int(row["SimFinId"]), str(row["Company Name"])

    def analyze(
        self, ticker_or_name: str, *, as_of: pl.DataFrame | None = None
    ) -> FundamentalReport:
        """Analyze fundamentals for a ticker (by company name)."""
        self._load_all()
        match = self.find_simfin_id(ticker_or_name)
        if match is None:
            return FundamentalReport(
                ticker=ticker_or_name, evidence=[f"Company '{ticker_or_name}' not found in SimFin"]
            )
        simfin_id, company_name = match

        # Filter income/balance/cashflow for this SimFinId
        inc = self._income.filter(pl.col("SimFinId") == simfin_id)  # type: ignore[union-attr]
        bal = self._balance.filter(pl.col("SimFinId") == simfin_id)  # type: ignore[union-attr]
        cf = self._cashflow.filter(pl.col("SimFinId") == simfin_id)  # type: ignore[union-attr]

        if inc.height == 0 or bal.height == 0 or cf.height == 0:
            return FundamentalReport(
                ticker=ticker_or_name,
                simfin_id=simfin_id,
                company_name=company_name,
                evidence=["Insufficient fundamental data (income/balance/cashflow empty)"],
            )

        # Sort by publish_date and take most recent
        inc = inc.sort("Publish Date", descending=True)
        bal = bal.sort("Publish Date", descending=True)
        cf = cf.sort("Publish Date", descending=True)

        # Most recent + previous (for YoY growth + F-Score prev period)
        inc_recent = inc.row(0, named=True)
        inc_prev = inc.row(1, named=True) if inc.height > 1 else inc_recent
        bal_recent = bal.row(0, named=True)
        bal_prev = bal.row(1, named=True) if bal.height > 1 else bal_recent
        cf_recent = cf.row(0, named=True)

        # F-Score components
        total_assets = bal_recent.get("Total Assets") or 1
        total_assets_prev = bal_prev.get("Total Assets") or 1
        roa = (inc_recent.get("Net Income") or 0) / total_assets if total_assets else 0
        roa_prev = (inc_prev.get("Net Income") or 0) / total_assets_prev if total_assets_prev else 0
        cfo = (
            (cf_recent.get("Net Cash from Operating Activities") or 0) / total_assets
            if total_assets
            else 0
        )
        current_assets = bal_recent.get("Total Current Assets") or 0
        current_liab = bal_recent.get("Total Current Liabilities") or 1
        current_ratio = current_assets / current_liab if current_liab else 0
        current_ratio_prev = (bal_prev.get("Total Current Assets") or 0) / (
            bal_prev.get("Total Current Liabilities") or 1
        )
        leverage = (bal_recent.get("Long Term Debt") or 0) / total_assets if total_assets else 0
        leverage_prev = (
            (bal_prev.get("Long Term Debt") or 0) / total_assets_prev if total_assets_prev else 0
        )
        gross_margin = (inc_recent.get("Gross Profit") or 0) / (inc_recent.get("Revenue") or 1)
        gross_margin_prev = (inc_prev.get("Gross Profit") or 0) / (inc_prev.get("Revenue") or 1)
        revenue = inc_recent.get("Revenue") or 0
        revenue_prev = inc_prev.get("Revenue") or 0
        asset_turnover = revenue / total_assets if total_assets else 0
        asset_turnover_prev = revenue_prev / total_assets_prev if total_assets_prev else 0

        # Piotroski F-Score (9-point)
        f_score = PiotroskiFScore.compute(
            roa=roa,
            cfo=cfo,
            roa_prev=roa_prev,
            accruals=0.0,
            leverage_prev=leverage_prev,
            leverage_curr=leverage,
            current_ratio_prev=current_ratio_prev,
            current_ratio_curr=current_ratio,
            equity_issued=(bal_recent.get("Shares (Diluted)") or 0)
            > (bal_prev.get("Shares (Diluted)") or 0),
            gross_margin_prev=gross_margin_prev,
            gross_margin_curr=gross_margin,
            asset_turnover_prev=asset_turnover_prev,
            asset_turnover_curr=asset_turnover,
        )

        # YoY growth
        revenue_growth_yoy = (revenue / revenue_prev - 1.0) if revenue_prev > 0 else None
        net_income = inc_recent.get("Net Income") or 0
        net_income_prev = inc_prev.get("Net Income") or 0
        net_income_growth_yoy = (
            (net_income / net_income_prev - 1.0) if net_income_prev > 0 else None
        )

        # 12-month past return from shareprices
        assert self._prices is not None  # ensured by _ensure_data()
        prices = self._prices
        pr = prices if "date" in prices.columns else prices.rename({"Date": "date"})
        pr_ticker = pr.filter(pl.col("SimFinId") == simfin_id).sort("date")
        return_12m = 0.0
        if pr_ticker.height > 252:
            close = pr_ticker["Close"]
            return_12m = float(close[-1] / close[-253] - 1.0)

        # Gross margin trend
        if gross_margin > gross_margin_prev + 0.02:
            gross_margin_trend = "expanding"
        elif gross_margin < gross_margin_prev - 0.02:
            gross_margin_trend = "contracting"
        else:
            gross_margin_trend = "stable"

        # Evidence
        evidence: list[str] = [
            f"F-Score: {f_score}/9 ({'high quality' if f_score >= 7 else 'mixed' if f_score >= 5 else 'low quality'})",
            f"Revenue YoY: {revenue_growth_yoy:+.1%}"
            if revenue_growth_yoy is not None
            else "Revenue YoY: n/a",
            f"Net Income YoY: {net_income_growth_yoy:+.1%}"
            if net_income_growth_yoy is not None
            else "Net Income YoY: n/a",
            f"Gross Margin: {gross_margin:.1%} ({gross_margin_trend})",
            f"12-mo return: {return_12m:+.1%}",
            f"Leverage: {leverage:.1%} (Δ vs prev: {leverage - leverage_prev:+.1%})",
            f"Current Ratio: {current_ratio:.2f}",
        ]
        if f_score >= 7 and revenue_growth_yoy and revenue_growth_yoy > 0:
            evidence.append("✅ High F-Score + revenue growth — turnaround candidate")
        if gross_margin_trend == "contracting":
            evidence.append("⚠️ Gross margin contracting — margin pressure risk")
        if leverage > 0.5:
            evidence.append("⚠️ High leverage (>50%) — balance sheet risk")

        return FundamentalReport(
            ticker=ticker_or_name,
            simfin_id=simfin_id,
            company_name=company_name,
            f_score=f_score,
            return_12m=return_12m,
            revenue_growth_yoy=revenue_growth_yoy,
            net_income_growth_yoy=net_income_growth_yoy,
            gross_margin=gross_margin,
            gross_margin_trend=gross_margin_trend,
            evidence=evidence,
        )


__all__: list[str] = ["FundamentalAnalyst", "FundamentalReport"]
