"""BL-023 deps-spring — uvicorn/sse-starlette alive, redis/psycopg2 gone.

2026-08-03: the dead-dependency audit (verifica moduli reali, non nomi
pacchetto) found 5 truly-dead deps. Two were revived with real usage:
- uvicorn: entrypoint `python -m apps.api.main` (run()) — the FastAPI app
  had no launch path.
- sse-starlette: EventSourceResponse replaces the hand-rolled SSE loop in
  apps/api/routers/stream.py.
Three were removed (no consumer): redis, psycopg2-binary,
langchain-community (NATS covers the bus, asyncpg covers Postgres,
litellm+langgraph cover agents).

NOTE: apps.api.main must be imported INSIDE test functions, never at
module level — importing it during collection reads .env (ORACLE_API_KEY)
and locks auth on for the whole process, which breaks tests/api in the
full suite (401s). tests/api/conftest.py does the same.
"""

from __future__ import annotations


def test_api_entrypoint_run_is_callable() -> None:
    """uvicorn is alive: the app exposes a run() launch entry."""
    from apps.api.main import run

    assert callable(run)


def test_stream_route_registered_via_sse_starlette() -> None:
    """sse-starlette is alive: the SSE route is registered and uses
    EventSourceResponse (media type text/event-stream)."""
    from apps.api.main import app

    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/stream/positions" in paths
    responses = paths["/api/v1/stream/positions"]["get"]["responses"]
    assert "200" in responses


def test_redis_settings_removed() -> None:
    """redis is gone: OracleSettings no longer carries a redis section."""
    from core.config import OracleSettings

    settings = OracleSettings()
    assert not hasattr(settings, "redis")
    assert settings.nats.url == "nats://localhost:4222"
