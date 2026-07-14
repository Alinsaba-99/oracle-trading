"""Tests for the yfinance FX data adapter (offline — no network)."""

from __future__ import annotations

import pandas as pd
import polars as pl
import pytest

from analytics.backtest.fx_data import OHLCV_SCHEMA, YFINANCE_SYMBOL_MAP, _to_wide_ohlcv


class TestSymbolMap:
    def test_forex_pairs_mapped(self) -> None:
        assert YFINANCE_SYMBOL_MAP["EURUSD"] == "EURUSD=X"
        assert YFINANCE_SYMBOL_MAP["GBPUSD"] == "GBPUSD=X"

    def test_gold_and_indices_mapped(self) -> None:
        assert YFINANCE_SYMBOL_MAP["XAUUSD"] == "GC=F"
        assert YFINANCE_SYMBOL_MAP["NAS100"] == "^NDX"


class TestToWideOhlcv:
    def test_flattens_multiindex_like_yfinance(self) -> None:
        # Reproduce yfinance's (Price, Ticker) MultiIndex columns.
        idx = pd.date_range("2026-07-10", periods=3, freq="D")
        cols = pd.MultiIndex.from_tuples(
            [
                ("Open", "EURUSD=X"),
                ("High", "EURUSD=X"),
                ("Low", "EURUSD=X"),
                ("Close", "EURUSD=X"),
                ("Volume", "EURUSD=X"),
            ]
        )
        df_pd = pd.DataFrame(
            [
                [1.10, 1.11, 1.09, 1.105, 0],
                [1.105, 1.12, 1.10, 1.115, 0],
                [1.115, 1.13, 1.11, 1.125, 0],
            ],
            index=idx,
            columns=cols,
        )

        wide = _to_wide_ohlcv(df_pd)

        assert list(wide.columns) == list(OHLCV_SCHEMA.keys())
        assert wide.height == 3
        assert wide["close"].to_list() == [1.105, 1.115, 1.125]
        assert wide.schema["timestamp"] == pl.Datetime

    def test_empty_dataframe_returns_schema(self) -> None:
        df_pd = pd.DataFrame(columns=["Open", "Close"]).set_index(pd.DatetimeIndex([]))
        wide = _to_wide_ohlcv(df_pd)
        assert wide.is_empty()
        assert list(wide.columns) == list(OHLCV_SCHEMA.keys())


@pytest.mark.skip(reason="network smoke — run manually: fetch_ohlcv('EURUSD', period='5d')")
class TestNetworkSmoke:
    def test_fetch_eurusd(self) -> None:
        from analytics.backtest.fx_data import fetch_ohlcv

        df = fetch_ohlcv("EURUSD", period="5d")
        assert not df.is_empty()
