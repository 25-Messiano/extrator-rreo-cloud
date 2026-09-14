import streamlit as st

from ui.common import require_login, topbar
from services.security import alterar_minha_senha, atualizar_meu_email

user = require_login()
topbar("Minha Conta", "E-mail de login, recuperação e alteração segura de senha")

st.info(
    "Sua senha atual nunca é exibida pelo sistema. Para trocar a senha, informe a senha atual e defina uma nova."
)

c1, c2, c3, c4 = st.columns(4)
c1.text_input("Nome", value=user.get("nome", ""), disabled=True)
c2.text_input("E-mail de login", value=user.get("email", ""), disabled=True)
c3.text_input("Perfil", value=user.get("perfil", ""), disabled=True)
c4.text_input("Identificador técnico", value=str(user.get("id", "")), disabled=True)

st.subheader("E-mail de login e recuperação")
st.caption("Este e-mail é usado para entrar no sistema e para recuperar a senha. Para alterá-lo, confirme sua senha atual.")
with st.form("alterar_meu_email_v26", clear_on_submit=True):
    novo_email=st.text_input("Novo e-mail")
    senha_email=st.text_input("Senha atual", type="password")
    salvar_email=st.form_submit_button("Atualizar e-mail")
if salvar_email:
    try:
        atualizar_meu_email(user["id"], senha_email, novo_email)
        st.success("E-mail de login atualizado. No próximo acesso, use o novo e-mail.")
        st.rerun()
    except Exception as e:
        st.error(str(e))

st.subheader("Alterar minha senha")
with st.form("alterar_minha_senha_v25", clear_on_submit=True):
    atual = st.text_input("Senha atual *", type="password")
    nova = st.text_input(
        "Nova senha *", type="password",
        help="Mínimo de 10 caracteres, contendo pelo menos uma letra e um número."
    )
    confirmar = st.text_input("Confirmar nova senha *", type="password")
    ok = st.form_submit_button("🔐 Alterar senha", type="primary")

if ok:
    if nova != confirmar:
        st.error("A confirmação da nova senha não confere.")
    elif not atual or not nova:
        st.error("Preencha a senha atual e a nova senha.")
    else:
        try:
            alterar_minha_senha(user["id"], atual, nova)
            st.session_state.clear()
            st.success("Senha alterada. Entre novamente com a nova senha.")
            st.switch_page("app.py")
        except Exception as e:
            st.error(str(e))

st.caption(
    "Se você esquecer a senha, use “Esqueci minha senha” na tela de acesso. Um Administrador também pode redefini-la em Usuários e Permissões. "
    "O Administrador não consegue visualizar sua senha atual."
)
