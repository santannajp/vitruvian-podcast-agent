#!/usr/bin/env bash
# Container entrypoint: bootstrap secrets, then exec Streamlit.
#
# Streamlit lazily executes the user script per browser session, so any
# startup work that needs to happen unconditionally at boot (decoding the
# NotebookLM session, etc.) must run here instead.
set -euo pipefail

# Render (and similar PaaS) inject the listening port via $PORT. Streamlit
# reads STREAMLIT_SERVER_PORT — propagate the value so we don't need a
# platform-specific Dockerfile. Falls back to 7860 for local runs.
if [ -n "${PORT:-}" ]; then
    export STREAMLIT_SERVER_PORT="$PORT"
fi

# Materialize the NotebookLM storage state from NOTEBOOKLM_STORAGE_STATE_B64
# (no-op when the secret is empty). Runs as the same user that will own the
# Streamlit process, so file perms (0600) match.
python -c "from nlm.bootstrap import bootstrap_storage_state; bootstrap_storage_state()"

# Hand off to Streamlit. exec replaces this shell so tini still owns PID 1.
exec streamlit run app/streamlit_app.py "$@"
