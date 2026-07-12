"""Oracle Dashboard API — FastAPI application."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from apps.api.config import APISettings
from apps.api.routers import router

settings = APISettings()

app = FastAPI(
    title="Oracle Dashboard API",
    version="0.1.0",
    docs_url="/api/docs",
)

# CORS (per sviluppo: Vite su porta 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Auth middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        api_key = request.headers.get("X-API-Key", "")
        if api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing X-API-Key header"},
            )
    return await call_next(request)


# Mount API routers
app.include_router(router)


# Serve static frontend in production (API routes take priority)
frontend_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
