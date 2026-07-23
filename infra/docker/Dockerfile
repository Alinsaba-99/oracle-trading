# Oracle Trading Platform — Docker image
# Build context: project root (../.. from infra/docker/)

FROM python:3.12-slim

# ── Non-root user ────────────────────────────────────────────────────
RUN groupadd -r oracle && useradd -r -g oracle -d /app -s /sbin/nologin oracle

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the locked manifest and source required by the API/research dashboard.
COPY pyproject.toml uv.lock .python-version ./
COPY application/ application/
COPY agents/ agents/
COPY analytics/ analytics/
COPY apps/ apps/
COPY audit/ audit/
COPY core/ core/
COPY execution/ execution/
COPY genetics/ genetics/
COPY market/ market/
COPY orchestration/ orchestration/
COPY policy/ policy/
COPY research/ research/
COPY checkpoints/ checkpoints/
COPY experiments/ experiments/

RUN pip install --no-cache-dir ".[analytics,execution]" \
    && chown -R oracle:oracle /app

# Non-root user from here on
USER oracle

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
