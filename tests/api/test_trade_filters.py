"""Test trade_service filtering logic against the real DB."""

from __future__ import annotations

from apps.api.services.trade_service import list_trades


class TestTradeFilters:
    """These tests exercise the filtering logic.

    They run against the real experiments.db if available, or gracefully
    handle its absence (returning empty results).
    """

    def test_no_filters(self) -> None:
        r = list_trades(limit=5)
        assert len(r["items"]) <= 5
        assert r["limit"] == 5

    def test_filter_by_engine(self) -> None:
        r = list_trades(engine="walk_forward")
        for item in r["items"]:
            assert item["engine"] == "walk_forward"

        r2 = list_trades(engine="vectorized")
        for item in r2["items"]:
            assert item["engine"] == "vectorized"

    def test_filter_by_fold(self) -> None:
        r = list_trades(fold="0")
        for item in r["items"]:
            assert item["fold"] == "0"

    def test_filter_engine_and_fold(self) -> None:
        r = list_trades(engine="walk_forward", fold="0")
        for item in r["items"]:
            assert item["engine"] == "walk_forward"
            assert item["fold"] == "0"

    def test_date_range(self) -> None:
        r = list_trades(from_date="2026-07-12", to_date="2026-07-13")
        for item in r["items"]:
            assert item["time"] >= "2026-07-12"
            assert item["time"] <= "2026-07-13T23:59:59"

    def test_invalid_engine_returns_empty(self) -> None:
        r = list_trades(engine="nonexistent_engine")
        assert len(r["items"]) == 0
        assert r["total"] == 0

    def test_safe_float_handles_inf_nan(self) -> None:
        """_safe_float is called internally; this tests the service doesn't crash."""
        r = list_trades(limit=3)
        # Just verify no exception and items are well-formed
        for item in r["items"]:
            assert isinstance(item["total_return"], float)
            assert isinstance(item["sharpe_ratio"], float)
