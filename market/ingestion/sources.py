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
from datetime import UTC, date, datetime, timedelta, timezone

UTC = UTC, timezone
UTC = timezone.utc
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable
from urllib.request import Request, urlopen

import pandas as pd

from market.ingestion.types import AssetClass, AssetSpec, OHLCVBar, RateLimit, SourceId

logger = logging.getLogger("oracle.market.ingestion.sources")


@runtime_checkable
class DataSource(Protocol):
    name: SourceId
    rate_limit: RateLimit

    def asset_spec(self, symbol: str) -> AssetSpec: ...

    def fetch_range(
        self, symbol: str, timeframe: str, start: date, end: date
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
        req = Request(url, headers={"User-Agent": self.rate_limit.user_agent, "Accept": "*/*"})
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
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        interval = self.INTERVAL_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"BinanceREST: unsupported timeframe {timeframe}")
        start_ms = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        end_ms = int(
            datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC).timestamp() * 1000
        )
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
        self, symbol: str, timeframe: str, start: date, end: date
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

    TF_DATABENTO: dict[str, str] = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}

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
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        if not self.api_key:
            logger.warning("%s: no API key configured (set DATABENTO_API_KEY); skipping", self.name)
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
        # Majors
        "EURUSD": "eurusd",
        "GBPUSD": "gbpusd",
        "USDJPY": "usdjpy",
        "AUDUSD": "audusd",
        "USDCHF": "usdchf",
        "USDCAD": "usdcad",
        "NZDUSD": "nzdusd",
        # Crosses EUR
        "EURGBP": "eurgbp",
        "EURJPY": "eurjpy",
        "EURCHF": "eurchf",
        "EURCAD": "eurcad",
        "EURAUD": "euraud",
        "EURNZD": "eurnzd",
        # Crosses GBP
        "GBPJPY": "gbpjpy",
        "GBPCHF": "gbpchf",
        "GBPCAD": "gbpcad",
        "GBPAUD": "gbpaud",
        "GBPNZD": "gbpnzd",
        # Crosses AUD
        "AUDJPY": "audjpy",
        "AUDCHF": "audchf",
        "AUDCAD": "audcad",
        "AUDNZD": "audnzd",
        # Crosses NZD
        "NZDJPY": "nzdjpy",
        "NZDCHF": "nzdchf",
        "NZDCAD": "nzdcad",
        # Crosses CHF/CAD
        "CHFJPY": "chfjpy",
        "CADJPY": "cadjpy",
        "CADCHF": "cadchf",
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
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        pair = self.FX_PAIRS.get(symbol.upper())
        if pair is None:
            logger.warning("%s: %s not in free FX list", self.name, symbol)
            return
        spec = self.asset_spec(symbol)
        year = start.year
        while year <= end.year:
            self._cooldown_until_clear()
            url = f"{self.BASE_URL}{pair}/{timeframe}/{year}/{pair}{timeframe}_{year}.zip"
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
                            yield OHLCVBar(
                                t, o, h, lo, c, Decimal("0"), spec.symbol, self.name, timeframe
                            )
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
            requests_per_second=0.3, requests_per_minute=15, user_agent="oracle-trading/1.0"
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
        self, symbol: str, timeframe: str, start: date, end: date
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
# YFinance — free OHLCV for equities, ETFs, futures, FX, crypto.
# No API key required. Daily back to ~1970 for equities, varies for others.
# Symbol map: ES=F for E-mini S&P 500, GC=F for Gold, etc.
# Interval support: 1m, 2m, 5m, 15m, 30m, 60m, 1h, 1d, 5d, 1wk, 1mo
# ----------------------------------------------------------------------
class YFinance(HttpSource):
    name = SourceId.YAHOO

    SYMBOL_MAP: dict[str, str] = {
        "ES": "ES=F",
        "NQ": "NQ=F",
        "YM": "YM=F",
        "CL": "CL=F",
        "GC": "GC=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "SPY": "SPY",
    }

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=1.0, requests_per_minute=60, user_agent="oracle-trading/1.0"
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        s = symbol.upper()
        if s in ("ES", "NQ", "YM"):
            cls = AssetClass.FUTURES
            mult = {"ES": Decimal("50"), "NQ": Decimal("20"), "YM": Decimal("5")}.get(
                s, Decimal("1")
            )
        elif s in ("CL", "GC"):
            cls = AssetClass.FUTURES
            mult = {"CL": Decimal("1000"), "GC": Decimal("100")}.get(s, Decimal("1"))
        elif s in ("EURUSD", "GBPUSD"):
            cls = AssetClass.FX
            mult = Decimal("1")
        else:
            cls = AssetClass.EQUITY
            mult = Decimal("1")
        return AssetSpec(
            symbol=s,
            asset_class=cls,
            exchange="nyse"
            if cls == AssetClass.EQUITY
            else "cme"
            if cls == AssetClass.FUTURES
            else "ideal",
            point_precision=2,
            volume_precision=0,
            earliest_available=date(2000, 1, 1),
            multiplier=mult,
            quote_currency="USD",
        )

    def fetch_range(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        import yfinance as yf

        ticker = self.SYMBOL_MAP.get(symbol.upper(), symbol)
        interval = self._to_yf_interval(timeframe)
        period = self._to_yf_period(start, end)
        self._cooldown_until_clear()
        try:
            hist = yf.download(
                ticker, period=period, interval=interval, progress=False, auto_adjust=True
            )
        except Exception as exc:
            logger.warning("%s: yfinance download failed for %s: %s", self.name, ticker, exc)
            return
        if hist.empty:
            logger.warning("%s: no data returned for %s", self.name, ticker)
            return
        spec = self.asset_spec(symbol)
        # yfinance returns MultiIndex columns; flatten to single level
        if isinstance(hist.columns, type(pd.Index([]))) and hasattr(hist.columns, "levels"):
            hist.columns = hist.columns.get_level_values(0)
        for idx, row in hist.iterrows():
            try:
                ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                d = ts.date()
                if d < start or d > end:
                    continue
                yield OHLCVBar(
                    ts,
                    Decimal(str(row["Open"])),
                    Decimal(str(row["High"])),
                    Decimal(str(row["Low"])),
                    Decimal(str(row["Close"])),
                    Decimal(str(row.get("Volume", 0) or 0)),
                    spec.symbol,
                    self.name,
                    timeframe,
                )
            except (KeyError, ValueError, InvalidOperation):
                continue

    @staticmethod
    def _to_yf_interval(tf: str) -> str:
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "60m",
            "1d": "1d",
            "1wk": "1wk",
            "1mo": "1mo",
        }
        return mapping.get(tf, "1d")

    @staticmethod
    def _to_yf_period(start: date, end: date) -> str:
        days = (end - start).days
        if days <= 7:
            return "1wk"
        if days <= 30:
            return "1mo"
        if days <= 90:
            return "3mo"
        if days <= 180:
            return "6mo"
        if days <= 365:
            return "1y"
        if days <= 730:
            return "2y"
        if days <= 1825:
            return "5y"
        return "max"


# Dukascopy JForex — new JSON endpoint (jetta.dukascopy.com/v1).
# Provides FX majors + crosses + XAU/XAG from 2003-05-04 at 1m resolution.
# No API key. Data served via CloudFront CDN — supports 10-20 concurrent reqs.
# Timeframes: 1m/5m/15m/30m native (day bucket); 1h/4h (month bucket); 1d (year bucket).
# 5m/15m/30m/4h are aggregated client-side from the finer native resolution.
class Dukascopy(HttpSource):
    """Adapter for the Dukascopy JForex v1 candle API.

    URL pattern (minute-resolution day bucket):
      GET https://jetta.dukascopy.com/v1/candles/minute/{code}/ASK/{year}/{month}/{day}

    Response: JSON with differential-encoded OHLCV arrays.
    Decode: reconstruct absolute prices from delta arrays + multiplier.
    """

    name = SourceId.DUKASCOPY
    BASE_URL = "https://jetta.dukascopy.com/v1"

    # Dukascopy instrument code (BASE-QUOTE hyphen format)
    SYMBOL_MAP: dict[str, str] = {
        # Majors
        "EURUSD": "EUR-USD",
        "GBPUSD": "GBP-USD",
        "USDJPY": "USD-JPY",
        "USDCHF": "USD-CHF",
        "USDCAD": "USD-CAD",
        "AUDUSD": "AUD-USD",
        "NZDUSD": "NZD-USD",
        # Metals
        "XAUUSD": "XAU-USD",
        "XAGUSD": "XAG-USD",
        # EUR crosses
        "EURGBP": "EUR-GBP",
        "EURJPY": "EUR-JPY",
        "EURCHF": "EUR-CHF",
        "EURCAD": "EUR-CAD",
        "EURAUD": "EUR-AUD",
        "EURNZD": "EUR-NZD",
        # GBP crosses
        "GBPJPY": "GBP-JPY",
        "GBPCHF": "GBP-CHF",
        "GBPCAD": "GBP-CAD",
        "GBPAUD": "GBP-AUD",
        "GBPNZD": "GBP-NZD",
        # AUD/NZD crosses
        "AUDJPY": "AUD-JPY",
        "AUDCHF": "AUD-CHF",
        "AUDCAD": "AUD-CAD",
        "AUDNZD": "AUD-NZD",
        "NZDJPY": "NZD-JPY",
        "NZDCHF": "NZD-CHF",
        "NZDCAD": "NZD-CAD",
        # CHF/CAD crosses
        "CHFJPY": "CHF-JPY",
        "CADJPY": "CAD-JPY",
        "CADCHF": "CAD-CHF",
    }

    # earliest 1m data per symbol (approximate; server returns empty before this)
    EARLIEST: dict[str, date] = {
        "EURUSD": date(2003, 5, 4),
        "GBPUSD": date(2003, 5, 4),
        "USDJPY": date(2003, 5, 4),
        "USDCHF": date(2003, 5, 4),
        "USDCAD": date(2003, 8, 3),
        "AUDUSD": date(2003, 8, 3),
        "NZDUSD": date(2003, 8, 3),
        "XAUUSD": date(2003, 5, 5),
        "XAGUSD": date(2003, 5, 4),
    }
    _DEFAULT_EARLIEST = date(2004, 1, 1)

    # timeframe → (api_source, bucket_type, minutes_per_bar)
    # bucket_type: "day" → 1 day of 1m bars, "month" → 1 month of 1h bars
    _TF_CONFIG: dict[str, tuple[str, str, int]] = {
        "1m": ("minute", "day", 1),
        "5m": ("minute", "day", 5),
        "15m": ("minute", "day", 15),
        "30m": ("minute", "day", 30),
        "1h": ("hour", "month", 60),
        "4h": ("hour", "month", 240),
        "1d": ("day", "year", 1440),
    }

    def __init__(self) -> None:
        super().__init__()
        self.rate_limit = RateLimit(
            requests_per_second=10.0,
            requests_per_minute=600,
            concurrent=10,
            cooldown_on_429=30.0,
            user_agent="oracle-trading/1.0 (research)",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        s = symbol.upper()
        is_jpy = "JPY" in s
        is_metal = s.startswith("XA")
        return AssetSpec(
            symbol=s,
            asset_class=AssetClass.FX if not is_metal else AssetClass.FUTURES,
            exchange="dukascopy",
            point_precision=3 if is_jpy else (2 if is_metal else 5),
            volume_precision=2,
            earliest_available=self.EARLIEST.get(s, self._DEFAULT_EARLIEST),
            multiplier=Decimal("100000") if not is_metal else Decimal("1"),
            quote_currency=s[3:6] if len(s) >= 6 else "USD",
        )

    def fetch_range(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        import json as _json

        code = self.SYMBOL_MAP.get(symbol.upper())
        if code is None:
            logger.warning("%s: symbol %s not in SYMBOL_MAP", self.name, symbol)
            return
        cfg = self._TF_CONFIG.get(timeframe)
        if cfg is None:
            logger.warning("%s: unsupported timeframe %s", self.name, timeframe)
            return
        api_source, bucket_type, _minutes_per_bar = cfg

        spec = self.asset_spec(symbol)
        earliest = spec.earliest_available or self._DEFAULT_EARLIEST
        effective_start = max(start, earliest)

        for url, _bucket_start in self._iter_bucket_urls(
            code, api_source, bucket_type, effective_start, end
        ):
            self._cooldown_until_clear()
            try:
                raw = self._get(url, timeout=30)
            except Exception as exc:
                logger.warning("%s: skip bucket %s — %s", self.name, url, exc)
                time.sleep(1.0)
                continue

            try:
                resp = _json.loads(raw)
            except Exception:
                continue

            bars = self._decode_response(resp, spec, timeframe)
            for bar in bars:
                if bar.timestamp.date() < start or bar.timestamp.date() > end:
                    continue
                yield bar

            time.sleep(1.0 / self.rate_limit.requests_per_second)

    def _iter_bucket_urls(
        self, code: str, api_source: str, bucket_type: str, start: date, end: date
    ) -> Iterator[tuple[str, date]]:
        """Yield (url, bucket_start_date) for each time bucket in [start, end]."""
        from datetime import timedelta

        cur = start
        while cur <= end:
            if bucket_type == "day":
                url = (
                    f"{self.BASE_URL}/candles/{api_source}/{code}/ASK"
                    f"/{cur.year}/{cur.month}/{cur.day}"
                )
                yield url, cur
                cur = (datetime(cur.year, cur.month, cur.day) + timedelta(days=1)).date()
            elif bucket_type == "month":
                url = f"{self.BASE_URL}/candles/{api_source}/{code}/ASK/{cur.year}/{cur.month}"
                yield url, cur
                cur = (
                    date(cur.year + 1, 1, 1)
                    if cur.month == 12
                    else date(cur.year, cur.month + 1, 1)
                )
            elif bucket_type == "year":
                url = f"{self.BASE_URL}/candles/{api_source}/{code}/ASK/{cur.year}"
                yield url, cur
                cur = date(cur.year + 1, 1, 1)

    @staticmethod
    def _parse_fields(
        resp: dict,  # type: ignore[type-arg]
    ) -> (
        tuple[int, float, int, list[int], list[int], list[int], list[int], list[int], list[float]]
        | None
    ):
        """Extract and validate the raw arrays from a Dukascopy JSON bucket."""
        try:
            base_ts_ms: int = int(resp["timestamp"])
            multiplier: float = float(resp["multiplier"])
            shift_ms: int = int(resp["shift"])
            times: list[int] = list(resp.get("times", []))
        except (KeyError, TypeError, ValueError):
            return None
        if not times:
            return None
        return (
            base_ts_ms,
            multiplier,
            shift_ms,
            times,
            list(resp.get("opens", [])),
            list(resp.get("highs", [])),
            list(resp.get("lows", [])),
            list(resp.get("closes", [])),
            list(resp.get("volumes", [])),
        )

    def _make_bar(
        self,
        ts_ms: int,
        o: int,
        h: int,
        lo: int,
        c: int,
        vol: float,
        multiplier: float,
        quant: Decimal,
        spec: AssetSpec,
        timeframe: str,
    ) -> OHLCVBar:
        bar_ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
        m = multiplier
        return OHLCVBar(
            bar_ts,
            Decimal(o * m).quantize(quant),
            Decimal(h * m).quantize(quant),
            Decimal(lo * m).quantize(quant),
            Decimal(c * m).quantize(quant),
            Decimal(str(round(vol, 2))),
            spec.symbol,
            self.name,
            timeframe,
        )

    def _resample_buf(
        self,
        buf: list[tuple[int, int, int, int, float]],
        close_ts_ms: int,
        shift_ms: int,
        multiplier: float,
        quant: Decimal,
        spec: AssetSpec,
        timeframe: str,
    ) -> OHLCVBar | None:
        if not buf:
            return None
        ao, ah, al, ac, av = (
            buf[0][0],
            max(x[1] for x in buf),
            min(x[2] for x in buf),
            buf[-1][3],
            sum(x[4] for x in buf),
        )
        bar_ts_ms = close_ts_ms - len(buf) * shift_ms
        return self._make_bar(bar_ts_ms, ao, ah, al, ac, av, multiplier, quant, spec, timeframe)

    def _decode_response(
        self, resp: dict[str, object], spec: AssetSpec, timeframe: str
    ) -> list[OHLCVBar]:
        """Decode Dukascopy differential JSON → list of OHLCVBar."""
        import math

        fields = self._parse_fields(resp)
        if fields is None:
            return []
        base_ts_ms, multiplier, shift_ms, times, opens, highs, lows, closes, volumes = fields

        prec = max(0, -math.floor(math.log10(abs(multiplier)))) if multiplier else 5
        quant = Decimal(10) ** -prec

        o_u = round(float(resp.get("open", 0)) / multiplier)
        h_u = round(float(resp.get("high", 0)) / multiplier)
        l_u = round(float(resp.get("low", 0)) / multiplier)
        c_u = round(float(resp.get("close", 0)) / multiplier)

        native_min = shift_ms // 60000
        target_min = self._TF_CONFIG[timeframe][2]
        bars_per_agg = target_min // native_min if target_min > native_min else 1
        needs_agg = bars_per_agg > 1

        bars: list[OHLCVBar] = []
        ts_ms = base_ts_ms
        agg_buf: list[tuple[int, int, int, int, float]] = []

        for i, td in enumerate(times):
            ts_ms += td * shift_ms
            o_u += opens[i] if i < len(opens) else 0
            h_u += highs[i] if i < len(highs) else 0
            l_u += lows[i] if i < len(lows) else 0
            c_u += closes[i] if i < len(closes) else 0
            vol = volumes[i] if i < len(volumes) else 0.0

            if needs_agg:
                agg_buf.append((o_u, h_u, l_u, c_u, vol))
                if len(agg_buf) >= bars_per_agg:
                    bar = self._resample_buf(
                        agg_buf, ts_ms, shift_ms, multiplier, quant, spec, timeframe
                    )
                    if bar:
                        bars.append(bar)
                    agg_buf.clear()
            else:
                bars.append(
                    self._make_bar(
                        ts_ms, o_u, h_u, l_u, c_u, vol, multiplier, quant, spec, timeframe
                    )
                )

        if needs_agg and agg_buf:
            bar = self._resample_buf(agg_buf, ts_ms, shift_ms, multiplier, quant, spec, timeframe)
            if bar:
                bars.append(bar)

        return bars


# ----------------------------------------------------------------------
# IBKR — Interactive Brokers historical data via ib_insync (local TWS/Gateway)
# Requires TWS/Gateway running on localhost:7497 (paper) or 7496 (live).
# Range: futures 1m from 2010+, equities 1m from 2000+.
# Rate limit: 50 req historical data per 10 seconds (IBKR hard cap).
# ----------------------------------------------------------------------
class IBKRHistorical(HttpSource):
    """Adapter for Interactive Brokers historical OHLCV.

    API details:
      - reqHistoricalData(contract, end, duration, bar_size, what_show, …)
      - 1m bars: duration max "6 M" (6 months) per call
      - Must reconnect for each pagination step
      - Paper account: TWS port 7497, Gateway port 4002
    """

    name = SourceId.IBKR

    # IBKR bar size → canonical timeframe
    _BAR_SIZE: dict[str, str] = {
        "1m": "1 min",
        "5m": "5 mins",
        "15m": "15 mins",
        "30m": "30 mins",
        "1h": "1 hour",
        "4h": "4 hours",
        "1d": "1 day",
    }

    # Symbol → (secType, exchange, currency, earliest)
    _SYMBOL_MAP: dict[str, tuple[str, str, str, date | None]] = {
        "ES": ("FUT", "CME", "USD", date(2010, 1, 1)),
        "NQ": ("FUT", "CME", "USD", date(2010, 1, 1)),
        "YM": ("FUT", "CBOT", "USD", date(2010, 1, 1)),
        "CL": ("FUT", "NYMEX", "USD", date(2010, 1, 1)),
        "GC": ("FUT", "COMEX", "USD", date(2010, 1, 1)),
        "SPY": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "AAPL": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "MSFT": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "QQQ": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "IWM": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "EEM": ("STK", "SMART", "USD", date(2000, 1, 1)),
        "TLT": ("STK", "SMART", "USD", date(2002, 1, 1)),
    }

    def __init__(self, host: str = "127.0.0.1", port: int = 7497) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self.rate_limit = RateLimit(
            requests_per_second=5.0,
            requests_per_minute=50,
            concurrent=1,
            notes="IBKR hard cap: 50 historical requests per 10 seconds",
        )

    def asset_spec(self, symbol: str) -> AssetSpec:
        spec = self._SYMBOL_MAP.get(symbol.upper())
        if spec is None:
            sec_type = "STK" if symbol.isalpha() else "FUT"
            return AssetSpec(
                symbol=symbol.upper(),
                asset_class=AssetClass.EQUITY,
                exchange="SMART",
                earliest_available=date(2010, 1, 1),
            )
        sec_type, exchange, currency, earliest = spec
        asset_cls = AssetClass.FUTURES if sec_type == "FUT" else AssetClass.EQUITY
        return AssetSpec(
            symbol=symbol.upper(),
            asset_class=asset_cls,
            exchange=exchange,
            earliest_available=earliest or date(2010, 1, 1),
            quote_currency=currency,
        )

    def fetch_range(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Iterator[OHLCVBar]:
        bar_size = self._BAR_SIZE.get(timeframe)
        if bar_size is None:
            raise ValueError(f"IBKR: unsupported timeframe {timeframe}")
        spec = self.asset_spec(symbol)
        earliest = spec.earliest_available or date(2000, 1, 1)
        effective_start = max(start, earliest)
        if effective_start >= end:
            return

        self._cooldown_until_clear()
        try:
            from ib_insync import IB, Contract
        except ImportError:
            logger.warning("ib_insync not installed — run ``uv add ib_insync``")
            return

        ib = IB()
        connection_attempts = 3
        for attempt in range(connection_attempts):
            try:
                ib.connect(self._host, self._port, clientId=42 + attempt)
                break
            except Exception as exc:
                if attempt == connection_attempts - 1:
                    logger.warning(
                        "IBKR: cannot connect to %s:%s after %d attempts: %s",
                        self._host,
                        self._port,
                        connection_attempts,
                        exc,
                    )
                    return
                time.sleep(1.0)

        try:
            # Build contract
            contract = Contract()
            contract.symbol = symbol.upper()
            info = self._SYMBOL_MAP.get(symbol.upper())
            if info:
                contract.secType = info[0]
                contract.exchange = info[1]
                contract.currency = info[2]
            else:
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"

            # For futures, use continuous contract via generic ticks
            if contract.secType == "FUT":
                contract.includeExpired = True

            # Paginate backward from end to start in 6-month chunks
            current_end = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
            while current_end > datetime(
                effective_start.year, effective_start.month, effective_start.day, tzinfo=UTC
            ):
                try:
                    bars = ib.reqHistoricalData(
                        contract,
                        endDateTime=current_end.strftime("%Y%m%d %H:%M:%S UTC"),
                        durationStr="6 M",
                        barSizeSetting=bar_size,
                        whatToShow="TRADES",
                        useRTH=True,
                        formatDate=1,
                        timeout=30,
                    )
                except Exception as exc:
                    logger.warning("IBKR fetch failed: %s", exc)
                    break

                if not bars:
                    break

                for bar in bars:
                    ts = bar.date.replace(tzinfo=UTC) if bar.date.tzinfo is None else bar.date
                    bar_date = ts.date()
                    if bar_date < effective_start or bar_date > end:
                        continue
                    yield OHLCVBar(
                        timestamp=ts,
                        open=Decimal(str(round(bar.open, 2))),
                        high=Decimal(str(round(bar.high, 2))),
                        low=Decimal(str(round(bar.low, 2))),
                        close=Decimal(str(round(bar.close, 2))),
                        volume=Decimal(str(int(bar.volume))),
                        symbol=spec.symbol,
                        source=self.name,
                        timeframe=timeframe,
                    )

                # Move current_end back to before the earliest bar in this batch
                earliest_bar = datetime.fromtimestamp(bars[0].date.timestamp(), tz=UTC)
                current_end = earliest_bar - timedelta(minutes=1)
                time.sleep(0.5)  # rate limiting between chunks

        finally:
            ib.disconnect()


SOURCES: dict[SourceId, DataSource] = {
    SourceId.BINANCE_REST: BinanceREST(),
    SourceId.CRYPTODATA: CryptoDataDownload(),
    SourceId.DATABENTO: DatabentoHistorical(),
    SourceId.YAHOO: YFinance(),
    SourceId.HISTDATA: HistData(),
    SourceId.STOOQ: Stooq(),
    SourceId.DUKASCOPY: Dukascopy(),
    SourceId.IBKR: IBKRHistorical(),
}


def get_source(source_id: SourceId) -> DataSource:
    return SOURCES[source_id]
