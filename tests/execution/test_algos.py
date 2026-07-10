"""Tests for execution algos (VWAP, TWAP, Iceberg, scheduler, factory, market data)."""

from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from execution.algos.factory import ALGO_REGISTRY, create_algo
from execution.algos.iceberg import IcebergAlgo
from execution.algos.scheduler import AlgoScheduler
from execution.algos.twap import TWAPAlgo
from execution.algos.vwap import VWAPAlgo
from execution.market_data import MarketDataFeed, MarketDataSnapshot
from execution.order_manager.types import FillReport

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture(autouse=True)
def _mock_asyncio_sleep() -> Generator[None, None, None]:
    """Prevent actual sleeps in algo execution."""
    with patch("asyncio.sleep", AsyncMock(return_value=None)):
        yield


@pytest.fixture
def mock_order() -> MagicMock:
    """Mock Order with a standard quantity."""
    order: MagicMock = MagicMock()
    order.quantity = Decimal("1000")
    return order


@pytest.fixture
def mock_market_data() -> MagicMock:
    """Mock MarketDataSnapshot with uniform volume profile."""
    md: MagicMock = MagicMock()
    md.bid = Decimal("99.50")
    md.ask = Decimal("100.50")
    md.last = Decimal("100.00")
    md.volume_profile = [0.05] * 24
    return md


# =========================================================================
# AlgoScheduler tests
# =========================================================================


class TestAlgoScheduler:
    """AlgoScheduler slicing logic."""

    def test_time_slices_divides_correctly(self) -> None:
        """time_slices divides 3600s into 12 equal intervals."""
        slices = AlgoScheduler.time_slices(3600, 12)
        assert len(slices) == 12
        assert all(s == 300 for s in slices)
        assert sum(slices) == 3600

    def test_time_slices_zero_returns_total(self) -> None:
        """time_slices with 0 slices returns [total_seconds]."""
        slices = AlgoScheduler.time_slices(3600, 0)
        assert slices == [3600]

    def test_time_slices_single_slice(self) -> None:
        """time_slices with 1 slice returns [total_seconds]."""
        slices = AlgoScheduler.time_slices(3600, 1)
        assert slices == [3600]

    def test_volume_slices_matches_profile(self) -> None:
        """volume_slices proportions match the input profile."""
        profile = [0.1, 0.2, 0.3, 0.4]
        slices = AlgoScheduler.volume_slices(Decimal("1000"), profile, 4)
        assert len(slices) == 4
        assert sum(slices) == Decimal("1000")
        ratios = [float(s / Decimal("1000")) for s in slices]
        for ratio, expected in zip(ratios, profile, strict=False):
            assert abs(ratio - expected) < 0.001

    def test_volume_slices_empty_profile(self) -> None:
        """volume_slices with empty profile returns [total_quantity]."""
        slices = AlgoScheduler.volume_slices(Decimal("1000"), [], 4)
        assert slices == [Decimal("1000")]

    def test_volume_slices_zero_slices(self) -> None:
        """volume_slices with n_slices=0 returns [total_quantity]."""
        slices = AlgoScheduler.volume_slices(Decimal("1000"), [0.1, 0.2], 0)
        assert slices == [Decimal("1000")]

    def test_volume_slices_zero_quantity(self) -> None:
        """volume_slices with zero quantity returns zero slices."""
        profile = [0.1, 0.2, 0.3, 0.4]
        slices = AlgoScheduler.volume_slices(Decimal("0"), profile, 4)
        assert len(slices) == 4
        assert all(s == Decimal("0") for s in slices)


# =========================================================================
# VWAPAlgo tests
# =========================================================================


class TestVWAPAlgo:
    """VWAP execution algo."""

    async def test_slices_according_to_volume_profile(
        self,
        mock_order: MagicMock,
        mock_market_data: MagicMock,
    ) -> None:
        """VWAP yields fills proportional to volume profile."""
        algo = VWAPAlgo(n_slices=4)
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, mock_market_data):
            fills.append(fill)
        assert len(fills) == 4
        assert all(isinstance(f, FillReport) for f in fills)
        assert sum(f.quantity for f in fills) == Decimal("1000")

    async def test_skips_zero_quantity_slices(
        self,
        mock_order: MagicMock,
    ) -> None:
        """VWAP skips slices where volume profile yields zero quantity."""
        algo = VWAPAlgo(n_slices=12)
        md: MagicMock = MagicMock()
        md.bid = Decimal("99.50")
        md.ask = Decimal("100.50")
        md.volume_profile = [1.0] + [0.0] * 23
        mock_order.quantity = Decimal("1000")
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, md):
            fills.append(fill)
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("1000")

    async def test_single_slice(self) -> None:
        """VWAP with single slice fills entire quantity at once."""
        algo = VWAPAlgo(n_slices=1)
        order: MagicMock = MagicMock()
        order.quantity = Decimal("100")
        md: MagicMock = MagicMock()
        md.bid = Decimal("99.50")
        md.ask = Decimal("100.50")
        md.volume_profile = [1.0]
        fills: list[FillReport] = []
        async for fill in algo.execute(order, md):
            fills.append(fill)
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("100")

    async def test_fill_price_is_midpoint(self) -> None:
        """VWAP uses midpoint of bid/ask as fill price."""
        algo = VWAPAlgo(n_slices=1)
        order: MagicMock = MagicMock()
        order.quantity = Decimal("100")
        md: MagicMock = MagicMock()
        md.bid = Decimal("99.00")
        md.ask = Decimal("101.00")
        md.volume_profile = [1.0]
        async for fill in algo.execute(order, md):
            assert fill.price == Decimal("100.00")


# =========================================================================
# TWAPAlgo tests
# =========================================================================


class TestTWAPAlgo:
    """TWAP execution algo."""

    async def test_produces_correct_number_of_slices(
        self,
        mock_order: MagicMock,
        mock_market_data: MagicMock,
    ) -> None:
        """TWAP yields correct number of equal-sized fills."""
        algo = TWAPAlgo(n_slices=6)
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, mock_market_data):
            fills.append(fill)
        assert len(fills) == 6
        assert all(isinstance(f, FillReport) for f in fills)
        expected_qty = Decimal("1000") / 6
        assert all(f.quantity == expected_qty for f in fills)

    async def test_zero_quantity(
        self,
        mock_order: MagicMock,
        mock_market_data: MagicMock,
    ) -> None:
        """TWAP with zero quantity yields zero-quantity fills."""
        mock_order.quantity = Decimal("0")
        algo = TWAPAlgo(n_slices=6)
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, mock_market_data):
            fills.append(fill)
        assert len(fills) == 6
        assert all(f.quantity == Decimal("0") for f in fills)

    async def test_uses_last_price(
        self,
        mock_market_data: MagicMock,
    ) -> None:
        """TWAP uses market last price as fill price."""
        algo = TWAPAlgo(n_slices=1)
        order: MagicMock = MagicMock()
        order.quantity = Decimal("100")
        async for fill in algo.execute(order, mock_market_data):
            assert fill.price == Decimal("100.00")


# =========================================================================
# IcebergAlgo tests
# =========================================================================


class TestIcebergAlgo:
    """Iceberg execution algo."""

    async def test_divides_into_display_size_chunks(
        self,
        mock_order: MagicMock,
        mock_market_data: MagicMock,
    ) -> None:
        """Iceberg yields display_size chunks, last one is remainder."""
        mock_order.quantity = Decimal("250")
        algo = IcebergAlgo(
            display_size=Decimal("100"),
            refresh_interval_s=0.01,
        )
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, mock_market_data):
            fills.append(fill)
        assert len(fills) == 3
        assert fills[0].quantity == Decimal("100")
        assert fills[1].quantity == Decimal("100")
        assert fills[2].quantity == Decimal("50")
        assert sum(f.quantity for f in fills) == Decimal("250")

    async def test_single_chunk_when_below_display_size(
        self,
        mock_order: MagicMock,
        mock_market_data: MagicMock,
    ) -> None:
        """Iceberg yields single fill when quantity below display size."""
        mock_order.quantity = Decimal("50")
        algo = IcebergAlgo(display_size=Decimal("100"), refresh_interval_s=0.01)
        fills: list[FillReport] = []
        async for fill in algo.execute(mock_order, mock_market_data):
            fills.append(fill)
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("50")

    async def test_exact_multiple(self) -> None:
        """Iceberg with exact multiple of display size."""
        algo = IcebergAlgo(display_size=Decimal("50"), refresh_interval_s=0.01)
        order: MagicMock = MagicMock()
        order.quantity = Decimal("200")
        md: MagicMock = MagicMock()
        md.last = Decimal("100.00")
        fills: list[FillReport] = []
        async for fill in algo.execute(order, md):
            fills.append(fill)
        assert len(fills) == 4
        assert all(f.quantity == Decimal("50") for f in fills)


# =========================================================================
# Factory tests
# =========================================================================


class TestCreateAlgo:
    """Algo factory."""

    def test_returns_vwap(self) -> None:
        """create_algo('vwap') returns VWAPAlgo instance."""
        algo = create_algo("vwap")
        assert isinstance(algo, VWAPAlgo)

    def test_returns_twap(self) -> None:
        """create_algo('twap') returns TWAPAlgo instance."""
        algo = create_algo("twap")
        assert isinstance(algo, TWAPAlgo)

    def test_returns_iceberg(self) -> None:
        """create_algo('iceberg') returns IcebergAlgo instance."""
        algo = create_algo("iceberg")
        assert isinstance(algo, IcebergAlgo)

    def test_with_config_overrides(self) -> None:
        """create_algo with config overrides default params."""
        algo = create_algo("vwap", {"n_slices": 6})
        assert isinstance(algo, VWAPAlgo)
        assert algo._n_slices == 6  # type: ignore[attr-defined]

    def test_returns_none_for_market(self) -> None:
        """create_algo('market') returns None for direct routing."""
        assert create_algo("market") is None

    def test_raises_for_unknown(self) -> None:
        """create_algo('unknown') raises ValueError."""
        with pytest.raises(ValueError, match="Unknown algo"):
            create_algo("unknown")

    def test_registry_contents(self) -> None:
        """ALGO_REGISTRY maps all expected algo names."""
        assert "vwap" in ALGO_REGISTRY
        assert "twap" in ALGO_REGISTRY
        assert "iceberg" in ALGO_REGISTRY
        assert ALGO_REGISTRY["vwap"] is VWAPAlgo
        assert ALGO_REGISTRY["twap"] is TWAPAlgo
        assert ALGO_REGISTRY["iceberg"] is IcebergAlgo


# =========================================================================
# MarketDataFeed tests
# =========================================================================


class TestMarketDataFeed:
    """Market data feed."""

    async def test_snapshot_returns_snapshot(self) -> None:
        """feed.snapshot returns a populated MarketDataSnapshot."""
        feed = MarketDataFeed()
        snap = await feed.snapshot("AAPL")
        assert isinstance(snap, MarketDataSnapshot)
        assert snap.instrument_id == "AAPL"
        assert snap.bid == Decimal("99.50")
        assert snap.ask == Decimal("100.50")
        assert snap.last == Decimal("100.00")
        assert len(snap.volume_profile) == 24
        assert abs(sum(snap.volume_profile) - 1.0) < 0.001
        assert snap.timestamp != ""
