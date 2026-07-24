from __future__ import annotations

import os

import streamlit as st

from .database import AuthDatabase
from .email_service import email_configured, notify_admin, send_recovery_code
from .security import generate_recovery_code
from .session import login_user


def render_first_admin(db: AuthDatabase) -> None:
    st.title("🔐 Primeiro acesso")
    st.caption("Crie o primeiro administrador do Extrator RREO Cloud.")
    with st.form("first_admin_form"):
        nome = st.text_input("Nome completo")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        confirmar = st.text_input("Confirmar senha", type="password")
        submitted = st.form_submit_button("Criar administrador", type="primary", use_container_width=True)
    if submitted:
        if senha != confirmar:
            st.error("As senhas não conferem.")
            return
        try:
            db.create_user(nome, email, senha, perfil="administrador")
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success("Administrador criado. Agora faça o login.")
        st.rerun()


def render_login(db: AuthDatabase) -> None:
    st.title("🔐 Entrar")
    st.caption("Acesso ao Extrator RREO Cloud")
    with st.form("login_form"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        user = db.authenticate(email, senha)
        if not user:
            st.error("E-mail ou senha inválidos, ou usuário bloqueado.")
        else:
            login_user(user)
            st.rerun()

    if st.button("Esqueci minha senha", use_container_width=True):
        st.session_state["show_recovery"] = True
    if st.session_state.get("show_recovery"):
        render_recovery_request(db)


def render_recovery_request(db: AuthDatabase) -> None:
    st.markdown("### Recuperar senha")
    email = st.text_input("E-mail cadastrado", key="recovery_request_email")
    if st.button("Enviar código", key="send_recovery_code", use_container_width=True):
        user = db.get_user_by_email(email)
        # Mensagem neutra para não expor quais e-mails estão cadastrados.
        if user and user.get("ativo"):
            code = generate_recovery_code()
            db.create_recovery(user["id"], code)
            try:
                send_recovery_code(user["nome"], user["email"], code)
                admin_email = (os.getenv("ADMIN_NOTIFICATION_EMAIL") or "").strip()
                if not admin_email:
                    admins = [u for u in db.list_users() if u["perfil"] == "administrador" and u["ativo"]]
                    admin_email = admins[0]["email"] if admins else ""
                if admin_email:
                    notify_admin(admin_email, user["nome"], user["email"])
                st.session_state["recovery_email"] = user["email"]
            except RuntimeError as exc:
                st.error(str(exc))
                return
            except Exception:
                st.error("Não foi possível enviar o e-mail agora. Verifique a configuração SMTP.")
                return
        st.success("Se o e-mail estiver cadastrado, o código será enviado.")

    recovery_email = st.session_state.get("recovery_email")
    if recovery_email:
        with st.form("confirm_recovery_form"):
            code = st.text_input("Código de 6 dígitos")
            new_password = st.text_input("Nova senha", type="password")
            confirm = st.text_input("Confirmar nova senha", type="password")
            reset = st.form_submit_button("Alterar senha", type="primary", use_container_width=True)
        if reset:
            if new_password != confirm:
                st.error("As senhas não conferem.")
                return
            user = db.verify_recovery(recovery_email, code)
            if not user:
                st.error("Código inválido ou expirado.")
                return
            try:
                db.update_password(user["id"], new_password)
            except ValueError as exc:
                st.error(str(exc))
                return
            st.session_state.pop("recovery_email", None)
            st.session_state.pop("show_recovery", None)
            st.success("Senha alterada. Faça o login.")


def render_force_password_change(db: AuthDatabase, user: dict) -> None:
    st.title("🔑 Trocar senha provisória")
    with st.form("force_password_change"):
        password = st.text_input("Nova senha", type="password")
        confirm = st.text_input("Confirmar nova senha", type="password")
        submitted = st.form_submit_button("Salvar nova senha", type="primary")
    if submitted:
        if password != confirm:
            st.error("As senhas não conferem.")
            return
        try:
            db.update_password(user["id"], password, force_change=False)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state["auth_user"]["trocar_senha"] = False
        st.success("Senha atualizada.")
        st.rerun()
