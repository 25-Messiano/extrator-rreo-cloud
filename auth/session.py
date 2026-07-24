from __future__ import annotations

import streamlit as st

SESSION_KEY = "auth_user"


def login_user(user: dict) -> None:
    st.session_state[SESSION_KEY] = {
        "id": user["id"],
        "nome": user["nome"],
        "email": user["email"],
        "perfil": user["perfil"],
        "trocar_senha": bool(user.get("trocar_senha", 0)),
    }


def logout_user() -> None:
    st.session_state.pop(SESSION_KEY, None)
    st.session_state.pop("recovery_email", None)


def current_user() -> dict | None:
    return st.session_state.get(SESSION_KEY)


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("perfil") == "administrador")
