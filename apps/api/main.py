"""Oracle Dashboard API — FastAPI application."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from apps.api.config import APISettings
from apps.api.routers import router

settings = APISettings()

# Log a startup warning if no API key is configured
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
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Auth middleware:
# - If settings.api_key is configured → every /api/ request must carry a
#   matching X-API-Key header (no header → 401, wrong header → 401).
# - If settings.api_key is empty (dev mode) → no key validation.
@app.middleware("http")
async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if (
        request.url.path.startswith("/api/")
        and request.method != "OPTIONS"
        and settings.api_key
    ):
        api_key = request.headers.get("X-API-Key", "")
        if api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing X-API-Key"},
            )

    return await call_next(request)


# Mount API routers
app.include_router(router)


# Serve static frontend in production (API routes take priority)
frontend_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
