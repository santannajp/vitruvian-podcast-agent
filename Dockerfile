# syntax=docker/dockerfile:1.6
#
# Vitruvian Audio Agent — production container.
#
# Build:  docker build -t vitruvian-audio .
# Run:    docker run --rm -p 7860:7860 \
#             -e APP_PASSWORD="$(openssl rand -hex 24)" \
#             -e OPENAI_API_KEY="…" \
#             vitruvian-audio
#
# Production image does NOT include the NotebookLM provider (Playwright +
# Chromium). Use NotebookLM only in local dev — install it manually there
# with: pip install "notebooklm-py[browser]" && playwright install chromium.

# ---------------------------------------------------------------------------
# Stage 1 — builder: install Python deps into a virtualenv
# ---------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build-time system deps (compilers for any wheel that needs them).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    # Streamlit hardening
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Runtime system deps: ffmpeg (audio export), curl (healthcheck), tini (PID 1).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tini \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user. UID 1000 matches what HF Spaces expects.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy the virtualenv from the builder stage.
COPY --from=builder --chown=app:app /opt/venv /opt/venv

WORKDIR /home/app
USER app

# Copy application source last so code changes don't bust the heavy layers.
COPY --chown=app:app . /home/app/

# Ensure the entrypoint script is executable.
USER root
RUN chmod +x /home/app/entrypoint.sh
USER app

EXPOSE 7860

# Lightweight liveness probe — Streamlit's healthz endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:7860/_stcore/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/home/app/entrypoint.sh"]
