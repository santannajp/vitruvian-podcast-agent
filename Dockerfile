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
# Target platform: Hugging Face Spaces (Docker SDK, port 7860).
# Includes Playwright + Chromium so the NotebookLM provider works when a
# storage_state.json is supplied; see README for the caveats.

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
    && /opt/venv/bin/pip install -r requirements.txt \
    && /opt/venv/bin/pip install "notebooklm-py[browser]"


# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # HF Spaces convention — keep the writable cache under the app dir.
    HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    PLAYWRIGHT_BROWSERS_PATH=/home/app/.cache/ms-playwright \
    # Streamlit hardening
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Runtime system deps: ffmpeg (audio export), curl (healthcheck), tini (PID 1),
# plus Chromium runtime libs needed by Playwright.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tini \
        ca-certificates \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user. UID 1000 matches what HF Spaces expects.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy the virtualenv from the builder stage.
COPY --from=builder --chown=app:app /opt/venv /opt/venv

WORKDIR /home/app

# Install Chromium for Playwright as the non-root user so the binary lands in
# the user-writable cache. --with-deps already covered above so we skip it
# here (the apt step above installed everything Playwright needs).
USER app
RUN python -m playwright install chromium

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
