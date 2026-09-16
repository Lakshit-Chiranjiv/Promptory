# ─────────────────────────────────────────────────────────────────
# Promptory — Dockerfile
#
# Multi-stage build:
#   Stage 1 (builder) — installs dependencies into an isolated layer
#   Stage 2 (runtime) — copies only what's needed; no build tools in final image
#
# Build:  docker build -t promptory .
# Run:    docker compose up          ← preferred (handles volume + env)
# ─────────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────────
# python:3.14-slim = official CPython 3.14, Debian-based, no extras
FROM python:3.14-slim AS builder

# Install uv — the fast Python package manager we use locally
# Using the official install script pinned to a stable release
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only the dependency manifests first.
# Docker caches each layer — if pyproject.toml hasn't changed,
# the expensive "install all deps" step is skipped on rebuild.
COPY pyproject.toml ./

# Install dependencies into /app/.venv inside the builder stage
# --no-dev        → skip any dev-only deps
# --frozen        → use the exact versions from uv.lock if present; fail if not satisfied
# UV_PROJECT_ENVIRONMENT → tells uv to install into a specific venv path
RUN uv venv /app/.venv && \
    UV_PROJECT_ENVIRONMENT=/app/.venv uv pip install --python /app/.venv/bin/python \
        fastapi uvicorn[standard] sqlalchemy jinja2 python-dotenv python-multipart pyyaml openai


# ── Stage 2: runtime image ────────────────────────────────────────
FROM python:3.14-slim AS runtime

# Non-root user for security — running as root inside a container is bad practice
RUN addgroup --system promptory && adduser --system --ingroup promptory promptory

WORKDIR /app

# Copy the installed virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source code
COPY app/       ./app/
COPY static/    ./static/

# Create the data directory (SQLite DB lives here).
# This will be overridden by the docker-compose volume mount,
# but needs to exist so the container can start without compose too.
RUN mkdir -p /app/data && chown -R promptory:promptory /app/data

# Switch to non-root user
USER promptory

# Tell Python to use the venv we copied in
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Port the server listens on inside the container
EXPOSE 8000

# Health check — Docker marks the container unhealthy if uvicorn stops responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

# Start the server.
# --host 0.0.0.0  → listen on all interfaces (required inside a container)
# --workers 1     → single worker is correct for SQLite (avoids write conflicts)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
