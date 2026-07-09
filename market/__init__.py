"""Market data ingestion — sources, normalizers, and pipelines."""

from market.ingestion import IngestionPipeline
from market.normalizer import Normalizer
from market.sources import BaseSource, BinanceWebSocketSource, CoinPaprikaSource, yfinanceSource

__all__ = [
    "BaseSource",
    "BinanceWebSocketSource",
    "CoinPaprikaSource",
    "IngestionPipeline",
    "Normalizer",
    "yfinanceSource",
]
