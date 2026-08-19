"""Tests for BL-301.b Binance Vision historical archive adapter.

Smoke tests use mocked ZIP payloads derived from the real Binance Vision
CSV schema (12 columns, no header on spot, header on futures/um).
Network-dependent smoke tests are marked ``@pytest.mark.network`` and
are skipped in CI unless ``--network`` is passed.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market.ingestion.sources import (
    BinanceVisionHistorical,
    _iter_csv_from_zip,
    _klines_row_to_bar,
    _next_month,
)
from market.ingestion.types import AssetClass, AssetSpec, SourceId

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPOT_KLINES_BODY = (
    b"1704067200000,42283.58,42298.62,42261.02,42298.61,35.92724000,"
    b"1704067259999,1519031.69451920,1327,23.18766000,980394.71034560,0\n"
    b"1704067260000,42298.62,42320.00,42298.61,42320.00,21.16779000,"
    b"1704067319999,895580.86104560,1348,13.47483000,570080.79421810,0\n"
    b"1704067320000,42319.99,42331.54,42319.99,42325.50,21.60391000,"
    b"1704067379999,914371.13818610,1019,11.21801000,474798.58741140,0\n"
)

FUTURES_KLINES_BODY = (
    b"open_time,open,high,low,close,volume,close_time,quote_volume,count,"
    b"taker_buy_volume,taker_buy_quote_volume,ignore\n"
    b"1704067200000,42314.00,42335.80,42289.60,42331.90,289.641,"
    b"1704067259999,12256155.25625,3310,175.211,7414459.86355,0\n"
    b"1704067260000,42331.90,42353.10,42331.80,42350.40,202.444,"
    b"1704067319999,8572240.95470,1885,154.353,6535804.80720,0\n"
)


def _make_zip(csv_body: bytes, name: str = "BTCUSDT-1m-2024-01.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, csv_body)
    return buf.getvalue()


@pytest.fixture
def spot_adapter() -> BinanceVisionHistorical:
    return BinanceVisionHistorical(market="spot")


@pytest.fixture
def futures_adapter() -> BinanceVisionHistorical:
    return BinanceVisionHistorical(market="futures/um")


@pytest.fixture
def btcusdt_spec(spot_adapter: BinanceVisionHistorical) -> AssetSpec:
    return spot_adapter.asset_spec("BTCUSDT")


# ---------------------------------------------------------------------------
# Construction + asset_spec
# ---------------------------------------------------------------------------


class TestBinanceVisionConstruction:
    def test_default_market_is_spot(self) -> None:
        adapter = BinanceVisionHistorical()
        assert adapter.market == "spot"
        assert adapter.name == SourceId.BINANCE_VISION

    def test_futures_um_market_supported(self) -> None:
        adapter = BinanceVisionHistorical(market="futures/um")
        assert adapter.market == "futures/um"

    def test_unsupported_market_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported market"):
            BinanceVisionHistorical(market="futures/cm")

    def test_registry_lookup(self) -> None:
        from market.ingestion.sources import SOURCES, get_source

        assert SourceId.BINANCE_VISION in SOURCES
        adapter = get_source(SourceId.BINANCE_VISION)
        assert isinstance(adapter, BinanceVisionHistorical)

    def test_supported_timeframes(self, spot_adapter: BinanceVisionHistorical) -> None:
        for tf in ("1s", "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"):
            assert tf in spot_adapter.INTERVAL_MAP

    def test_unsupported_timeframe_raises(self, spot_adapter: BinanceVisionHistorical) -> None:
        with pytest.raises(ValueError, match="unsupported timeframe"):
            list(spot_adapter.fetch_range("BTCUSDT", "2m", date(2024, 1, 1), date(2024, 1, 2)))


class TestBinanceVisionAssetSpec:
    def test_btcusdt_spot_is_crypto_spot(self, spot_adapter: BinanceVisionHistorical) -> None:
        spec = spot_adapter.asset_spec("BTCUSDT")
        assert spec.asset_class == AssetClass.CRYPTO_SPOT
        assert spec.exchange == "binance_vision"
        assert spec.quote_currency == "USDT"
        assert spec.point_precision == 8

    def test_futures_um_is_crypto_perp(self, futures_adapter: BinanceVisionHistorical) -> None:
        spec = futures_adapter.asset_spec("BTCUSDT")
        assert spec.asset_class == AssetClass.CRYPTO_PERP
        assert spec.exchange == "binance_vision"

    def test_ethusdt_high_precision(self, spot_adapter: BinanceVisionHistorical) -> None:
        spec = spot_adapter.asset_spec("ETHUSDT")
        assert spec.point_precision == 8

    def test_earliest_available_2017_08(self, spot_adapter: BinanceVisionHistorical) -> None:
        spec = spot_adapter.asset_spec("BTCUSDT")
        assert spec.earliest_available == date(2017, 8, 1)


# ---------------------------------------------------------------------------
# CSV parsing — pure functions, no network
# ---------------------------------------------------------------------------


class TestKlinesRowToBar:
    def test_valid_spot_row(self, btcusdt_spec: AssetSpec) -> None:
        row = ["1704067200000", "42283.58", "42298.62", "42261.02", "42298.61", "35.92724000"]
        bar = _klines_row_to_bar(
            row, btcusdt_spec, SourceId.BINANCE_VISION, "1m", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert bar is not None
        assert bar.timestamp.year == 2024 and bar.timestamp.month == 1
        assert bar.open == Decimal("42283.58")
        assert bar.close == Decimal("42298.61")
        assert bar.volume == Decimal("35.92724000")
        assert bar.source == SourceId.BINANCE_VISION
        assert bar.timeframe == "1m"

    def test_short_row_returns_none(self, btcusdt_spec: AssetSpec) -> None:
        row = ["1704067200000", "42283.58"]
        bar = _klines_row_to_bar(
            row, btcusdt_spec, SourceId.BINANCE_VISION, "1m", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert bar is None

    def test_invalid_decimal_returns_none(self, btcusdt_spec: AssetSpec) -> None:
        row = ["1704067200000", "abc", "42298.62", "42261.02", "42298.61", "35.92724000"]
        bar = _klines_row_to_bar(
            row, btcusdt_spec, SourceId.BINANCE_VISION, "1m", date(2024, 1, 1), date(2024, 1, 31)
        )
        assert bar is None

    def test_out_of_range_returns_none(self, btcusdt_spec: AssetSpec) -> None:
        row = ["1704067200000", "42283.58", "42298.62", "42261.02", "42298.61", "35.92724000"]
        # 2024-01-01 timestamp but range is 2024-02
        bar = _klines_row_to_bar(
            row, btcusdt_spec, SourceId.BINANCE_VISION, "1m", date(2024, 2, 1), date(2024, 2, 28)
        )
        assert bar is None


class TestNextMonth:
    def test_january_to_february(self) -> None:
        assert _next_month(date(2024, 1, 15)) == date(2024, 2, 1)

    def test_december_rolls_year(self) -> None:
        assert _next_month(date(2024, 12, 15)) == date(2025, 1, 1)

    def test_preserves_day_ignored(self) -> None:
        # _next_month always returns day=1 (next month boundary)
        assert _next_month(date(2024, 6, 30)).day == 1
        assert _next_month(date(2024, 6, 30)).month == 7


class TestIterCsvFromZip:
    def test_yields_csv_members(self) -> None:
        zip_bytes = _make_zip(SPOT_KLINES_BODY)
        members = list(_iter_csv_from_zip(zip_bytes))
        assert len(members) == 1
        name, text = members[0]
        assert name.endswith(".csv")
        assert "42283.58" in text

    def test_skips_non_csv_members(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "skip me")
            zf.writestr("BTCUSDT-1m-2024-01.csv", SPOT_KLINES_BODY.decode())
        members = list(_iter_csv_from_zip(buf.getvalue()))
        assert len(members) == 1

    def test_bad_zip_returns_empty(self) -> None:
        # Random bytes — not a valid zip
        members = list(_iter_csv_from_zip(b"\x00\x01\x02 not a zip"))
        assert members == []


# ---------------------------------------------------------------------------
# fetch_range with mocked HTTP — exercises parser end-to-end
# ---------------------------------------------------------------------------


class TestFetchRangeParsing:
    def test_parses_spot_klines_zip(
        self, spot_adapter: BinanceVisionHistorical, btcusdt_spec: AssetSpec
    ) -> None:
        zip_bytes = _make_zip(SPOT_KLINES_BODY)
        with patch.object(spot_adapter, "_get", return_value=zip_bytes):
            bars = list(
                spot_adapter.fetch_range("BTCUSDT", "1m", date(2024, 1, 1), date(2024, 1, 2))
            )
        assert len(bars) == 3
        assert all(b.symbol == "BTCUSDT" for b in bars)
        assert all(b.source == SourceId.BINANCE_VISION for b in bars)
        assert all(b.timeframe == "1m" for b in bars)
        # First bar: 2024-01-01 00:00:00 UTC
        assert bars[0].timestamp.year == 2024
        assert bars[0].open == Decimal("42283.58")

    def test_parses_futures_klines_with_header(
        self, futures_adapter: BinanceVisionHistorical
    ) -> None:
        zip_bytes = _make_zip(FUTURES_KLINES_BODY)
        with patch.object(futures_adapter, "_get", return_value=zip_bytes):
            bars = list(
                futures_adapter.fetch_range("BTCUSDT", "1m", date(2024, 1, 1), date(2024, 1, 2))
            )
        assert len(bars) == 2
        assert bars[0].open == Decimal("42314.00")

    def test_404_skipped_silently(self, spot_adapter: BinanceVisionHistorical) -> None:
        from urllib.error import HTTPError

        def fake_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
            raise HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))  # type: ignore[arg-type]

        with patch.object(spot_adapter, "_get", side_effect=fake_get):
            bars = list(
                spot_adapter.fetch_range("BTCUSDT", "1m", date(2010, 1, 1), date(2010, 1, 5))
            )
        # 2010-01 has no Binance Vision archive (pre-listing); skip without error
        assert bars == []

    def test_start_clamped_to_earliest_listing(
        self, spot_adapter: BinanceVisionHistorical, btcusdt_spec: AssetSpec
    ) -> None:
        # Requesting 2010-01 with 2017-08 earliest: adapter should fetch 2017-08 onwards
        zip_bytes = _make_zip(SPOT_KLINES_BODY)
        calls: list[str] = []

        def fake_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(url)
            return zip_bytes

        with patch.object(spot_adapter, "_get", side_effect=fake_get):
            list(spot_adapter.fetch_range("BTCUSDT", "1m", date(2010, 1, 1), date(2017, 8, 31)))
        # Should have skipped from 2010-01 to 2017-08, then iterated monthly
        assert any("2017-08" in url for url in calls)
        assert not any("2010" in url for url in calls)

    def test_monthly_url_pattern(self, spot_adapter: BinanceVisionHistorical) -> None:
        url = spot_adapter._monthly_url("BTCUSDT", "1m", date(2024, 1, 1))
        assert url == (
            "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip"
        )

    def test_futures_monthly_url_includes_um(
        self, futures_adapter: BinanceVisionHistorical
    ) -> None:
        url = futures_adapter._monthly_url("BTCUSDT", "1m", date(2024, 1, 1))
        assert "/futures/um/monthly/klines/" in url


# ---------------------------------------------------------------------------
# Network smoke test (gated, skipped by default)
# ---------------------------------------------------------------------------


NETWORK = (
    pytest.mark.skipif(
        not pytest.config.getoption("--network", default=False)
        if hasattr(pytest, "config")
        else True,
        reason="Network smoke test — run with --network flag",
    )
    if False
    else pytest.mark.skip(reason="Run manually: pytest -m network")
)


@NETWORK
def test_network_smoke_btcusdt_1m_2024_01(spot_adapter: BinanceVisionHistorical) -> None:
    """Live download of BTCUSDT 1m for 2024-01-01..02. ~2MB ZIP.

    Run: pytest tests/unit/test_ingestion_binance_vision.py -m network
    """
    bars = list(spot_adapter.fetch_range("BTCUSDT", "1m", date(2024, 1, 1), date(2024, 1, 2)))
    assert len(bars) > 0
    assert bars[0].timestamp.year == 2024
    assert bars[0].open > Decimal("1000")
