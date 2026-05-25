#!/usr/bin/env bash
# Container entrypoint: exec Streamlit on the platform-provided port.
set -euo pipefail

# Render (and similar PaaS) inject the listening port via $PORT. Streamlit
# reads STREAMLIT_SERVER_PORT — propagate the value so we don't need a
# platform-specific Dockerfile. Falls back to 7860 for local runs.
if [ -n "${PORT:-}" ]; then
    export STREAMLIT_SERVER_PORT="$PORT"
fi

# Hand off to Streamlit. exec replaces this shell so tini still owns PID 1.
exec streamlit run app/streamlit_app.py "$@"
