from __future__ import annotations

import streamlit as st

from auth.database import AuthDatabase
from auth.email_service import _send, email_configured
from auth.guards import require_admin

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")
admin = require_admin()
db = AuthDatabase()


@st.dialog("Novo usuário")
def new_user_dialog() -> None:
    st.caption("Informe os dados básicos para criar o acesso.")
    with st.form("create_user_dialog_form"):
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        password = st.text_input("Senha provisória", type="password")
        perfil = st.selectbox("Perfil", ["operador", "administrador"])
        send_email = st.checkbox("Enviar a senha provisória por e-mail", value=False)
        submitted = st.form_submit_button(
            "Criar usuário", type="primary", use_container_width=True
        )

    if submitted:
        try:
            db.create_user(
                nome=nome,
                email=email,
                password=password,
                perfil=perfil,
                trocar_senha=False,
            )
            if send_email:
                if email_configured():
                    _send(
                        email,
                        "Acesso ao Extrator RREO Cloud",
                        f"Olá, {nome}.\n\nSeu acesso foi criado.\n"
                        f"E-mail: {email}\nSenha provisória: {password}\n\n"
                        "No primeiro acesso, será necessário criar uma nova senha.",
                    )
                    st.success("Usuário criado e e-mail enviado.")
                else:
                    st.warning(
                        "Usuário criado, mas o envio de e-mail ainda não está configurado."
                    )
            else:
                st.success("Usuário criado com sucesso.")
            st.session_state.pop("selected_user_id", None)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Não foi possível criar o usuário: {exc}")


@st.dialog("Acesso do usuário")
def manage_user_dialog(user: dict) -> None:
    st.markdown(f"### {user['nome']}")
    st.caption("Altere somente o acesso deste usuário.")

    st.text_input("E-mail", value=user["email"], disabled=True)

    with st.form(f"password_form_{user['id']}"):
        temporary = st.text_input("Nova senha provisória", type="password")
        save_password = st.form_submit_button(
            "Salvar nova senha", type="primary", use_container_width=True
        )

    if save_password:
        try:
            db.update_password(user["id"], temporary, force_change=False)
            st.success("Nova senha salva com sucesso.")
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    is_self = user["id"] == admin["id"]

    if user["ativo"]:
        if st.button(
            "Bloquear usuário",
            use_container_width=True,
            disabled=is_self,
            key=f"block_{user['id']}",
        ):
            db.set_active(user["id"], False)
            st.success("Usuário bloqueado.")
            st.rerun()
        if is_self:
            st.caption("O administrador conectado não pode bloquear o próprio acesso.")
    else:
        if st.button(
            "Reativar usuário",
            type="primary",
            use_container_width=True,
            key=f"activate_{user['id']}",
        ):
            db.set_active(user["id"], True)
            st.success("Usuário reativado.")
            st.rerun()


st.title("👥 Administração de usuários")
st.caption("Clique no e-mail ou em Abrir para gerenciar o acesso.")

left, right = st.columns([5, 1])
with right:
    if st.button("➕ Novo usuário", type="primary", use_container_width=True):
        new_user_dialog()

users = db.list_users()

if not users:
    st.info("Nenhum usuário cadastrado.")
else:
    st.markdown(
        """
        <style>
        .user-header{font-size:11px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.05em;padding:0 8px 6px}
        .user-row{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:8px 10px;margin-bottom:8px}
        .user-name{font-weight:800;color:#17233d;padding-top:8px}
        .user-meta{font-size:12px;color:#64748b;padding-top:10px}
        .status-active{display:inline-block;background:#eaf8ef;color:#16833b;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:800;margin-top:6px}
        .status-blocked{display:inline-block;background:#fff0f0;color:#c62828;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:800;margin-top:6px}
        </style>
        """,
        unsafe_allow_html=True,
    )

    h1, h2, h3, h4, h5 = st.columns([2.2, 3.5, 1.4, 1.2, 1])
    h1.markdown('<div class="user-header">Nome</div>', unsafe_allow_html=True)
    h2.markdown('<div class="user-header">E-mail</div>', unsafe_allow_html=True)
    h3.markdown('<div class="user-header">Perfil</div>', unsafe_allow_html=True)
    h4.markdown('<div class="user-header">Status</div>', unsafe_allow_html=True)
    h5.markdown('<div class="user-header">Ação</div>', unsafe_allow_html=True)

    for user in users:
        c1, c2, c3, c4, c5 = st.columns([2.2, 3.5, 1.4, 1.2, 1])
        with c1:
            st.markdown(
                f'<div class="user-name">{user["nome"]}</div>',
                unsafe_allow_html=True,
            )
        with c2:
            # O próprio e-mail funciona como botão para abrir o usuário.
            if st.button(
                user["email"],
                key=f"email_{user['id']}",
                use_container_width=True,
            ):
                manage_user_dialog(user)
        with c3:
            st.markdown(
                f'<div class="user-meta">{str(user["perfil"]).title()}</div>',
                unsafe_allow_html=True,
            )
        with c4:
            status_class = "status-active" if user["ativo"] else "status-blocked"
            status_text = "Ativo" if user["ativo"] else "Bloqueado"
            st.markdown(
                f'<span class="{status_class}">{status_text}</span>',
                unsafe_allow_html=True,
            )
        with c5:
            if st.button(
                "Abrir",
                key=f"open_{user['id']}",
                type="primary",
                use_container_width=True,
            ):
                manage_user_dialog(user)
