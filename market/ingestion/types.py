"""BL-301 — Shared types for the data ingestion layer.

Defines:
- OHLCVBar: canonical normalized OHLCV record (Decimal-based)
- RateLimit: per-source throttling configuration
- AssetClass + AssetSpec: instrument metadata
- Quality flags for the normalizer
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class AssetClass(StrEnum):
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_PERP = "crypto_perp"
    FUTURES = "futures"
    FX = "fx"
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"


class SourceId(StrEnum):
    """Identifies an external data provider.

    Each :class:`DataSource` in ``sources.py`` exposes one of these.
    """

    BINANCE_REST = "binance_rest"
    CRYPTODATA = "cryptodata"
    DATABENTO = "databento"
    HISTDATA = "histdata"
    YAHOO = "yahoo"
    STOOQ = "stooq"
    DUKASCOPY = "dukascopy"
    IBKR = "ibkr"


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Per-source throttling configuration.

    The pipeline uses asyncio.Semaphore to cap concurrent requests and a
    sliding-window sleep to respect requests_per_second. On 429 responses
    it switches to cooldown_on_429 backoff.
    """

    requests_per_second: float
    requests_per_minute: int = 60
    concurrent: int = 1
    cooldown_on_429: float = 30.0
    user_agent: str = "oracle-trading/1.0"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class AssetSpec:
    """Static metadata for one (symbol, source) instrument.

    The pipeline uses this to validate that a fetched range is plausible
    (e.g. Binance BTCUSDT 1m starts no earlier than 2017-08) and to set
    per-asset decimal precision on the normalized bar.
    """

    symbol: str
    asset_class: AssetClass
    exchange: str
    point_precision: int = 2
    volume_precision: int = 8
    earliest_available: date | None = None
    multiplier: Decimal = Decimal("1")
    quote_currency: str = "USD"


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """Canonical normalized bar.

    Time is always UTC-aware datetime. Prices are Decimal at the asset's
    declared ``point_precision``; volume at ``volume_precision``. The bar
    is immutable: quality checks must run BEFORE constructing it.
    """

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    symbol: str
    source: SourceId
    timeframe: str


class QualityFlag(StrEnum):
    OHLC_INVALID = "ohlc_invalid"  # high < low or open/close out of range
    VOLUME_NEGATIVE = "volume_negative"
    TIMESTAMP_NONMONOTONIC = "timestamp_nonmonotonic"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    NULL_OR_NAN = "null_or_nan"
    PRECISION_LOSS = "precision_loss"
    SYMBOL_MISMATCH = "symbol_mismatch"
    TIMEFRAME_MISMATCH = "timeframe_mismatch"
    UNKNOWN_SOURCE = "unknown_source"


@dataclass
class NormalizedBatch:
    """Result of one fetch: a stream of bars plus per-line quality flags.

    The pipeline reads this from the normalizer and decides whether to
    MERGE_ALL, MERGE_GOOD_ONLY, or REJECT_BATCH.
    """

    bars: list[OHLCVBar] = field(default_factory=list)
    rejected: list[tuple[int, QualityFlag, str]] = field(default_factory=list)
    source_rows_total: int = 0
    source_rejected: int = 0

    def __iter__(self) -> Iterator[OHLCVBar]:
        return iter(self.bars)
