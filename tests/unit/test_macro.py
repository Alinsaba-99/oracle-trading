"""Tests for M8 Macro — FRED, FXMacroData, and state aggregation."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import polars as pl
import pytest

from analytics.common.errors import MacroError
from analytics.macro.fred import KNOWN_SERIES, FREDClient
from analytics.macro.fxmacro import FXMacroDataClient
from analytics.macro.state import MacroSnapshot, MacroStatePublisher

# ======================================================================
# Helpers
# ======================================================================


def _fred_observations(*values: float, start: str = "2024-01-01") -> list[dict[str, str]]:
    """Build a FRED ``observations`` list with sequential monthly dates."""
    from datetime import datetime as dt

    base = dt.strptime(start, "%Y-%m-%d")
    obs: list[dict[str, str]] = []
    for i, v in enumerate(values):
        d = base.replace(month=base.month + i) if i else base
        obs.append({"date": d.strftime("%Y-%m-%d"), "value": str(v)})
    return obs


def _mock_fred_response(*values: float, start: str = "2024-01-01") -> dict:
    return {"observations": _fred_observations(*values, start=start)}


def _mock_fred_empty_response() -> dict:
    return {"observations": []}


def _mock_fred_missing_response() -> dict:
    return {}


# ======================================================================
# FREDClient
# ======================================================================


class TestFREDClientInit:
    def test_requires_api_key(self) -> None:
        """Missing API key raises MacroError."""
        with patch.dict("os.environ", clear=True), pytest.raises(MacroError, match="FRED_API_KEY"):
            FREDClient()

    def test_accepts_explicit_key(self) -> None:
        """Explicit key skips env lookup."""
        client = FREDClient(api_key="test-key-123")
        assert client._api_key == "test-key-123"

    def test_reads_env_var(self) -> None:
        """Uses FRED_API_KEY env var when available."""
        with patch.dict("os.environ", {"FRED_API_KEY": "env-key"}):
            client = FREDClient()
            assert client._api_key == "env-key"

    def test_known_series(self) -> None:
        """KNOWN_SERIES contains expected identifiers."""
        assert "GDP" in KNOWN_SERIES
        assert "CPI" in KNOWN_SERIES
        assert "UNRATE" in KNOWN_SERIES
        assert "FEDFUNDS" in KNOWN_SERIES
        assert "GDPC1" in KNOWN_SERIES


class TestFREDClientLifecycle:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        """Connect creates an httpx client; disconnect clears it."""
        client = FREDClient(api_key="test")
        assert client._client is None

        await client.connect()
        assert client._client is not None

        await client.disconnect()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Async context manager connects on enter, disconnects on exit."""
        async with FREDClient(api_key="test") as client:
            assert client._client is not None

        assert client._client is None

    @pytest.mark.asyncio
    async def test_fetch_without_connect_raises(self) -> None:
        """fetch_series raises MacroError when not connected."""
        client = FREDClient(api_key="test")
        with pytest.raises(MacroError, match=r"Not connected|call"):
            await client.fetch_series("GDP")


class TestFREDClientFetchSeries:
    """FRED response parsing and API interaction."""

    @pytest.mark.asyncio
    async def test_parses_valid_response(self) -> None:
        """Valid JSON observations become a Polars DataFrame."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_response(6.4, 4.9, 3.2))
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        df = await client.fetch_series("CPI")

        assert isinstance(df, pl.DataFrame)
        assert df.columns == ["date", "value"]
        assert len(df) == 3
        assert df["value"].to_list() == [6.4, 4.9, 3.2]
        assert str(df["date"].dtype) == "Date"

    @pytest.mark.asyncio
    async def test_filters_missing_observations(self) -> None:
        """Observations with ``"."`` or missing values are excluded."""
        client = FREDClient(api_key="test")
        observations = [
            {"date": "2024-01-01", "value": "5.0"},
            {"date": "2024-02-01", "value": "."},
            {"date": "2024-03-01", "value": ""},
            {"date": "2024-04-01", "value": None},
        ]
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value={"observations": observations})
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        df = await client.fetch_series("UNRATE")

        assert len(df) == 1
        assert df["value"][0] == 5.0

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        """Empty observations returns empty DataFrame with correct schema."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_empty_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        df = await client.fetch_series("GDP")

        assert len(df) == 0
        assert df.columns == ["date", "value"]

    @pytest.mark.asyncio
    async def test_missing_observations_key(self) -> None:
        """Response without ``observations`` raises MacroError."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_missing_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        with pytest.raises(MacroError, match="observations"):
            await client.fetch_series("GDP")

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        """HTTP 4xx/5xx raises MacroError."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Client Error",
            request=MagicMock(),
            response=MagicMock(status_code=404, text="Not Found"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        with pytest.raises(MacroError, match="FRED API HTTP 404"):
            await client.fetch_series("INVALID_SERIES")

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        """Request timeout raises MacroError."""
        client = FREDClient(api_key="test")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client._client = mock_client

        with pytest.raises(MacroError, match="timeout"):
            await client.fetch_series("GDP")

    @pytest.mark.asyncio
    async def test_request_error(self) -> None:
        """Any httpx.RequestError raises MacroError."""
        client = FREDClient(api_key="test")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection failed"))
        client._client = mock_client

        with pytest.raises(MacroError, match="request failed"):
            await client.fetch_series("GDP")

    @pytest.mark.asyncio
    async def test_sends_correct_params(self) -> None:
        """fetch_series sends series_id, api_key, file_type, and optional date params."""
        client = FREDClient(api_key="secret")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_empty_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        await client.fetch_series("GDP", start="2023-01-01", end="2023-12-31")

        mock_client.get.assert_called_once()
        _call_params = mock_client.get.call_args[1]["params"]
        assert _call_params["series_id"] == "GDP"
        assert _call_params["api_key"] == "secret"
        assert _call_params["file_type"] == "json"
        assert _call_params["observation_start"] == "2023-01-01"
        assert _call_params["observation_end"] == "2023-12-31"

    @pytest.mark.asyncio
    async def test_multiple_fetch(self) -> None:
        """fetch_multiple returns dict of series_id -> DataFrame."""
        client = FREDClient(api_key="test")

        def _make_resp(vals: list[float]) -> MagicMock:
            r = MagicMock()
            r.json = MagicMock(return_value=_mock_fred_response(*vals))
            r.raise_for_status = MagicMock()
            return r

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[_make_resp([6.4, 4.9]), _make_resp([3.5, 3.0])])
        client._client = mock_client

        results = await client.fetch_multiple(["CPI", "FEDFUNDS"])

        assert set(results.keys()) == {"CPI", "FEDFUNDS"}
        assert len(results["CPI"]) == 2
        assert len(results["FEDFUNDS"]) == 2


class TestFREDClientRateLimiting:
    """Rate limit enforcement — 120 req/min max."""

    @pytest.mark.asyncio
    async def test_under_limit_passes_immediately(self) -> None:
        """Fewer than 120 requests in the window passes without sleep."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_empty_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        t0 = time.monotonic()
        for _ in range(50):
            await client.fetch_series("GDP")
        elapsed = time.monotonic() - t0

        # Should complete quickly — no rate limit backpressure
        assert elapsed < 5.0

    @pytest.mark.asyncio
    async def test_rate_limit_throttles(self) -> None:
        """Exceeding 120 req/min blocks until a slot opens."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_empty_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        # Fire 120 requests — these all pass without throttle
        for _ in range(120):
            await client.fetch_series("GDP")

        # The 121st should delay
        t0 = time.monotonic()
        await client.fetch_series("GDP")
        elapsed = time.monotonic() - t0

        # Should have waited at least some non-trivial time
        # (at least 0.5s given no waits between the 120 rapid calls)
        assert elapsed > 0.1, "Rate limiter did not throttle"

    @pytest.mark.asyncio
    async def test_window_evicts_old_requests(self) -> None:
        """Timestamps older than 60s are evicted, allowing new requests."""
        client = FREDClient(api_key="test")
        mock_resp = MagicMock()
        mock_resp.json = MagicMock(return_value=_mock_fred_empty_response())
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        client._client = mock_client

        # Fill the window
        for _ in range(120):
            await client.fetch_series("GDP")
        assert len(client._request_times) == 120

        # Manually age the timestamps beyond the window
        old = time.monotonic() - 61.0
        client._request_times = client._request_times.__class__([old] * 120)

        # Next request should evict all stale entries
        await client.fetch_series("GDP")
        # Eviction happens inside _acquire — queue should now have 1 entry
        assert len(client._request_times) <= 2


# ======================================================================
# FXMacroDataClient
# ======================================================================


class TestFXMacroDataClientMock:
    """Mock-mode behaviour (default, no API key)."""

    @pytest.mark.asyncio
    async def test_fetch_central_bank_rates_returns_expected_keys(self) -> None:
        """Returns a dict mapping currency codes to rates."""
        client = FXMacroDataClient()
        rates = await client.fetch_central_bank_rates()

        assert isinstance(rates, dict)
        assert "USD" in rates
        assert "EUR" in rates
        assert "GBP" in rates
        assert "JPY" in rates
        assert all(isinstance(v, float) for v in rates.values())

    @pytest.mark.asyncio
    async def test_fetch_central_bank_rates_consistent(self) -> None:
        """Subsequent calls return the same default rates."""
        client = FXMacroDataClient()
        rates1 = await client.fetch_central_bank_rates()
        rates2 = await client.fetch_central_bank_rates()
        assert rates1 == rates2

    @pytest.mark.asyncio
    async def test_fetch_inflation_us(self) -> None:
        """US inflation returns a Polars DataFrame."""
        client = FXMacroDataClient()
        df = await client.fetch_inflation_data("US")

        assert isinstance(df, pl.DataFrame)
        assert df.columns == ["date", "rate"]
        assert len(df) > 0
        assert str(df["date"].dtype) == "Date"

    @pytest.mark.asyncio
    async def test_fetch_inflation_unknown_country(self) -> None:
        """Unsupported country raises MacroError with supported list."""
        client = FXMacroDataClient()
        with pytest.raises(MacroError, match="Unsupported country"):
            await client.fetch_inflation_data("XX")

    @pytest.mark.asyncio
    async def test_supported_countries(self) -> None:
        """supported_countries returns expected codes."""
        client = FXMacroDataClient()
        countries = client.supported_countries()
        assert "US" in countries
        assert "GB" in countries
        assert "JP" in countries
        assert "DE" in countries

    @pytest.mark.asyncio
    async def test_inflation_data_sorted(self) -> None:
        """Inflation data is sorted chronologically."""
        client = FXMacroDataClient()
        df = await client.fetch_inflation_data("US")
        dates = df["date"].to_list()
        assert dates == sorted(dates)


# ======================================================================
# Macro State
# ======================================================================


class TestMacroSnapshot:
    """MacroSnapshot dataclass behaviour."""

    def test_default_timestamp_is_utc(self) -> None:
        """Default timestamp is timezone-aware UTC."""
        snap = MacroSnapshot()
        assert snap.timestamp.tzinfo is not None

    def test_summary_includes_expected_keys(self) -> None:
        """summary() returns a dict with top-level keys."""
        snap = MacroSnapshot(
            fred_series={
                "GDP": pl.DataFrame(
                    {
                        "date": pl.Series(["2024-01-01"], dtype=pl.String).str.to_date("%Y-%m-%d"),
                        "value": pl.Series([3.0], dtype=pl.Float64),
                    }
                )
            },
            central_bank_rates={"USD": 5.5},
            inflation={
                "US": pl.DataFrame(
                    {
                        "date": pl.Series(["2024-01-01"], dtype=pl.String).str.to_date("%Y-%m-%d"),
                        "rate": pl.Series([3.1], dtype=pl.Float64),
                    }
                )
            },
        )
        s = snap.summary()

        assert "timestamp" in s
        assert "fred" in s
        assert "central_bank_rates" in s
        assert "inflation" in s
        assert s["fred"]["GDP"]["latest_value"] == 3.0
        assert s["central_bank_rates"]["USD"] == 5.5
        assert s["inflation"]["US"]["latest_rate"] == 3.1

    def test_summary_empty_series(self) -> None:
        """Empty DataFrames produce None entries."""
        snap = MacroSnapshot(
            fred_series={
                "GDP": pl.DataFrame(
                    {"date": pl.Series([], dtype=pl.Date), "value": pl.Series([], dtype=pl.Float64)}
                )
            }
        )
        s = snap.summary()
        assert s["fred"]["GDP"] is None


class TestMacroStatePublisher:
    """State publisher aggregation and publishing."""

    @pytest.mark.asyncio
    async def test_collect_returns_snapshot(self) -> None:
        """collect() returns a MacroSnapshot with data from both sources."""
        fred = FREDClient(api_key="test")
        fx = FXMacroDataClient()

        # Stub FRED fetch_multiple
        fred_df = pl.DataFrame(
            {
                "date": pl.Series(["2024-01-01"], dtype=pl.String).str.to_date("%Y-%m-%d"),
                "value": pl.Series([3.0], dtype=pl.Float64),
            }
        )
        fred.fetch_multiple = AsyncMock(return_value={"GDP": fred_df})  # type: ignore[method-assign]

        publisher = MacroStatePublisher(
            fred_client=fred, fx_client=fx, fred_series=["GDP"], inflation_countries=["US"]
        )
        snapshot = await publisher.collect()

        assert isinstance(snapshot, MacroSnapshot)
        assert "GDP" in snapshot.fred_series
        assert "USD" in snapshot.central_bank_rates
        assert "US" in snapshot.inflation

    @pytest.mark.asyncio
    async def test_collect_graceful_failure(self) -> None:
        """A failing data source produces empty placeholders, not a hard crash."""
        fred = FREDClient(api_key="test")
        fx = FXMacroDataClient()

        fred.fetch_multiple = AsyncMock(  # type: ignore[method-assign]
            side_effect=MacroError("FRED down")
        )

        publisher = MacroStatePublisher(
            fred_client=fred, fx_client=fx, fred_series=["GDP"], inflation_countries=[]
        )
        snapshot = await publisher.collect()

        # FRED data empty, but other data still populated
        assert snapshot.fred_series == {}
        assert "USD" in snapshot.central_bank_rates

    @pytest.mark.asyncio
    async def test_collect_summary(self) -> None:
        """collect_summary returns the dict form directly."""
        fred = FREDClient(api_key="test")
        fx = FXMacroDataClient()
        fred_df = pl.DataFrame(
            {
                "date": pl.Series(["2024-01-01"], dtype=pl.String).str.to_date("%Y-%m-%d"),
                "value": pl.Series([3.0], dtype=pl.Float64),
            }
        )
        fred.fetch_multiple = AsyncMock(return_value={"GDP": fred_df})  # type: ignore[method-assign]

        publisher = MacroStatePublisher(
            fred_client=fred, fx_client=fx, fred_series=["GDP"], inflation_countries=[]
        )
        summary = await publisher.collect_summary()

        assert isinstance(summary, dict)
        assert "fred" in summary
        assert summary["fred"]["GDP"]["latest_value"] == 3.0

    @pytest.mark.asyncio
    async def test_publish_calls_nats(self) -> None:
        """publish() sends the summary via NATS."""
        fred = FREDClient(api_key="test")
        fx = FXMacroDataClient()
        fred_df = pl.DataFrame(
            {
                "date": pl.Series(["2024-01-01"], dtype=pl.String).str.to_date("%Y-%m-%d"),
                "value": pl.Series([3.0], dtype=pl.Float64),
            }
        )
        fred.fetch_multiple = AsyncMock(return_value={"GDP": fred_df})  # type: ignore[method-assign]

        publisher = MacroStatePublisher(
            fred_client=fred, fx_client=fx, fred_series=["GDP"], inflation_countries=[]
        )

        nats_mock = AsyncMock()
        summary = await publisher.publish(nats_mock)

        nats_mock.publish.assert_called_once()
        # subject is the first positional arg
        args, _kwargs = nats_mock.publish.call_args
        assert args[0] == "analytics.macro.state"
        assert "fred" in summary
