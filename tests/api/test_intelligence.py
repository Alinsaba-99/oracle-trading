"""API tests for the isolated ElizaOS intelligence gateway."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.api.main import app


def _payload() -> dict[str, object]:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC).isoformat()
    return {
        "observation_id": "api-observation-1",
        "agent_id": "eliza-news-scout",
        "event_time": now,
        "available_at": now,
        "instruments": ["MES"],
        "observation_type": "macro_surprise",
        "direction": "bullish",
        "confidence": 0.7,
        "novelty": 0.8,
        "time_horizon": "4h",
        "summary": "macro surprise",
        "evidence": [
            {
                "source": "official",
                "observed_at": now,
                "available_at": now,
                "content_hash": "hash",
                "credibility": 0.9,
            }
        ],
    }


def test_intelligence_gateway_accepts_without_execution_access(tmp_path, monkeypatch) -> None:
    from apps.api.routers import intelligence

    monkeypatch.setattr(
        intelligence, "inbox", intelligence.SQLiteIntelligenceInbox(tmp_path / "intelligence.db")
    )
    response = TestClient(app).post("/api/v1/intelligence/observations", json=_payload())

    assert response.status_code == 202
    assert response.json() == {
        "observation_id": "api-observation-1",
        "accepted": True,
        "duplicate": False,
        "execution_access": False,
    }
