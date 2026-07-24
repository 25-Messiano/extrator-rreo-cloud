from __future__ import annotations

import os
import time

import streamlit as st

from .database import AuthDatabase
from .email_service import notify_admin, send_recovery_code
from .security import generate_recovery_code, password_requirements
from .session import login_user


def _auth_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="auth-brand">
            <div class="auth-brand-icon">{icon}</div>
            <div>
                <div class="auth-brand-name">Extrator RREO Cloud</div>
                <div class="auth-brand-caption">{subtitle}</div>
            </div>
        </div>
        <div class="auth-dialog-title">{title}</div>
        """,
        unsafe_allow_html=True,
    )


def _password_checklist(password: str, confirmation: str) -> dict[str, bool]:
    checks = password_requirements(password)
    checks["As senhas coincidem"] = bool(password) and password == confirmation

    items = "".join(
        f'<div class="password-rule {"ok" if passed else "pending"}">'
        f'<span>{"✓" if passed else "○"}</span>{label}</div>'
        for label, passed in checks.items()
    )
    st.markdown(
        f'<div class="password-box"><div class="password-box-title">Requisitos da senha</div>{items}</div>',
        unsafe_allow_html=True,
    )
    return checks


@st.dialog("Primeiro acesso", width="small")
def _first_admin_dialog(db: AuthDatabase) -> None:
    st.markdown(
        """
        <div class="first-access-head">
            <div class="first-access-lock">▣</div>
            <div class="first-access-title">Primeiro acesso</div>
            <div class="first-access-line"></div>
        </div>
        <div class="first-access-welcome">
            <strong>Bem-vindo ao Extrator RREO Cloud.</strong><br>
            Vamos criar a primeira conta de administrador.<br>
            Esta etapa será executada apenas uma vez.
        </div>
        """,
        unsafe_allow_html=True,
    )

    nome = st.text_input(
        "Nome completo",
        key="first_admin_name",
        placeholder="Ex.: João da Silva",
    )
    email = st.text_input(
        "E-mail",
        key="first_admin_email",
        placeholder="Ex.: joao.silva@email.com",
    )
    senha = st.text_input(
        "Senha",
        type="password",
        key="first_admin_password",
        placeholder="Ex.: MinhaSenha123",
    )
    confirmar = st.text_input(
        "Confirmar senha",
        type="password",
        key="first_admin_confirm",
        placeholder="Digite novamente a senha",
    )
    checks = _password_checklist(senha, confirmar)

    submitted = st.button(
        "Criar administrador",
        type="primary",
        use_container_width=True,
        key="create_first_admin",
        disabled=not all(checks.values()),
    )
    st.markdown(
        '<div class="auth-version">Extrator RREO Cloud &nbsp;•&nbsp; versão 1.2.2</div>'
        '<div class="setup-required-note">ⓘ &nbsp;É necessário concluir a configuração do administrador para utilizar o sistema.</div>',
        unsafe_allow_html=True,
    )

    if submitted:
        try:
            db.create_user(nome, email, senha, perfil="administrador")
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success("Administrador criado com sucesso! Abrindo a tela de login...")
        time.sleep(1.2)
        st.rerun()


def render_first_admin(db: AuthDatabase) -> None:
    _first_admin_dialog(db)


@st.dialog("Acesso ao sistema", width="large")
def _login_dialog(db: AuthDatabase) -> None:
    _auth_header("🔑", "Entrar", "Acesso seguro ao painel")

    if st.session_state.get("show_recovery"):
        render_recovery_request(db)
        if st.button("← Voltar ao login", use_container_width=True, key="back_to_login"):
            st.session_state.pop("show_recovery", None)
            st.session_state.pop("recovery_email", None)
            st.rerun()
        return

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

    if st.button("Esqueci minha senha", use_container_width=True, key="open_recovery"):
        st.session_state["show_recovery"] = True
        st.rerun()

    st.markdown('<div class="auth-version">Extrator RREO Cloud • versão 1.2.1</div>', unsafe_allow_html=True)


def render_login(db: AuthDatabase) -> None:
    _login_dialog(db)


def render_recovery_request(db: AuthDatabase) -> None:
    st.markdown('<div class="auth-dialog-title">Recuperar senha</div>', unsafe_allow_html=True)
    st.caption("Informe o e-mail cadastrado para receber um código de 6 dígitos.")
    email = st.text_input("E-mail cadastrado", key="recovery_request_email")
    if st.button("Enviar código", key="send_recovery_code", type="primary", use_container_width=True):
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
        code = st.text_input("Código de 6 dígitos", key="recovery_code")
        new_password = st.text_input("Nova senha", type="password", key="recovery_new_password")
        confirm = st.text_input("Confirmar nova senha", type="password", key="recovery_confirm_password")
        checks = _password_checklist(new_password, confirm)
        reset = st.button(
            "Alterar senha",
            type="primary",
            use_container_width=True,
            key="reset_password",
            disabled=not all(checks.values()) or len(code.strip()) != 6,
        )
        if reset:
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
            time.sleep(1.0)
            st.rerun()


@st.dialog("Troca de senha", width="large")
def _force_password_dialog(db: AuthDatabase, user: dict) -> None:
    _auth_header("🔑", "Trocar senha provisória", "Defina sua senha definitiva")
    password = st.text_input("Nova senha", type="password", key="force_new_password")
    confirm = st.text_input("Confirmar nova senha", type="password", key="force_confirm_password")
    checks = _password_checklist(password, confirm)
    submitted = st.button(
        "Salvar nova senha",
        type="primary",
        use_container_width=True,
        key="save_forced_password",
        disabled=not all(checks.values()),
    )
    if submitted:
        try:
            db.update_password(user["id"], password, force_change=False)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state["auth_user"]["trocar_senha"] = False
        st.success("Senha atualizada.")
        time.sleep(0.8)
        st.rerun()


def render_force_password_change(db: AuthDatabase, user: dict) -> None:
    _force_password_dialog(db, user)
