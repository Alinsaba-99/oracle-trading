"""BL-301 — Data source adapters (5 zero-cost providers).

Each adapter conforms to the :class:`DataSource` protocol (duck-typed):

    def name(self) -> str                                   # unique
    def rate_limit(self) -> RateLimit
    def asset_spec(self, symbol: str) -> AssetSpec
    def fetch_range(self, symbol: str, timeframe: str,
                   start: date, end: date) -> Iterator[OHLCVBar]
    def is_paused(self) -> bool          # 429 backoff still in effect

Adapters live behind their concrete class so that adding BL-301.b adapters
(Dukascopy full FX, Polygon, Stooq intraday) is additive.
"""
from __future__ import annotations

import csv
import io
import logging
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timezone

UTC = UTC, timezone
UTC = timezone.utc
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable
from urllib.request import Request, urlopen

from market.ingestion.types import AssetClass, AssetSpec, OHLCVBar, RateLimit, SourceId

logger = logging.getLogger("oracle.market.ingestion.sources")


@runtime_checkable
class DataSource(Protocol):
    name: SourceId
    rate_limit: RateLimit

    def asset_spec(self, symbol: str) -> AssetSpec: ...

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]: ...

    def is_paused(self) -> bool: ...


class HttpSource:
    """Mixin providing GET-with-UA, JSON decode, pause-on-429."""

    def __init__(self) -> None:
        self._paused_until: float = 0.0

    def is_paused(self) -> bool:
        return time.monotonic() < self._paused_until

    def _paused_seconds_remaining(self) -> float:
        return max(0.0, self._paused_until - time.monotonic())

    def _pause(self, seconds: float) -> None:
        self._paused_until = time.monotonic() + seconds
        logger.warning("%s paused for %.1fs", self.name, seconds)

    def _get(self, url: str, *, timeout: int = 30) -> bytes:
        req = Request(
            url,
            headers={"User-Agent": self.rate_limit.user_agent, "Accept": "*/*"},
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                if resp.status == 429:
                    self._pause(self.rate_limit.cooldown_on_429)
                    raise RuntimeError(f"429 from {self.name}: {url[:120]}")
                return resp.read()
        except Exception as exc:
            if hasattr(exc, "code") and exc.code == 429:
                self._pause(self.rate_limit.cooldown_on_429)
            raise

    def _cooldown_until_clear(self, max_wait: float = 90.0) -> None:
        start = time.monotonic()
        while self.is_paused() and (time.monotonic() - start) < max_wait:
            time.sleep(min(2.0, self._paused_seconds_remaining()))


# ----------------------------------------------------------------------
# Binance REST — public klines endpoint
# Range: BTCUSDT 1m from 2017-08-17. No API key.
# Rate limit: 1200 req/min, weight 2 per klines call. We use 1 per second.
# ----------------------------------------------------------------------
class BinanceREST(HttpSource):
    """Adapter for the Binance public ``klines`` endpoint.

    URL pattern:
      GET https://api.binance.com/api/v3/klines
        ?symbol={symbol}&interval={tf}&startTime={ms}&endTime={ms}&limit=1000

    Returns up to 1000 candeles per call. We paginate via ``startTime``.
    """

    name = SourceId.BINANCE_REST
    BASE_URL = "https://api.binance.com/api/v3/klines"

    INTERVAL_MAP: dict[str, str] = {
        "1s": "1s",
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M",
    }

    CRYPTO_EARLIEST = {"1m": date(2017, 8, 17), "1h": date(2017, 8, 17), "1d": date(2017, 1, 1)}

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=10.0,
            requests_per_minute=1200,
            concurrent=4,
            user_agent="oracle-trading/1.0 (research)",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        sym = symbol.upper()
        return AssetSpec(
            symbol=sym,
            asset_class=AssetClass.CRYPTO_SPOT if "PERP" not in sym else AssetClass.CRYPTO_PERP,
            exchange="binance",
            point_precision=8 if "BTC" in sym or "ETH" in sym else 4,
            volume_precision=8,
            earliest_available=self.CRYPTO_EARLIEST.get("1m", date(2017, 8, 17)),
            quote_currency=sym.split("USDT")[-1] if "USDT" in sym else "USDT",
        )

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]:
        interval = self.INTERVAL_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"BinanceREST: unsupported timeframe {timeframe}")
        start_ms = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        end_ms = int(datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC).timestamp() * 1000)
        spec = self.asset_spec(symbol)
        ms = start_ms
        while ms < end_ms:
            self._cooldown_until_clear()
            url = (
                f"{self.BASE_URL}?symbol={symbol.upper()}&interval={interval}"
                f"&startTime={ms}&endTime={end_ms}&limit=1000"
            )
            data = self._get_json(url)
            if not data:
                break
            for row in data:
                o, h, lo, c, v = (Decimal(str(row[k])) for k in (1, 2, 3, 4, 5))
                t = datetime.fromtimestamp(row[0] / 1000.0, tz=UTC)
                yield OHLCVBar(t, o, h, lo, c, v, spec.symbol, self.name, timeframe)
            ms = int(data[-1][6]) + 1
            time.sleep(1.0 / self.rate_limit.requests_per_second)

    def _get_json(self, url: str) -> list:
        import json

        raw = self._get(url)
        return json.loads(raw)


# ----------------------------------------------------------------------
# CryptoDataDownload — bulk monthly/annual CSVs (no API, no key).
# Supports BTC, ETH, top alts on Binance, Coinbase, Kraken, Bitfinex.
# Range: depends on exchange; spot BTC on Binance: 2014→today 1d,
# 2017→today 1m.
# URL: https://www.cryptodatadownload.com/data/binance/{sym}/{ym}/{sym}-{tf}-2024-01.csv.gz
# ----------------------------------------------------------------------
class CryptoDataDownload(HttpSource):
    name = SourceId.CRYPTODATA
    BASE_URL = "https://www.cryptodatadownload.com/cdd/"

    TF_DIR: dict[str, str] = {
        "1m": "minutework",
        "5m": "5minwork",
        "1h": "hourwork",
        "1d": "dailywork",
    }

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=0.5,
            requests_per_minute=30,
            concurrent=2,
            user_agent="oracle-trading/1.0 (research)",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        return AssetSpec(
            symbol=symbol.upper(),
            asset_class=AssetClass.CRYPTO_SPOT,
            exchange="binance",
            point_precision=8 if any(c in symbol for c in ("BTC", "ETH")) else 4,
            volume_precision=8,
            earliest_available=date(2017, 1, 1),
            quote_currency="USDT" if "USDT" in symbol.upper() else "USD",
        )

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]:
        self._cooldown_until_clear()
        url = f"{self.BASE_URL}{symbol.upper()}_{timeframe}_2024-01.csv.gz"
        req = Request(url, headers={"User-Agent": self.rate_limit.user_agent})
        from urllib.error import HTTPError

        try:
            with urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except HTTPError as exc:
            if exc.code == 404:
                logger.warning(
                    "%s: no historical archive for %s %s (try BinanceREST)",
                    self.name,
                    symbol,
                    timeframe,
                )
                return
            raise
        text = raw.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        spec = self.asset_spec(symbol)
        for row in reader:
            try:
                t = datetime.fromisoformat(
                    row.get("Unix", row.get("Date", "")).replace("Z", "+00:00")
                )
                if t.tzinfo is None:
                    t = t.replace(tzinfo=UTC)
                ts = t.date()
                if ts < start or ts > end:
                    continue
                o = Decimal(row["Open"])
                h = Decimal(row["High"])
                lo = Decimal(row["Low"])
                c = Decimal(row["Close"])
                v = Decimal(row.get("Volume", row.get("Volume BTC", "0")))
                yield OHLCVBar(t, o, h, lo, c, v, spec.symbol, self.name, timeframe)
            except (KeyError, ValueError, InvalidOperation):
                continue
        time.sleep(2.0)


# ----------------------------------------------------------------------
# Databento — institutional-grade historical for CME/CBOT/NYMEX.
# Free tier: 1 GB/month. ES/NQ/CL/GC via GLBX or CME symbology.
# Date range: 2010→today for daily, 2018→today for 1m+ on free tier.
# ----------------------------------------------------------------------
class DatabentoHistorical(HttpSource):
    name = SourceId.DATABENTO
    BASE_URL = "https://hist.databento.com/v0/klines"

    TF_DATABENTO: dict[str, str] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "1d": "1d",
    }

    SYMBOL_MAP: dict[str, str] = {
        "ES": "ES.FUT",
        "NQ": "NQ.FUT",
        "CL": "CL.FUT",
        "GC": "GC.FUT",
        "YM": "YM.FUT",
    }

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self.api_key = api_key
        self.rate_limit = RateLimit(
            requests_per_second=0.5,
            requests_per_minute=20,
            cooldown_on_429=60.0,
            user_agent="oracle-trading/1.0",
            notes="Free tier 1 GB/month",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        return AssetSpec(
            symbol=symbol.upper(),
            asset_class=AssetClass.FUTURES,
            exchange="cme",
            point_precision=2,
            volume_precision=0,
            earliest_available=date(2010, 1, 1),
            multiplier=Decimal("50") if symbol.upper() == "ES" else Decimal("1"),
            quote_currency="USD",
        )

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]:
        if not self.api_key:
            logger.warning(
                "%s: no API key configured (set DATABENTO_API_KEY); skipping",
                self.name,
            )
            return
        tf = self.TF_DATABENTO.get(timeframe)
        if tf is None:
            raise ValueError(f"Databento: unsupported timeframe {timeframe}")
        sym = self.SYMBOL_MAP.get(symbol.upper(), symbol.upper())
        self._cooldown_until_clear()
        url = (
            f"{self.BASE_URL}?dataset=glbx.mdp3&symbols={sym}&schema=ohlcv-{timeframe}"
            f"&start={start.isoformat()}&end={end.isoformat()}"
        )
        req = Request(
            url,
            headers={
                "User-Agent": self.rate_limit.user_agent,
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urlopen(req, timeout=120) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        spec = self.asset_spec(symbol)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row["ts_event"]).astimezone(UTC)
                o = Decimal(row["open"]) / Decimal("1000000000")
                h = Decimal(row["high"]) / Decimal("1000000000")
                lo = Decimal(row["low"]) / Decimal("1000000000")
                c = Decimal(row["close"]) / Decimal("1000000000")
                v = Decimal(row.get("volume", "0"))
                yield OHLCVBar(
                    ts,
                    o.quantize(Decimal("0.0001")),
                    h.quantize(Decimal("0.0001")),
                    lo.quantize(Decimal("0.0001")),
                    c.quantize(Decimal("0.0001")),
                    v,
                    spec.symbol,
                    self.name,
                    timeframe,
                )
            except (KeyError, ValueError, InvalidOperation):
                continue


# ----------------------------------------------------------------------
# HistData.com — free bulk CSV for FX majors (1m, 5m, 1h, 1d).
# Range: 2000→today for EURUSD; daily zip per year.
# URL pattern: https://www.histdata.com/download-free/{pair}/{tf}/{year}
# ----------------------------------------------------------------------
class HistData(HttpSource):
    name = SourceId.HISTDATA
    BASE_URL = "https://www.histdata.com/download-free/"

    FX_PAIRS: dict[str, str] = {
        "EURUSD": "eurusd",
        "GBPUSD": "gbpusd",
        "USDJPY": "usdjpy",
        "AUDUSD": "audusd",
        "USDCHF": "usdchf",
        "USDCAD": "usdcad",
    }

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=0.2,
            requests_per_minute=12,
            concurrent=1,
            user_agent="oracle-trading/1.0",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        return AssetSpec(
            symbol=symbol.upper(),
            asset_class=AssetClass.FX,
            exchange="ecb",
            point_precision=5 if "JPY" not in symbol.upper() else 3,
            volume_precision=0,
            earliest_available=date(2000, 1, 1),
            multiplier=Decimal("100000"),
            quote_currency=symbol.upper()[3:6],
        )

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]:
        pair = self.FX_PAIRS.get(symbol.upper())
        if pair is None:
            logger.warning("%s: %s not in free FX list", self.name, symbol)
            return
        spec = self.asset_spec(symbol)
        year = start.year
        while year <= end.year:
            self._cooldown_until_clear()
            url = (
                f"{self.BASE_URL}{pair}/{timeframe}/{year}/{pair}{timeframe}_{year}.zip"
            )
            req = Request(url, headers={"User-Agent": self.rate_limit.user_agent})
            try:
                with urlopen(req, timeout=60) as resp:
                    raw = resp.read()
            except Exception as exc:
                logger.warning("%s: skip %s — %s", self.name, year, exc)
                year += 1
                continue
            import zipfile

            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in zf.namelist():
                    if not name.endswith((".csv", ".txt")):
                        continue
                    with zf.open(name) as fh:
                        text = io.TextIOWrapper(fh, encoding="utf-8", errors="ignore").read()
                    for line in text.splitlines()[1:]:
                        parts = line.split(",")
                        if len(parts) < 5:
                            continue
                        try:
                            t = datetime.strptime(
                                f"{parts[0]} {parts[1]}", "%Y%m%d %H%M%S"
                            ).replace(tzinfo=UTC)
                            if t.date() < start or t.date() > end:
                                continue
                            o = Decimal(parts[2])
                            h = Decimal(parts[3])
                            lo = Decimal(parts[4])
                            c = Decimal(parts[5])
                            yield OHLCVBar(t, o, h, lo, c, Decimal("0"), spec.symbol, self.name, timeframe)
                        except (ValueError, InvalidOperation, IndexError):
                            continue
            time.sleep(5.0)
            year += 1


# ----------------------------------------------------------------------
# Stooq — free daily OHLCV for futures and ETFs (1990→today).
# URL pattern: https://stooq.com/q/d/lo/?s={sym}.us&i=d
# Range: depends on symbol; ES continuous back to 1990s.
# ----------------------------------------------------------------------
class Stooq(HttpSource):
    name = SourceId.STOOQ
    BASE_URL = "https://stooq.com/q/d/lo/"

    SYMBOL_MAP: dict[str, str] = {
        "ES": "es.f",
        "NQ": "nq.f",
        "YM": "ym.f",
        "CL": "cl.f",
        "GC": "gc.f",
        "ES_D": "es.d",
    }

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=0.3,
            requests_per_minute=15,
            user_agent="oracle-trading/1.0",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        return AssetSpec(
            symbol=symbol.upper(),
            asset_class=AssetClass.FUTURES,
            exchange="cme",
            point_precision=2,
            volume_precision=0,
            earliest_available=date(1990, 1, 1),
            multiplier=Decimal("50") if symbol.upper() == "ES" else Decimal("1"),
            quote_currency="USD",
        )

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> Iterator[OHLCVBar]:
        if timeframe != "1d":
            logger.warning("%s: daily only; tf=%s skipped", self.name, timeframe)
            return
        sym = self.SYMBOL_MAP.get(symbol.upper(), f"{symbol.lower()}.f")
        self._cooldown_until_clear()
        url = f"{self.BASE_URL}?s={sym}&i=d"
        req = Request(url, headers={"User-Agent": self.rate_limit.user_agent})
        with urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        spec = self.asset_spec(symbol)
        for row in reader:
            try:
                d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                if d < start or d > end:
                    continue
                o = Decimal(row["Open"])
                h = Decimal(row["High"])
                lo = Decimal(row["Low"])
                c = Decimal(row["Close"])
                v = Decimal(row.get("Volume", "0") or "0")
                yield OHLCVBar(
                    datetime(d.year, d.month, d.day, tzinfo=UTC),
                    o,
                    h,
                    lo,
                    c,
                    v,
                    spec.symbol,
                    self.name,
                    timeframe,
                )
            except (KeyError, ValueError, InvalidOperation):
                continue


# ----------------------------------------------------------------------
# Registry helper
# ----------------------------------------------------------------------
SOURCES: dict[SourceId, DataSource] = {
    SourceId.BINANCE_REST: BinanceREST(),
    SourceId.CRYPTODATA: CryptoDataDownload(),
    SourceId.DATABENTO: DatabentoHistorical(),
    SourceId.HISTDATA: HistData(),
    SourceId.STOOQ: Stooq(),
}


def get_source(source_id: SourceId) -> DataSource:
    return SOURCES[source_id]
