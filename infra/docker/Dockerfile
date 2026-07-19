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

# Copy project files and install deps
COPY pyproject.toml .python-version ./
RUN pip install --no-cache-dir -e ".[dev]" polars

# Copy source
COPY agents/ analytics/ apps/ core/ execution/ genetics/ market/ policy/ ./

# Non-root user from here on
USER oracle

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
