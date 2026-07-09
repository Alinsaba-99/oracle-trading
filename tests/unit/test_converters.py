"""Tests for analytics data converters (Polars/pandas/NumPy interop)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import pytest

from analytics.common.converters import (
    from_numpy,
    to_numpy_2d,
    to_pandas,
    to_polars,
    validate_frame,
)


class TestToPolars:
    """Tests for to_polars converter."""

    def test_from_polars_dataframe(self) -> None:
        df = pl.DataFrame({"a": [1, 2, 3]})
        result = to_polars(df)
        assert isinstance(result, pl.DataFrame)
        assert result.shape == (3, 1)

    def test_from_lazyframe(self) -> None:
        lf = pl.LazyFrame({"a": [1, 2, 3]})
        result = to_polars(lf)
        assert isinstance(result, pl.DataFrame)
        assert result.shape == (3, 1)

    def test_from_pandas(self) -> None:
        pdf = pd.DataFrame({"a": [1, 2, 3]})
        result = to_polars(pdf)
        assert isinstance(result, pl.DataFrame)
        assert result.shape == (3, 1)


class TestToPandas:
    """Tests for to_pandas converter."""

    def test_from_polars(self) -> None:
        pdf = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        plf = pl.from_pandas(pdf)
        result = to_pandas(plf)
        pd.testing.assert_frame_equal(result, pdf)

    def test_from_lazyframe(self) -> None:
        pdf = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        lf = pl.LazyFrame(pdf)
        result = to_pandas(lf)
        pd.testing.assert_frame_equal(result, pdf)


class TestToNumpy2D:
    """Tests for to_numpy_2d converter."""

    def test_from_polars_series(self) -> None:
        s = pl.Series("x", [1.0, 2.0, 3.0])
        result = to_numpy_2d(s)
        assert result.shape == (3, 1)
        assert result.dtype == np.float64

    def test_from_pandas_series(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0], name="x")
        result = to_numpy_2d(s)
        assert result.shape == (3, 1)
        assert result.dtype == np.float64

    def test_from_numpy_1d(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        result = to_numpy_2d(arr)
        assert result.shape == (3, 1)

    def test_ta_lib_compatible_shape(self) -> None:
        """TA-Lib expects 2D float64 arrays with shape (N, 1)."""
        s = pl.Series("close", [100.0, 101.0, 102.0])
        result = to_numpy_2d(s)
        assert result.ndim == 2
        assert result.shape[1] == 1
        assert result.dtype == np.float64


class TestFromNumpy:
    """Tests for from_numpy converter."""

    def test_basic_conversion(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        result = from_numpy(arr)
        assert isinstance(result, pl.Series)
        assert result.dtype == pl.Float64
        assert result.to_list() == [1.0, 2.0, 3.0]

    def test_nan_to_null(self) -> None:
        arr = np.array([1.0, np.nan, 3.0])
        result = from_numpy(arr)
        assert result[0] == 1.0
        assert result[1] is None
        assert result[2] == 3.0

    def test_all_nan(self) -> None:
        arr = np.array([np.nan, np.nan])
        result = from_numpy(arr)
        assert result[0] is None
        assert result[1] is None

    def test_2d_input_gets_raveled(self) -> None:
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = from_numpy(arr)
        assert len(result) == 4
        assert result.to_list() == [1.0, 2.0, 3.0, 4.0]


class TestValidateFrame:
    """Tests for validate_frame utility."""

    def test_passes_with_all_columns(self) -> None:
        df = pl.DataFrame({"open": [1.0], "close": [2.0], "volume": [100]})
        validate_frame(df, ["open", "close"])  # should not raise

    def test_raises_on_missing_columns(self) -> None:
        df = pl.DataFrame({"open": [1.0]})
        with pytest.raises(ValueError, match=r"Missing required columns:.*close"):
            validate_frame(df, ["open", "close"])

    def test_raises_on_multiple_missing(self) -> None:
        df = pl.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match=r"Missing required columns:.*b.*c"):
            validate_frame(df, ["a", "b", "c"])


class TestRoundTrip:
    """Tests for round-trip conversions."""

    def test_pandas_polars_roundtrip(self) -> None:
        original = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
        polars_df = to_polars(original)
        assert isinstance(polars_df, pl.DataFrame)
        back = to_pandas(polars_df)
        pd.testing.assert_frame_equal(original, back)

    def test_numpy_polars_roundtrip(self) -> None:
        arr = np.array([1.5, 2.5, 3.5])
        series = from_numpy(arr)
        back = series.to_numpy()
        np.testing.assert_array_almost_equal(arr, back)
