"""Tests for BL-301.b Dukascopy adapter and HistData expansion."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

from market.ingestion.sources import Dukascopy, HistData, _clamp_bucket_range
from market.ingestion.types import AssetClass, SourceId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resp(
    ts_ms: int = 1704067200000,  # 2024-01-01 00:00:00 UTC
    multiplier: float = 1e-5,
    shift_ms: int = 60000,  # 1 minute
    n_bars: int = 3,
) -> dict[str, Any]:
    """Build a minimal valid Dukascopy JSON response with n_bars bars."""
    # first bar absolute, subsequent are delta-0 (flat)
    open_price = 1.10000
    return {
        "timestamp": ts_ms,
        "multiplier": multiplier,
        "shift": shift_ms,
        "open": open_price,
        "high": open_price + 0.0001,
        "low": open_price - 0.0001,
        "close": open_price + 0.00005,
        "times": [1] * n_bars,
        "opens": [0] * n_bars,
        "highs": [0] * n_bars,
        "lows": [0] * n_bars,
        "closes": [0] * n_bars,
        "volumes": [1000.0] * n_bars,
    }


# ---------------------------------------------------------------------------
# Dukascopy.asset_spec
# ---------------------------------------------------------------------------


class TestDukascopyAssetSpec:
    def setup_method(self) -> None:
        self.src = Dukascopy()

    def test_eurusd_spec(self) -> None:
        spec = self.src.asset_spec("EURUSD")
        assert spec.symbol == "EURUSD"
        assert spec.asset_class == AssetClass.FX
        assert spec.point_precision == 5
        assert spec.earliest_available == date(2003, 5, 4)

    def test_usdjpy_precision(self) -> None:
        spec = self.src.asset_spec("USDJPY")
        assert spec.point_precision == 3

    def test_xauusd_is_not_fx(self) -> None:
        spec = self.src.asset_spec("XAUUSD")
        assert spec.asset_class != AssetClass.FX
        assert spec.point_precision == 2

    def test_unknown_symbol_gets_default_earliest(self) -> None:
        spec = self.src.asset_spec("EXOTIC123")
        assert spec.earliest_available == Dukascopy._DEFAULT_EARLIEST


# ---------------------------------------------------------------------------
# Dukascopy._parse_fields
# ---------------------------------------------------------------------------


class TestDukascopyParseFields:
    def test_valid_response(self) -> None:
        resp = _make_resp(n_bars=2)
        result = Dukascopy._parse_fields(resp)
        assert result is not None
        base_ts, mult, shift, times, _opens, _highs, _lows, _closes, _volumes = result
        assert base_ts == resp["timestamp"]
        assert mult == resp["multiplier"]
        assert shift == resp["shift"]
        assert times == [1, 1]

    def test_empty_times_returns_none(self) -> None:
        resp = _make_resp(n_bars=0)
        resp["times"] = []
        assert Dukascopy._parse_fields(resp) is None

    def test_missing_required_key_returns_none(self) -> None:
        resp: dict[str, Any] = {"multiplier": 1e-5, "shift": 60000}
        assert Dukascopy._parse_fields(resp) is None

    def test_non_dict_returns_none(self) -> None:
        assert Dukascopy._parse_fields("bad") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Dukascopy._decode_response  (1m, no resampling)
# ---------------------------------------------------------------------------


class TestDukascopyDecodeResponse:
    def setup_method(self) -> None:
        self.src = Dukascopy()
        self.spec = self.src.asset_spec("EURUSD")

    def test_returns_correct_bar_count(self) -> None:
        resp = _make_resp(n_bars=5)
        bars = self.src._decode_response(resp, self.spec, "1m")
        assert len(bars) == 5

    def test_timestamps_are_utc_monotonic(self) -> None:
        resp = _make_resp(n_bars=3)
        bars = self.src._decode_response(resp, self.spec, "1m")
        ts = [b.timestamp for b in bars]
        assert all(t.tzinfo is not None for t in ts)
        assert ts == sorted(ts)

    def test_prices_are_decimal(self) -> None:
        bars = self.src._decode_response(_make_resp(n_bars=1), self.spec, "1m")
        b = bars[0]
        assert isinstance(b.open, Decimal)
        assert isinstance(b.close, Decimal)

    def test_symbol_and_source_set(self) -> None:
        bars = self.src._decode_response(_make_resp(n_bars=1), self.spec, "1m")
        b = bars[0]
        assert b.symbol == "EURUSD"
        assert b.source == SourceId.DUKASCOPY
        assert b.timeframe == "1m"

    def test_empty_response_returns_empty(self) -> None:
        resp = _make_resp(n_bars=0)
        resp["times"] = []
        bars = self.src._decode_response(resp, self.spec, "1m")
        assert bars == []

    def test_malformed_response_returns_empty(self) -> None:
        bars = self.src._decode_response({}, self.spec, "1m")
        assert bars == []

    def test_5m_resamples_to_fewer_bars(self) -> None:
        # 10 1m native bars → 2 5m bars
        resp = _make_resp(n_bars=10, shift_ms=60000)
        bars = self.src._decode_response(resp, self.spec, "5m")
        assert len(bars) == 2

    def test_15m_resamples_correctly(self) -> None:
        resp = _make_resp(n_bars=15, shift_ms=60000)
        bars = self.src._decode_response(resp, self.spec, "15m")
        assert len(bars) == 1

    def test_resampled_high_is_max_of_natives(self) -> None:
        resp = _make_resp(n_bars=5, shift_ms=60000)
        # make highs diverge so we can verify max
        resp["highs"] = [10, 50, 5, 20, 3]
        bars_1m = self.src._decode_response(resp, self.spec, "1m")
        bars_5m = self.src._decode_response(resp, self.spec, "5m")
        assert len(bars_5m) == 1
        expected_high = max(b.high for b in bars_1m)
        assert bars_5m[0].high == expected_high

    def test_1h_from_hour_bucket(self) -> None:
        # 1h response has shift=3600000; no resampling needed
        resp = _make_resp(n_bars=4, shift_ms=3600000)
        bars = self.src._decode_response(resp, self.spec, "1h")
        assert len(bars) == 4

    def test_4h_resamples_from_1h_bucket(self) -> None:
        resp = _make_resp(n_bars=8, shift_ms=3600000)
        bars = self.src._decode_response(resp, self.spec, "4h")
        assert len(bars) == 2


# ---------------------------------------------------------------------------
# Dukascopy._iter_bucket_urls
# ---------------------------------------------------------------------------


class TestDukascopyIterBucketUrls:
    def setup_method(self) -> None:
        self.src = Dukascopy()

    def _urls(self, bucket_type: str, start: date, end: date) -> list[str]:
        return [
            url
            for url, _ in self.src._iter_bucket_urls("EUR-USD", "minute", bucket_type, start, end)
        ]

    def test_day_bucket_count(self) -> None:
        urls = self._urls("day", date(2024, 1, 1), date(2024, 1, 3))
        assert len(urls) == 3

    def test_month_bucket_count(self) -> None:
        urls = self._urls("month", date(2024, 1, 1), date(2024, 3, 1))
        assert len(urls) == 3

    def test_year_bucket_count(self) -> None:
        urls = self._urls("year", date(2022, 1, 1), date(2024, 1, 1))
        assert len(urls) == 3

    def test_day_url_format(self) -> None:
        urls = self._urls("day", date(2024, 6, 15), date(2024, 6, 15))
        assert urls[0].endswith("/2024/6/15")

    def test_month_url_format(self) -> None:
        urls = self._urls("month", date(2024, 3, 1), date(2024, 3, 31))
        assert urls[0].endswith("/2024/3")

    def test_year_url_format(self) -> None:
        urls = self._urls("year", date(2023, 1, 1), date(2023, 12, 31))
        assert urls[0].endswith("/2023")


# ---------------------------------------------------------------------------
# Dukascopy.fetch_range  (mocked HTTP)
# ---------------------------------------------------------------------------


class TestDukascopyFetchRange:
    def setup_method(self) -> None:
        self.src = Dukascopy()

    def _mock_get(self, resp_dict: dict[str, Any]) -> MagicMock:
        return MagicMock(return_value=json.dumps(resp_dict).encode())

    def test_unknown_symbol_yields_nothing(self) -> None:
        bars = list(self.src.fetch_range("FAKEPAIR", "1m", date(2024, 1, 1), date(2024, 1, 1)))
        assert bars == []

    def test_unsupported_timeframe_yields_nothing(self) -> None:
        bars = list(self.src.fetch_range("EURUSD", "2m", date(2024, 1, 1), date(2024, 1, 1)))
        assert bars == []

    def test_network_error_skips_bucket(self) -> None:
        with patch.object(self.src, "_get", side_effect=OSError("timeout")):
            bars = list(self.src.fetch_range("EURUSD", "1m", date(2024, 1, 1), date(2024, 1, 1)))
        assert bars == []

    def test_valid_response_yields_bars(self) -> None:
        resp = _make_resp(n_bars=3)
        with patch.object(self.src, "_get", self._mock_get(resp)), patch("time.sleep"):
            bars = list(self.src.fetch_range("EURUSD", "1m", date(2024, 1, 1), date(2024, 1, 1)))
        assert len(bars) == 3
        assert all(b.symbol == "EURUSD" for b in bars)
        assert all(b.source == SourceId.DUKASCOPY for b in bars)

    def test_date_filter_applied(self) -> None:
        # bars with ts outside [start, end] are dropped
        # 2024-01-02 is outside fetch window 2024-01-01..2024-01-01
        ts_outside = int(datetime(2024, 1, 2, tzinfo=UTC).timestamp() * 1000)
        resp = _make_resp(n_bars=1, ts_ms=ts_outside)
        with patch.object(self.src, "_get", self._mock_get(resp)), patch("time.sleep"):
            bars = list(self.src.fetch_range("EURUSD", "1m", date(2024, 1, 1), date(2024, 1, 1)))
        assert bars == []


# ---------------------------------------------------------------------------
# HistData FX_PAIRS expansion
# ---------------------------------------------------------------------------


class TestHistDataExpansion:
    def test_has_all_majors(self) -> None:
        majors = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"}
        assert majors.issubset(HistData.FX_PAIRS.keys())

    def test_has_eur_crosses(self) -> None:
        crosses = {"EURGBP", "EURJPY", "EURCHF", "EURCAD", "EURAUD", "EURNZD"}
        assert crosses.issubset(HistData.FX_PAIRS.keys())

    def test_has_gbp_crosses(self) -> None:
        crosses = {"GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD"}
        assert crosses.issubset(HistData.FX_PAIRS.keys())

    def test_has_aud_nzd_crosses(self) -> None:
        crosses = {"AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD", "NZDJPY", "NZDCHF", "NZDCAD"}
        assert crosses.issubset(HistData.FX_PAIRS.keys())

    def test_has_chf_cad_crosses(self) -> None:
        assert {"CHFJPY", "CADJPY", "CADCHF"}.issubset(HistData.FX_PAIRS.keys())

    def test_total_pair_count_at_least_28(self) -> None:
        assert len(HistData.FX_PAIRS) >= 28

    def test_all_values_lowercase(self) -> None:
        assert all(v == v.lower() for v in HistData.FX_PAIRS.values())


# ---------------------------------------------------------------------------
# Dukascopy registry registration
# ---------------------------------------------------------------------------


class TestDukascopyRegistry:
    def test_in_sources_registry(self) -> None:
        from market.ingestion.sources import SOURCES

        assert SourceId.DUKASCOPY in SOURCES

    def test_registry_instance_is_dukascopy(self) -> None:
        from market.ingestion.sources import SOURCES

        assert isinstance(SOURCES[SourceId.DUKASCOPY], Dukascopy)


# ---------------------------------------------------------------------------
# _clamp_bucket_range — jetta serves closed buckets only (current → HTTP 400)
# ---------------------------------------------------------------------------


class TestClampBucketRange:
    """_clamp_bucket_range clamps to buckets strictly older than *today*."""

    T = date(2026, 7, 31)  # "today" per i test

    def test_day_bucket_caps_at_yesterday(self) -> None:
        s, e = _clamp_bucket_range(
            "day", date(2026, 7, 26), date(2026, 7, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2026, 7, 26), date(2026, 7, 30))

    def test_day_bucket_collapses_when_range_is_current_day(self) -> None:
        s, e = _clamp_bucket_range(
            "day", date(2026, 7, 31), date(2026, 7, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2026, 7, 30), date(2026, 7, 30))

    def test_month_bucket_caps_at_previous_month_end(self) -> None:
        s, e = _clamp_bucket_range(
            "month", date(2026, 7, 26), date(2026, 7, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2026, 6, 30), date(2026, 6, 30))

    def test_month_bucket_closed_month_is_not_capped(self) -> None:
        # giugno è un mese chiuso: servibile, nessun clamp/collapse
        s, e = _clamp_bucket_range(
            "month", date(2026, 6, 1), date(2026, 6, 2), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2026, 6, 1), date(2026, 6, 2))

    def test_month_bucket_after_rollover_includes_new_closed_month(self) -> None:
        s, e = _clamp_bucket_range(
            "month", date(2026, 7, 26), date(2026, 8, 5), date(2003, 5, 4), date(2026, 8, 5)
        )
        assert (s, e) == (date(2026, 7, 26), date(2026, 7, 31))

    def test_year_bucket_caps_at_previous_year_end(self) -> None:
        s, e = _clamp_bucket_range(
            "year", date(2026, 7, 28), date(2026, 7, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2025, 12, 31), date(2025, 12, 31))

    def test_year_bucket_closed_year_is_not_capped(self) -> None:
        # 2025 è un anno chiuso: servibile, nessun clamp/collapse (regressione
        # del bug che filtrava tutto: cap dipendeva da end, non da today)
        s, e = _clamp_bucket_range(
            "year", date(2025, 1, 1), date(2025, 12, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2025, 1, 1), date(2025, 12, 31))

    def test_year_bucket_after_rollover_includes_new_closed_year(self) -> None:
        s, e = _clamp_bucket_range(
            "year", date(2026, 12, 20), date(2027, 1, 15), date(2003, 5, 4), date(2027, 1, 15)
        )
        assert (s, e) == (date(2026, 12, 20), date(2026, 12, 31))

    def test_earliest_floor(self) -> None:
        s, e = _clamp_bucket_range(
            "day", date(2000, 1, 1), date(2026, 7, 31), date(2003, 5, 4), self.T
        )
        assert (s, e) == (date(2003, 5, 4), date(2026, 7, 30))
