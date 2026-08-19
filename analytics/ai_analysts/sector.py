"""Sector Analyst — ingests sector ETF returns and industry rotation.

For the target ticker, identify its sector, fetch sector ETF performance
(last 1m / 3m / 12m), and check if the sector is in rotation (positive
momentum) or out of favor (negative momentum).

The analyst uses yfinance (free) for sector ETF data. Output is a
structured SectorReport with rotation signal.

References
----------
- Sector rotation theory: Stan Nison, Martin Pring — money flows from
  late-cycle sectors (utilities, consumer staples) to early-cycle
  (financials, industrials, tech) during bull transitions.
- Deep-research 2026-08-15: cross-asset / cross-sector rotation is one
  of the few "documented edges" not yet falsified by Oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Sector ETF proxies (US market). Source: ETF.com canonical mapping.
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

# Sector heuristic mapping (industry keywords → sector)
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Technology": [
        "semiconductor",
        "software",
        "tech",
        "computing",
        "ai",
        "chip",
        "hardware",
        "internet",
        "cloud",
        "saas",
    ],
    "Healthcare": ["pharma", "biotech", "medical", "drug", "hospital", "healthcare"],
    "Financials": [
        "bank",
        "insurance",
        "asset management",
        "financial",
        "fintech",
        "payment",
        "credit",
    ],
    "Consumer Discretionary": [
        "retail",
        "restaurant",
        "hotel",
        "travel",
        "auto",
        "apparel",
        "fashion",
        "luxury",
    ],
    "Consumer Staples": ["food", "beverage", "household", "tobacco", "staple", "grocery"],
    "Energy": ["oil", "gas", "petroleum", "energy", "refining", "pipeline"],
    "Industrials": ["industrial", "machinery", "construction", "aerospace", "defense", "logistics"],
    "Materials": ["chemical", "mining", "steel", "metal", "material", "commodity"],
    "Real Estate": ["reit", "property", "real estate", "development"],
    "Utilities": ["utility", "electric", "water", "gas distribution"],
    "Communication Services": ["media", "telecom", "streaming", "entertainment", "advertising"],
}


@dataclass
class SectorReport:
    """Sector rotation analysis for one ticker.

    Attributes
    ----------
    ticker : str
        Target ticker (e.g. "INTC").
    sector : str
        Identified sector (e.g. "Technology").
    sector_etf : str
        ETF ticker representing the sector (e.g. "XLK").
    sector_1m_return : float
        Last 1-month return of the sector ETF.
    sector_3m_return : float
        Last 3-month return.
    sector_12m_return : float
        Last 12-month return.
    rotation_signal : str
        One of: "rotating_in", "rotating_out", "neutral".
    evidence : list[str]
        Bullet-point evidence supporting the signal.
    """

    ticker: str
    sector: str
    sector_etf: str
    sector_1m_return: float = 0.0
    sector_3m_return: float = 0.0
    sector_12m_return: float = 0.0
    rotation_signal: str = "neutral"
    evidence: list[str] = field(default_factory=list)


class SectorAnalyst:
    """Sector rotation analyst.

    Given a ticker + business description, identify the sector, fetch
    the sector ETF performance, and classify rotation signal.
    """

    def __init__(self, *, lookback_days: int = 252) -> None:
        self.lookback_days = lookback_days

    def identify_sector(self, business_summary: str) -> str:
        """Identify sector from company business summary keywords."""
        bs = business_summary.lower()
        scores: dict[str, int] = dict.fromkeys(SECTOR_ETFS, 0)
        for sector, kws in SECTOR_KEYWORDS.items():
            for kw in kws:
                if kw in bs:
                    scores[sector] += 1
        # Pick highest-scoring sector; default to Technology
        best = max(scores, key=lambda s: scores[s])
        if scores[best] == 0:
            return "Technology"  # default
        return best

    def fetch_sector_etf_returns(self, sector_etf: str) -> dict[str, float]:
        """Fetch 1m / 3m / 12m returns for a sector ETF via yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            return {"1m": 0.0, "3m": 0.0, "12m": 0.0}

        try:
            etf = yf.Ticker(sector_etf)
            hist = etf.history(period="1y")  # 1 year of daily bars
            if hist.empty:
                return {"1m": 0.0, "3m": 0.0, "12m": 0.0}
            close = hist["Close"]
            ret_1m = float(close.iloc[-1] / close.iloc[-22] - 1.0) if len(close) > 22 else 0.0
            ret_3m = float(close.iloc[-1] / close.iloc[-66] - 1.0) if len(close) > 66 else 0.0
            ret_12m = float(close.iloc[-1] / close.iloc[0] - 1.0) if len(close) > 0 else 0.0
            return {"1m": ret_1m, "3m": ret_3m, "12m": ret_12m}
        except Exception:
            return {"1m": 0.0, "3m": 0.0, "12m": 0.0}

    def classify_rotation(self, returns: dict[str, float]) -> str:
        """Classify rotation signal from 1m/3m/12m returns.

        Simple rule (v1):
        - rotating_in: all 3 returns positive AND 1m > 3m > 12m OR 1m > 5%
        - rotating_out: all 3 negative OR 1m < -5%
        - neutral: otherwise
        """
        r1 = returns["1m"]
        r3 = returns["3m"]
        r12 = returns["12m"]
        if r1 > 0 and r3 > 0 and r12 > 0 and (r1 > r3 > r12 or r1 > 0.05):
            return "rotating_in"
        if r1 < 0 and r3 < 0 and r12 < 0:
            return "rotating_out"
        if r1 < -0.05 or r3 < -0.05:
            return "rotating_out"
        return "neutral"

    def analyze(self, ticker: str, *, business_summary: str = "") -> SectorReport:
        """Analyze sector rotation for a ticker."""
        sector = self.identify_sector(business_summary)
        etf = SECTOR_ETFS.get(sector, "XLK")
        returns = self.fetch_sector_etf_returns(etf)
        rotation = self.classify_rotation(returns)
        evidence: list[str] = [
            f"Sector {sector} ETF {etf}: 1m={returns['1m']:+.1%}, "
            f"3m={returns['3m']:+.1%}, 12m={returns['12m']:+.1%}"
        ]
        if rotation == "rotating_in":
            evidence.append("Sector momentum positive across all timeframes")
        elif rotation == "rotating_out":
            evidence.append("Sector momentum negative — defensive positioning recommended")
        else:
            evidence.append("Sector momentum mixed — no strong directional bias")
        return SectorReport(
            ticker=ticker,
            sector=sector,
            sector_etf=etf,
            sector_1m_return=returns["1m"],
            sector_3m_return=returns["3m"],
            sector_12m_return=returns["12m"],
            rotation_signal=rotation,
            evidence=evidence,
        )


__all__: list[str] = ["SECTOR_ETFS", "SECTOR_KEYWORDS", "SectorAnalyst", "SectorReport"]
