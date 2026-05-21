"""
app/auth.py — Lightweight password gate for the Streamlit UI.

Activated when config.APP_PASSWORD is non-empty (typically set as a Hugging
Face Spaces secret in production). When empty, the app stays open — local
development is unaffected.

Uses hmac.compare_digest to avoid timing-based password disclosure.
"""

import hmac

import streamlit as st

import config


_SESSION_KEY = "_auth_passed"
_ATTEMPT_KEY = "_auth_attempts"
_MAX_ATTEMPTS = 5


def require_password() -> None:
    """
    Block rendering of the rest of the app until the user enters the correct
    password. Does nothing when APP_PASSWORD is not configured.
    """
    expected = config.APP_PASSWORD
    if not expected:
        return  # auth disabled

    if st.session_state.get(_SESSION_KEY):
        return

    attempts = st.session_state.get(_ATTEMPT_KEY, 0)
    if attempts >= _MAX_ATTEMPTS:
        st.error(
            "🚫 Muitas tentativas falhadas. Recarregue a página e tente novamente."
        )
        st.stop()

    st.title("🔒 Acesso restrito")
    st.caption("Esse deploy está protegido por senha.")

    with st.form("auth_form"):
        entered = st.text_input("Senha", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.session_state[_SESSION_KEY] = True
            st.session_state[_ATTEMPT_KEY] = 0
            st.rerun()
        else:
            st.session_state[_ATTEMPT_KEY] = attempts + 1
            remaining = _MAX_ATTEMPTS - st.session_state[_ATTEMPT_KEY]
            st.error(
                f"Senha incorreta. Tentativas restantes: {max(remaining, 0)}."
            )

    st.stop()
