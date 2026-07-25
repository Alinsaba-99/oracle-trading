"""BL-002 anti-overwrite guard tests for yfinance_futures pinning.

Verifies that DataFetcher.yfinance_futures refuses to overwrite a pinned
dataset unless explicitly allowed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def fake_data_dir(tmp_path: Path) -> Path:
    """Create a fake data/ohlcv dir with a pinned dataset that should NOT be touched."""
    fake = tmp_path / "data"
    ohlcv = fake / "ohlcv"
    pinned = fake / "pinned"
    ohlcv.mkdir(parents=True)
    pinned.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [101.0, 102.0, 103.0, 104.0, 105.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        }
    )
    df.to_parquet(ohlcv / "ES_1d.parquet")
    df.to_parquet(pinned / "ES_1d_test.parquet")
    return fake


def test_yfinance_futures_refuses_overwrite_pinned(
    fake_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling yfinance_futures without allow_overwrite must NOT mutate ES_1d.parquet."""
    from market.data_sources import DataFetcher

    fetcher = DataFetcher.__new__(DataFetcher)
    fetcher.config = None
    fetcher.DATA_DIR = fake_data_dir / "ohlcv"

    orig_path = fake_data_dir / "ohlcv" / "ES_1d.parquet"
    orig_hash = hashlib.sha256(orig_path.read_bytes()).hexdigest()

    def _fake_yf(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "Open": [999.0, 999.0],
                "High": [999.0, 999.0],
                "Low": [999.0, 999.0],
                "Close": [999.0, 999.0],
                "Volume": [0, 0],
            }
        )

    monkeypatch.setattr("yfinance.download", _fake_yf)

    fetcher.yfinance_futures("ES", period="1mo")

    new_hash = hashlib.sha256(orig_path.read_bytes()).hexdigest()
    assert new_hash == orig_hash, "ES_1d.parquet was overwritten despite pinning"


def test_yfinance_futures_overwrites_when_allowed(
    fake_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_overwrite=True the fetch should succeed and the file should change."""
    from market.data_sources import DataFetcher

    fetcher = DataFetcher.__new__(DataFetcher)
    fetcher.config = None
    fetcher.DATA_DIR = fake_data_dir / "ohlcv"

    def _fake_yf(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "Open": [888.0, 888.0],
                "High": [888.0, 888.0],
                "Low": [888.0, 888.0],
                "Close": [888.0, 888.0],
                "Volume": [0, 0],
            }
        )

    monkeypatch.setattr("yfinance.download", _fake_yf)

    orig_path = fake_data_dir / "ohlcv" / "ES_1d.parquet"
    orig_hash = hashlib.sha256(orig_path.read_bytes()).hexdigest()

    fetcher.yfinance_futures("ES", period="1mo", allow_overwrite=True)

    new_hash = hashlib.sha256(orig_path.read_bytes()).hexdigest()
    assert new_hash != orig_hash, "allow_overwrite=True did not actually overwrite"
