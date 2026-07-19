# Oracle Trading Platform — Docker image
# Build context: project root (../.. from infra/docker/)

FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY .python-version .

# Install runtime dependencies (Polars per API, plus dev/lint/test tools)
RUN pip install --no-cache-dir -e ".[dev]" polars

# Copy source
COPY agents/ agents/
COPY analytics/ analytics/
COPY apps/ apps/
COPY core/ core/
COPY execution/ execution/
COPY genetics/ genetics/
COPY market/ market/
COPY policy/ policy/

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
