"""Oracle Dashboard API — FastAPI application."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from apps.api.config import APISettings
from apps.api.routers import router
from core.domain.guard import current_mode, guard


class SafeJSONEncoder:
    """JSON encoder that replaces Infinity/NaN with null."""

    @staticmethod
    def clean(obj: Any) -> Any:
        if isinstance(obj, float):
            if math.isinf(obj) or math.isnan(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: SafeJSONEncoder.clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [SafeJSONEncoder.clean(v) for v in obj]
        return obj


settings = APISettings()

# ── Mode guard ──────────────────────────────────────────────────────
# Every entry point verifies the operating mode at startup.
guard(current_mode())

# ── Production fail-closed guard ────────────────────────────────────
# If running in production (debug=False) without an API key, refuse to
# start rather than silently exposing an open API.
if settings.is_production and not settings.auth_enabled:
    msg = (
        "FATAL: ORACLE_API_KEY is required in production mode. "
        "Set the environment variable or run with debug=true for development."
    )
    raise SystemExit(msg)

if not settings.api_key:
    import logging

    logging.warning(
        "No ORACLE_API_KEY configured — API authentication is disabled. "
        "Set ORACLE_API_KEY environment variable for production."
    )

app = FastAPI(
    title="Oracle Dashboard API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS (per sviluppo: Vite su porta 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers
@app.middleware("http")
async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Auth middleware:
# - If settings.auth_enabled → every /api/ request must carry a
#   matching X-API-Key header (no header → 401, wrong header → 401).
# - If api_key is empty (dev mode) → no key validation.
@app.middleware("http")
async def auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if (
        request.url.path.startswith("/api/")
        and request.url.path not in {"/api/health", "/api/ready"}
        and request.method != "OPTIONS"
        and settings.auth_enabled
    ):
        api_key = request.headers.get("X-API-Key", "")
        if api_key != settings.api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing X-API-Key"})

    response = await call_next(request)

    # Sanitize JSON responses (Infinity/NaN protection)
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            body = b""
            body_iterator = getattr(response, "body_iterator", None)
            if body_iterator is None:
                return response
            async for chunk in body_iterator:
                body += chunk
            import json

            data = json.loads(body)
            cleaned = SafeJSONEncoder.clean(data)
            return JSONResponse(content=cleaned, status_code=response.status_code)
        except Exception:
            pass

    return response


# Prometheus metrics endpoint (scraped by infra/docker/prometheus.yml)
@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint per Docker."""
    return {"status": "ok", "service": "oracle-api"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Return Prometheus-format metrics."""
    import time

    lines = [
        "# HELP oracle_api_requests_total Total API requests",
        "# TYPE oracle_api_requests_total counter",
        "oracle_api_requests_total 0",
        "# HELP oracle_api_up API is up and running",
        "# TYPE oracle_api_up gauge",
        "oracle_api_up 1.0",
        f"# EOF {time.time()}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n")


# Mount API routers
app.include_router(router)


# Serve static frontend in production (API routes take priority)
frontend_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def run() -> None:
    """Launch the API server with uvicorn (host/port from APISettings).

    Entry point that keeps the ``uvicorn`` dependency alive and gives the
    dashboard a real launch path:
        uv run --frozen python -m apps.api.main
    """
    import uvicorn

    uvicorn.run("apps.api.main:app", host=settings.host, port=settings.port, reload=settings.debug)


if __name__ == "__main__":
    run()
