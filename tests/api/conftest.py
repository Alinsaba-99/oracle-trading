"""Pytest fixtures for API endpoint tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point trade_service at the real experiments.db, or stub if missing."""
    real_db = Path(__file__).resolve().parents[2] / "experiments" / "experiments.db"
    if real_db.exists():
        return  # uses the default path in trade_service.py

    monkeypatch.setattr(
        "apps.api.services.trade_service._DB_PATH", Path("/nonexistent/experiments.db")
    )
    monkeypatch.setattr("apps.api.services.checkpoint_reader.list_ga_runs", lambda: [])
    monkeypatch.setattr("apps.api.services.checkpoint_reader.get_ga_run", lambda _run_id: None)
    monkeypatch.setattr("apps.api.services.checkpoint_reader.get_latest_run_summary", lambda: None)
    monkeypatch.setattr("apps.api.services.checkpoint_reader.get_equity_curve", lambda: [])


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient without API key (debug mode)."""
    from apps.api.main import app

    return TestClient(app)
