from __future__ import annotations

import streamlit as st

from .session import current_user, is_admin


def require_auth() -> dict:
    user = current_user()
    if not user:
        st.error("Faça login para acessar esta página.")
        st.page_link("app.py", label="Ir para o login", icon="🔐")
        st.stop()
    return user


def require_admin() -> dict:
    user = require_auth()
    if not is_admin():
        st.error("Esta área é exclusiva para administradores.")
        st.stop()
    return user
