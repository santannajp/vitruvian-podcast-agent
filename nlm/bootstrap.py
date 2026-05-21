"""
nlm/bootstrap.py — Restore a NotebookLM browser session at runtime from
the NOTEBOOKLM_STORAGE_STATE_B64 secret.

The notebooklm-py library expects a Playwright storage_state.json on disk
that was produced by the interactive `notebooklm login` flow. In headless
deployments (Hugging Face Spaces, Cloud Run, etc.) that flow can't run, so
operators encode the JSON locally and inject it as a base64 env var.

Idempotent: a non-empty file at the target path is never overwritten.
"""

import base64
import binascii
import json
import os
from pathlib import Path

import config


def bootstrap_storage_state() -> None:
    """
    Decode config.NOTEBOOKLM_STORAGE_STATE_B64 and write it to the path
    notebooklm-py expects. No-op when the secret is unset or the target
    file already exists.
    """
    encoded = config.NOTEBOOKLM_STORAGE_STATE_B64
    if not encoded:
        return

    target = _target_path()
    if target.exists() and target.stat().st_size > 0:
        return  # already bootstrapped (or operator placed a file by hand)

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        print(f"[NLM Bootstrap] Invalid base64 in NOTEBOOKLM_STORAGE_STATE_B64: {exc}")
        return

    # Light validation — make sure it parses as JSON with a cookies array.
    # We don't enforce a strict schema; notebooklm-py will surface a clearer
    # error if the contents are wrong.
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or "cookies" not in parsed:
            print("[NLM Bootstrap] Decoded payload does not look like a Playwright storage_state (no 'cookies' key).")
            return
    except json.JSONDecodeError as exc:
        print(f"[NLM Bootstrap] Decoded payload is not valid JSON: {exc}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    # Restrict permissions — session cookies are credentials.
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass

    print(f"[NLM Bootstrap] Restored NotebookLM session from secret to {target}")


def _target_path() -> Path:
    """
    Return the path where the storage state must live.

    Honors the NOTEBOOKLM_HOME env var the library reads, then writes to
    the profile-based layout used by notebooklm-py >= 0.4.
    """
    home_env = os.environ.get("NOTEBOOKLM_HOME")
    base_dir = (
        Path(home_env).expanduser().resolve()
        if home_env
        else Path.home() / ".notebooklm"
    )
    return base_dir / "profiles" / "default" / "storage_state.json"
