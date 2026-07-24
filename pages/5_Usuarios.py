from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.database import AuthDatabase
from auth.guards import require_admin
from auth.email_service import _send, email_configured

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")
admin = require_admin()
db = AuthDatabase()

st.title("👥 Administração de usuários")
st.caption("Crie operadores ou administradores e controle o acesso ao sistema.")

with st.expander("Cadastrar novo usuário", expanded=True):
    with st.form("create_user_form"):
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        perfil = st.selectbox("Perfil", ["operador", "administrador"])
        password = st.text_input("Senha provisória", type="password")
        send_email = st.checkbox("Enviar senha provisória por e-mail", value=False)
        submitted = st.form_submit_button("Criar usuário", type="primary")
    if submitted:
        try:
            db.create_user(nome, email, password, perfil=perfil, trocar_senha=True)
            if send_email:
                if not email_configured():
                    st.warning("Usuário criado, mas o envio de e-mail ainda não está configurado.")
                else:
                    _send(
                        email,
                        "Acesso ao Extrator RREO Cloud",
                        f"Olá, {nome}.\n\nSeu acesso foi criado.\nE-mail: {email}\n"
                        f"Senha provisória: {password}\n\nNo primeiro acesso, será necessário criar uma nova senha.",
                    )
                    st.success("Usuário criado e e-mail enviado.")
            else:
                st.success("Usuário criado. Ele deverá trocar a senha no primeiro acesso.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.warning("Usuário criado, mas não foi possível enviar o e-mail.")

users = db.list_users()
if users:
    table = pd.DataFrame(users)
    table["ativo"] = table["ativo"].map({1: "Sim", 0: "Não"})
    table["trocar_senha"] = table["trocar_senha"].map({1: "Sim", 0: "Não"})
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown("### Gerenciar acesso")
    labels = {f"{u['nome']} — {u['email']}": u for u in users}
    selected_label = st.selectbox("Usuário", list(labels))
    selected = labels[selected_label]
    c1, c2 = st.columns(2)
    with c1:
        if selected["ativo"]:
            if st.button("Bloquear usuário", use_container_width=True, disabled=selected["id"] == admin["id"]):
                db.set_active(selected["id"], False)
                st.success("Usuário bloqueado.")
                st.rerun()
        else:
            if st.button("Reativar usuário", use_container_width=True):
                db.set_active(selected["id"], True)
                st.success("Usuário reativado.")
                st.rerun()
    with c2:
        with st.form("temp_password_form"):
            temporary = st.text_input("Nova senha provisória", type="password")
            reset = st.form_submit_button("Definir senha provisória", use_container_width=True)
        if reset:
            try:
                db.update_password(selected["id"], temporary, force_change=True)
                st.success("Senha provisória definida. A troca será exigida no próximo acesso.")
            except ValueError as exc:
                st.error(str(exc))
