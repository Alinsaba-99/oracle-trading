"""Instrument registry for the multi-asset, multi-timeframe, multi-venue backbone (R0).

Every instrument carries the metadata the data layer needs to fetch OHLCV
(yfinance / ccxt / MetaApi / a futures feed), which prop-firm venue allows it
(``the5ers`` = MT5 CFD, ``lucid`` = exchange futures, ``free`` = unconstrained),
and its product type. Session calendars and contract specs (point value, min
tick) are intentionally left light here — authoritative session times land in
the ChallengeSimulator session model (R3) and contract specs in the sizing /
execution layer (R3/F5), so we do not ship guesses.

This is the single source of truth for the R0 data backbone: providers write
into the existing ``data/ohlcv`` Parquet layout that ``BacktestDataProvider``
already consumes, keyed by ``Instrument.id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class AssetClass(StrEnum):
    FX = "fx"
    METAL = "metal"
    INDEX = "index"
    ENERGY = "energy"
    RATE = "rate"
    CRYPTO = "crypto"


class ProductType(StrEnum):
    """How the instrument trades — drives data source and venue eligibility."""

    SPOT = "spot"  # cash FX / spot metal (CFD-able on MT5)
    CFD = "cfd"  # MT5 contract-for-difference (The5ers)
    FUTURE = "future"  # exchange-listed futures (Lucid)


class Venue(StrEnum):
    THE5ERS = "the5ers"
    LUCID = "lucid"
    FREE = "free"


class DataSource(StrEnum):
    YFINANCE = "yfinance"
    CCXT = "ccxt"
    METAAPI = "metaapi"
    FUTURES = "futures"  # Rithmic/Tradovate/Polygon intraday futures (TBD)


def _v(*venues: Venue) -> frozenset[Venue]:
    return frozenset(venues)


@dataclass(frozen=True)
class Instrument:
    """One tradeable market, as the engine sees it."""

    id: str  # canonical id used across the engine ("XAUUSD")
    name: str
    asset_class: AssetClass
    product_type: ProductType
    # symbol per data source (None = not fetchable from that source)
    yf: str | None = None  # yfinance ticker ("GC=F")
    ccxt: str | None = None  # ccxt unified symbol ("BTC/USDT")
    metaapi: str | None = None  # MT5 symbol ("XAUUSD.r")
    futures: str | None = None  # futures root/continuous ("ES")
    venues: frozenset[Venue] = frozenset()
    # trading session in UTC (for intraday-flat enforcement; None = 24/7).
    # Populated authoritatively by the R3 session calendar, not guessed here.
    session_open_utc: str | None = None
    session_close_utc: str | None = None
    point_value: float = 1.0  # $ per point — finalized in sizing/execution layer
    min_tick: float = 0.01


class InstrumentRegistry:
    """Extensible registry. ``DEFAULTS`` seeds the all-asset universe; add via ``register``."""

    def __init__(self, items: list[Instrument] | None = None) -> None:
        self._by_id: dict[str, Instrument] = {}
        for item in items or self.DEFAULTS:
            self.register(item)

    def register(self, inst: Instrument) -> None:
        if inst.id in self._by_id:
            raise ValueError(f"duplicate instrument id: {inst.id}")
        self._by_id[inst.id] = inst

    def get(self, instrument_id: str) -> Instrument:
        return self._by_id[instrument_id]

    def all(self) -> list[Instrument]:
        return list(self._by_id.values())

    def by_venue(self, venue: Venue) -> list[Instrument]:
        return [i for i in self._by_id.values() if venue in i.venues]

    def by_source(self, source: DataSource) -> list[Instrument]:
        attr = {
            DataSource.YFINANCE: "yf",
            DataSource.CCXT: "ccxt",
            DataSource.METAAPI: "metaapi",
            DataSource.FUTURES: "futures",
        }[source]
        return [i for i in self._by_id.values() if getattr(i, attr, None) is not None]

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, instrument_id: object) -> bool:
        return instrument_id in self._by_id

    # ------------------------------------------------------------------ seed
    # All-asset universe, venue-tagged. The5ers = MT5 CFD (spot FX / metals /
    # indices); Lucid = CME futures (intraday-only); FREE = everything.
    DEFAULTS: ClassVar[list[Instrument]] = [
        # --- FX spot / CFD (The5ers MT5; yfinance daily proxy) ---
        Instrument(
            "EURUSD",
            "Euro / USD",
            AssetClass.FX,
            ProductType.SPOT,
            yf="EURUSD=X",
            metaapi="EURUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "GBPUSD",
            "Pound / USD",
            AssetClass.FX,
            ProductType.SPOT,
            yf="GBPUSD=X",
            metaapi="GBPUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "USDJPY",
            "USD / Yen",
            AssetClass.FX,
            ProductType.SPOT,
            yf="USDJPY=X",
            metaapi="USDJPY",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "USDCHF",
            "USD / Franc",
            AssetClass.FX,
            ProductType.SPOT,
            yf="USDCHF=X",
            metaapi="USDCHF",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "AUDUSD",
            "Aussie / USD",
            AssetClass.FX,
            ProductType.SPOT,
            yf="AUDUSD=X",
            metaapi="AUDUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "USDCAD",
            "USD / Loonie",
            AssetClass.FX,
            ProductType.SPOT,
            yf="USDCAD=X",
            metaapi="USDCAD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "NZDUSD",
            "Kiwi / USD",
            AssetClass.FX,
            ProductType.SPOT,
            yf="NZDUSD=X",
            metaapi="NZDUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "EURGBP",
            "Euro / Pound",
            AssetClass.FX,
            ProductType.SPOT,
            yf="EURGBP=X",
            metaapi="EURGBP",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "EURJPY",
            "Euro / Yen",
            AssetClass.FX,
            ProductType.SPOT,
            yf="EURJPY=X",
            metaapi="EURJPY",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "GBPJPY",
            "Pound / Yen",
            AssetClass.FX,
            ProductType.SPOT,
            yf="GBPJPY=X",
            metaapi="GBPJPY",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        # --- Metals spot / CFD (The5ers) ---
        Instrument(
            "XAUUSD",
            "Gold spot",
            AssetClass.METAL,
            ProductType.SPOT,
            metaapi="XAUUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "XAGUSD",
            "Silver spot",
            AssetClass.METAL,
            ProductType.SPOT,
            metaapi="XAGUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "XPTUSD",
            "Platinum spot",
            AssetClass.METAL,
            ProductType.SPOT,
            metaapi="XPTUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "XPDUSD",
            "Palladium spot",
            AssetClass.METAL,
            ProductType.SPOT,
            metaapi="XPDUSD",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        # --- Index CFD (The5ers; yfinance cash-index proxy) ---
        Instrument(
            "SP500",
            "S&P 500 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^GSPC",
            metaapi="SP500",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "NAS100",
            "Nasdaq 100 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^NDX",
            metaapi="NAS100",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "US30",
            "Dow 30 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^DJI",
            metaapi="US30",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "DAX",
            "Dax 40 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^GDAXI",
            metaapi="GER40",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "UK100",
            "FTSE 100 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^FTSE",
            metaapi="UK100",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        Instrument(
            "JP225",
            "Nikkei 225 CFD",
            AssetClass.INDEX,
            ProductType.CFD,
            yf="^N225",
            metaapi="JP225",
            venues=_v(Venue.THE5ERS, Venue.FREE),
        ),
        # --- Index futures (Lucid; yfinance continuous proxy) ---
        Instrument(
            "ES",
            "E-mini S&P 500",
            AssetClass.INDEX,
            ProductType.FUTURE,
            yf="ES=F",
            futures="ES",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "NQ",
            "E-mini Nasdaq 100",
            AssetClass.INDEX,
            ProductType.FUTURE,
            yf="NQ=F",
            futures="NQ",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "YM",
            "E-mini Dow",
            AssetClass.INDEX,
            ProductType.FUTURE,
            yf="YM=F",
            futures="YM",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "RTY",
            "E-mini Russell 2000",
            AssetClass.INDEX,
            ProductType.FUTURE,
            yf="RTY=F",
            futures="RTY",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        # --- Metals futures (Lucid) ---
        Instrument(
            "GC",
            "Gold futures",
            AssetClass.METAL,
            ProductType.FUTURE,
            yf="GC=F",
            futures="GC",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "SI",
            "Silver futures",
            AssetClass.METAL,
            ProductType.FUTURE,
            yf="SI=F",
            futures="SI",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        # --- Energy futures (Lucid) ---
        Instrument(
            "CL",
            "WTI Crude futures",
            AssetClass.ENERGY,
            ProductType.FUTURE,
            yf="CL=F",
            futures="CL",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "NG",
            "Natural Gas futures",
            AssetClass.ENERGY,
            ProductType.FUTURE,
            yf="NG=F",
            futures="NG",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "RB",
            "RBOB Gasoline futures",
            AssetClass.ENERGY,
            ProductType.FUTURE,
            yf="RB=F",
            futures="RB",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "HO",
            "Heating Oil futures",
            AssetClass.ENERGY,
            ProductType.FUTURE,
            yf="HO=F",
            futures="HO",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        # --- Rates futures (Lucid) ---
        Instrument(
            "ZN",
            "10yr Treasury futures",
            AssetClass.RATE,
            ProductType.FUTURE,
            yf="ZN=F",
            futures="ZN",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "ZB",
            "30yr Bond futures",
            AssetClass.RATE,
            ProductType.FUTURE,
            yf="ZB=F",
            futures="ZB",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "ZF",
            "5yr Treasury futures",
            AssetClass.RATE,
            ProductType.FUTURE,
            yf="ZF=F",
            futures="ZF",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        # --- FX futures (Lucid) ---
        Instrument(
            "6E",
            "Euro FX futures",
            AssetClass.FX,
            ProductType.FUTURE,
            yf="6E=F",
            futures="6E",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "6B",
            "Pound FX futures",
            AssetClass.FX,
            ProductType.FUTURE,
            yf="6B=F",
            futures="6B",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "6J",
            "Yen FX futures",
            AssetClass.FX,
            ProductType.FUTURE,
            yf="6J=F",
            futures="6J",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        # --- Crypto spot (ccxt intraday + yfinance daily) ---
        Instrument(
            "BTC",
            "Bitcoin",
            AssetClass.CRYPTO,
            ProductType.SPOT,
            yf="BTC-USD",
            ccxt="BTC/USDT",
            venues=_v(Venue.FREE, Venue.THE5ERS),
        ),
        Instrument(
            "ETH",
            "Ethereum",
            AssetClass.CRYPTO,
            ProductType.SPOT,
            yf="ETH-USD",
            ccxt="ETH/USDT",
            venues=_v(Venue.FREE, Venue.THE5ERS),
        ),
        Instrument(
            "SOL",
            "Solana",
            AssetClass.CRYPTO,
            ProductType.SPOT,
            yf="SOL-USD",
            ccxt="SOL/USDT",
            venues=_v(Venue.FREE, Venue.THE5ERS),
        ),
        # --- Crypto futures (Lucid; CME) ---
        Instrument(
            "BTF",
            "Bitcoin futures",
            AssetClass.CRYPTO,
            ProductType.FUTURE,
            yf="BTC=F",
            futures="BRR",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
        Instrument(
            "ETHF",
            "Ethereum futures",
            AssetClass.CRYPTO,
            ProductType.FUTURE,
            yf="ETH=F",
            futures="ETH",
            venues=_v(Venue.LUCID, Venue.FREE),
        ),
    ]


def default_registry() -> InstrumentRegistry:
    """Convenience: the seeded all-asset registry."""
    return InstrumentRegistry()
