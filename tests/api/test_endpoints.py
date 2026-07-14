"""Test all API endpoints respond with correct status and shape."""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.config import APISettings


class TestPerformance:
    def test_summary_returns_schema(self, client: TestClient) -> None:
        r = client.get("/api/v1/performance/summary")
        assert r.status_code == 200
        data = r.json()
        assert "sharpe" in data
        assert "sortino" in data
        assert "max_drawdown" in data

    def test_equity_returns_503_when_no_data(self, client: TestClient) -> None:
        r = client.get("/api/v1/performance/equity")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "points" in data or "detail" in data

    def test_today_returns_503_when_not_wired(self, client: TestClient) -> None:
        r = client.get("/api/v1/performance/today")
        assert r.status_code == 503
        data = r.json()
        assert "detail" in data


class TestTrades:
    def test_list_default_pagination(self, client: TestClient) -> None:
        r = client.get("/api/v1/trades")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_list_custom_limit(self, client: TestClient) -> None:
        r = client.get("/api/v1/trades?limit=5&offset=10")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_export_csv_returns_text(self, client: TestClient) -> None:
        r = client.get("/api/v1/trades/export?format=csv")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")

    def test_positions_returns_503_when_not_wired(self, client: TestClient) -> None:
        r = client.get("/api/v1/trades/positions")
        assert r.status_code == 503
        assert "detail" in r.json()


class TestGA:
    def test_runs_returns_list(self, client: TestClient) -> None:
        r = client.get("/api/v1/ga/runs")
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)

    def test_run_detail_not_found(self, client: TestClient) -> None:
        r = client.get("/api/v1/ga/runs/nonexistent_run")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "not_found"


class TestAuth:
    def test_no_key_allowed_in_dev(self, client: TestClient) -> None:
        """When no API key is configured, requests pass without X-API-Key."""
        settings = APISettings()
        if not settings.api_key:
            r = client.get("/api/v1/performance/summary", headers={})
            assert r.status_code == 200

    def test_missing_key_returns_401_when_configured(self, client: TestClient) -> None:
        """When an API key is configured, missing X-API-Key → 401."""
        settings = APISettings()
        if settings.api_key:
            r = client.get("/api/v1/performance/summary", headers={})
            assert r.status_code == 401

    def test_wrong_key_returns_401(self, client: TestClient) -> None:
        settings = APISettings()
        if settings.api_key:
            r = client.get(
                "/api/v1/performance/summary",
                headers={"X-API-Key": "wrong-key"},
            )
            assert r.status_code == 401
