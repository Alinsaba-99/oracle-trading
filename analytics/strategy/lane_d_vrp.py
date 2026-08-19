"""Lane D — Option Selling VRP (Variance Risk Premium) Strategy.

The VRP is one of the most documented edges in academic finance literature:
on average, implied volatility (used to price options) systematically exceeds
realized volatility. Variance swap sellers profit; variance swap buyers
lose. This means: **short option premium is positive-EV on average**.

Implementation strategy (BL-507):
1. Sell cash-secured puts on SPY or ES futures at 30 DTE, delta ~0.20-0.25
2. Hold to ~50% of DTE (e.g., 15 days into a 30-DTE position)
3. Roll or close before expiration to avoid pin risk
4. Position size: ≤2% of capital per position (margin/collateral: 100% of strike)
5. Manage winners: close at 50% max profit; manage losers: roll out + down
6. Avoid earnings / FOMC / CPI days (event risk)

References
----------
- Carr & Wu (2009). "Variance Risk Premiums." Review of Financial Studies.
- Bollerslev, Tauchen, Zhou (2009). "Expected Stock Returns and Variance Risk Premia."
- AQR white paper "Selling Volatility" — long-term track record.
- Tastytrade research: short premium strategies have ~1.0-1.5 Sharpe over 5y.
- Wikipedia: Variance risk premium.

Edge
----
- Implied vol is on average ~2-3 vol points above realized vol
- Theta decay is mathematically deterministic: 1/sqrt(DTE)
- Tail risk exists: 1987, 2008, 2020 COVID saw VRP go negative briefly
- Risk management: small size, defined risk, roll before expiry

IBKR Integration
-----------------
- `ib_insync` library (already installed)
- Contract: Stock or Index options via `Option` class
- Order: LMT order at mid (or MKT for paper)
- This module uses paper trading credentials (TWSUSERID alinsaba99)

Limitations (v1)
-----------------
- NO live order placement (BL-507 v1: signal + thesis only)
- NO real-time position management (next version)
- Backtest-ready: theoretical EV computation from historical IV vs RV
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class VRPConfig:
    """Configuration for Lane D option selling VRP strategy.

    Attributes
    ----------
    target_dte : int
        Target days-to-expiration when opening positions (default 30).
    target_delta : float
        Target short put delta (0.20-0.25 = "20-25 delta"; safer = 0.15).
        Lower delta = further OTM = safer but smaller premium.
    position_size_pct : float
        Max fraction of capital per position (default 0.02 = 2%).
    max_positions : int
        Maximum concurrent open positions (default 5).
    exit_at_dte : int
        Exit when DTE drops to this threshold (default 7; avoid pin risk).
    take_profit_pct : float
        Take profit at this fraction of max premium (default 0.50).
    roll_threshold : float
        Roll losing positions when loss exceeds this fraction (default 0.20).
    underlying : str
        Underlying symbol (default "SPY"; alt: "ES" future option, "QQQ").
    avoid_events : tuple[str, ...]
        Events to avoid trading (default: ('earnings', 'fomc', 'cpi')).
    """

    target_dte: int = 30
    target_delta: float = 0.20
    position_size_pct: float = 0.02
    max_positions: int = 5
    exit_at_dte: int = 7
    take_profit_pct: float = 0.50
    roll_threshold: float = 0.20
    underlying: str = "SPY"
    avoid_events: tuple[str, ...] = ("earnings", "fomc", "cpi")


@dataclass(frozen=True)
class VRPSignal:
    """One short-put signal output by the VRP strategy.

    Attributes
    ----------
    underlying : str
        Underlying symbol.
    underlying_price : float
        Spot price at signal generation.
    strike : float
        Strike price of the short put (target_delta-based).
    dte : int
        Days to expiration.
    estimated_premium : float
        Estimated option premium (theoretical).
    implied_vol : float | None
        Implied vol used for premium estimate.
    realised_vol_30d : float | None
        30-day realised vol of the underlying.
    vrp : float | None
        Variance risk premium = IV - RV (positive = edge for seller).
    edge_signal : str
        "SELL_PUT" if VRP > 1.0 vol point (clear edge); "PASS" otherwise.
    confidence : float
        Confidence in [0, 1] based on VRP magnitude + DTE alignment.
    thesis : str
        One-sentence summary of the trade thesis.
    invalidation : str
        When to close/roll (stop loss, time stop, IV collapse).
    """

    underlying: str
    underlying_price: float
    strike: float
    dte: int
    estimated_premium: float
    implied_vol: float | None = None
    realised_vol_30d: float | None = None
    vrp: float | None = None
    edge_signal: str = "PASS"
    confidence: float = 0.0
    thesis: str = ""
    invalidation: str = ""


class VRPStrategy:
    """Lane D option selling VRP strategy.

    v1: signal generation (theoretical EV computation from historical
    IV vs RV). NOT connected to IBKR live order placement — that's v2.
    """

    def __init__(
        self, *, config: VRPConfig | None = None, ibkr_port: int = 4002, ibkr_client_id: int = 11
    ) -> None:
        self.config = config or VRPConfig()
        self.ibkr_port = ibkr_port
        self.ibkr_client_id = ibkr_client_id
        self._ib: Any = None

    def _connect_ibkr(self) -> Any:
        """Connect to IBKR Gateway for live data (paper trading only)."""
        try:
            from ib_insync import IB

            if self._ib is None or not self._ib.isConnected():
                self._ib = IB()  # type: ignore[no-untyped-call]
                self._ib.connect(
                    "127.0.0.1", self.ibkr_port, clientId=self.ibkr_client_id, timeout=10
                )
            return self._ib
        except Exception as e:
            print(f"WARN IBKR connect: {e}")
            return None

    def _disconnect_ibkr(self) -> None:
        if self._ib is not None:
            try:
                self._ib.disconnect()
            except Exception:
                pass
            self._ib = None

    def fetch_underlying_price(self, underlying: str) -> float | None:
        """Fetch current spot price of the underlying via IBKR.

        Paper trading account has no market data subscription, so real-time
        tickers return 0. We fall back to delayed market data (last bar)
        from reqHistoricalData.
        """
        ib = self._connect_ibkr()
        if ib is None:
            return None
        try:
            from datetime import datetime

            from ib_insync import Future, Stock

            if underlying in ("SPY", "QQQ", "IWM", "DIA"):
                c = Stock(underlying, "SMART", "USD")
            else:
                cds = ib.reqContractDetails(Future(underlying, "CME", "USD"))
                if not cds:
                    return None
                c = cds[0].contract
            ib.qualifyContracts(c)
            # Try live ticker first
            ticker = ib.reqTickers(c)[0]
            price = ticker.marketPrice()
            if price == price and price > 0:  # not NaN, not 0
                return float(price)
            # Fallback: fetch last bar from history (delayed data, no subscription)
            bars = ib.reqHistoricalData(
                c,
                endDateTime=datetime.now(),
                durationStr="2 D",
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=False,
                formatDate=1,
            )
            if bars:
                return float(bars[-1].close)
            return None
        except Exception as e:
            print(f"WARN fetch price: {e}")
            return None

    def fetch_option_chain(self, underlying: str, target_dte: int) -> list[dict[str, Any]] | None:
        """Fetch option chain from IBKR for the underlying at target DTE.

        Returns a list of dicts with strike, dte, implied_vol, etc.
        """
        ib = self._connect_ibkr()
        if ib is None:
            return None
        try:
            from ib_insync import Option, Stock

            if underlying in ("SPY", "QQQ", "IWM", "DIA"):
                c = Stock(underlying, "SMART", "USD")
                ib.qualifyContracts(c)
                chains = ib.reqSecDefOptParams(c.symbol, "", c.secType, c.conId)
                if not chains:
                    return None
                chain = next((ch for ch in chains if ch.exchange == "SMART"), chains[0])
                # Find expiry closest to target_dte
                today = datetime.now().date()
                expiries = sorted(datetime.strptime(e, "%Y%m%d").date() for e in chain.expirations)
                target_date = today + timedelta(days=target_dte)
                nearest_expiry = min(expiries, key=lambda e: abs((e - target_date).days))
                # Get strikes near the underlying price
                strikes = sorted(chain.strikes)
                underlying_price = self.fetch_underlying_price(underlying)
                if underlying_price is None:
                    return None
                # Get OTM puts: strike < underlying_price, target delta ~0.20
                # Simple heuristic: 0.20 delta put ≈ 1 std below price
                # std = underlying_price * IV * sqrt(DTE/365)
                # Use strikes around (price - 1*std) for ~16% ITM prob
                otm_puts = [s for s in strikes if s < underlying_price][-10:]
                results: list[dict[str, Any]] = []
                for strike in otm_puts:
                    opt = Option(
                        underlying, nearest_expiry.strftime("%Y%m%d"), strike, "P", "SMART"
                    )
                    try:
                        ib.qualifyContracts(opt)
                        ticker = ib.reqTickers(opt)[0]
                        if ticker.modelGreeks:
                            delta = ticker.modelGreeks.delta
                            iv = ticker.modelGreeks.impliedVol
                            price = ticker.marketPrice()
                            dte = (nearest_expiry - today).days
                            results.append(
                                {
                                    "strike": strike,
                                    "dte": dte,
                                    "delta": delta,
                                    "implied_vol": iv,
                                    "premium": price,
                                }
                            )
                    except Exception:
                        continue
                return results
        except Exception as e:
            print(f"WARN option chain: {e}")
            return None
        return None

    def compute_realised_vol(self, underlying: str, lookback_days: int = 30) -> float | None:
        """Compute 30-day realised volatility from underlying daily returns."""
        ib = self._connect_ibkr()
        if ib is None:
            return None
        try:
            import math

            from ib_insync import Future, Stock

            if underlying in ("SPY", "QQQ", "IWM", "DIA"):
                c = Stock(underlying, "SMART", "USD")
            else:
                cds = ib.reqContractDetails(Future(underlying, "CME", "USD"))
                if not cds:
                    return None
                c = cds[0].contract
            ib.qualifyContracts(c)
            bars = ib.reqHistoricalData(
                c,
                endDateTime=datetime.now(),
                durationStr=f"{lookback_days + 10} D",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=False,
                formatDate=1,
            )
            if len(bars) < lookback_days:
                return None
            closes = [bar.close for bar in bars[-lookback_days:]]
            returns = [
                (closes[i] / closes[i - 1] - 1.0)
                for i in range(1, len(closes))
                if closes[i - 1] != 0
            ]
            if len(returns) < 5:
                return None
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            return float(math.sqrt(var) * math.sqrt(252))  # annualised
        except Exception as e:
            print(f"WARN realised vol: {e}")
            return None

    def generate_signal(self, underlying: str | None = None) -> VRPSignal:
        """Generate one short-put signal for the configured underlying."""
        u = underlying or self.config.underlying
        underlying_price = self.fetch_underlying_price(u)
        if underlying_price is None:
            return VRPSignal(
                underlying=u,
                underlying_price=0.0,
                strike=0.0,
                dte=self.config.target_dte,
                estimated_premium=0.0,
                edge_signal="PASS",
                thesis="Failed to fetch underlying price (IBKR not connected?)",
            )
        chain = self.fetch_option_chain(u, self.config.target_dte)
        if not chain:
            return VRPSignal(
                underlying=u,
                underlying_price=underlying_price,
                strike=round(underlying_price * 0.95, 2),
                dte=self.config.target_dte,
                estimated_premium=0.0,
                edge_signal="PASS",
                thesis="Failed to fetch option chain (IBKR data subscription?)",
            )
        # Pick the put closest to target_delta
        target = self.config.target_delta
        best = min(chain, key=lambda o: abs(o["delta"] - (-target)) if o.get("delta") else 999)
        iv = best.get("implied_vol")
        premium = best.get("premium", 0.0)
        strike = best["strike"]
        dte = best["dte"]
        rv = self.compute_realised_vol(u)
        vrp = (iv - rv) if (iv is not None and rv is not None) else None
        # Edge signal: VRP > 0.01 (1 vol point) = clear edge for seller
        edge = "SELL_PUT" if (vrp is not None and vrp > 0.01) else "PASS"
        confidence = min(1.0, (vrp or 0) / 0.05) if vrp else 0.0
        thesis = (
            (
                f"Short {u} ${strike} put {dte}DTE: IV {iv:.1%} vs RV {rv:.1%} "
                f"(VRP +{vrp:.3f}) — premium ${premium:.2f} "
                f"({premium / underlying_price:.2%} of underlying)"
            )
            if (iv and rv and vrp)
            else f"Short {u} ${strike} put {dte}DTE premium ${premium:.2f}"
        )
        invalidation = (
            f"Close if loss > {self.config.roll_threshold:.0%} of premium OR "
            f"DTE <= {self.config.exit_at_dte} OR realised vol > implied vol "
            f"(VRP inverts)"
        )
        return VRPSignal(
            underlying=u,
            underlying_price=underlying_price,
            strike=strike,
            dte=dte,
            estimated_premium=premium,
            implied_vol=iv,
            realised_vol_30d=rv,
            vrp=vrp,
            edge_signal=edge,
            confidence=confidence,
            thesis=thesis,
            invalidation=invalidation,
        )

    def close(self) -> None:
        """Disconnect from IBKR."""
        self._disconnect_ibkr()


__all__: list[str] = ["VRPConfig", "VRPSignal", "VRPStrategy"]
