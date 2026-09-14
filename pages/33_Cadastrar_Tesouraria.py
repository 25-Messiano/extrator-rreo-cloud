import streamlit as st

from ui.common import require_login, require_admin, topbar
from services.tenancy import criar_tesouraria_com_admin, obter_tesouraria, app_version

user = require_login("USUARIOS")
require_admin(user)
topbar("Cadastrar Nova Tesouraria", "Crie uma filial ligada ao mesmo código-base da Central")

st.success(
    f"Todas as unidades usam o mesmo TESOURARIA APLB {app_version()}. "
    "Ao atualizar o sistema na Central, a nova versão passa a valer automaticamente para todas as filiais."
)
st.info(
    "Cadastrar uma filial NÃO cria uma cópia do aplicativo e NÃO copia lançamentos financeiros. "
    "A nova unidade nasce vazia, com a mesma estrutura funcional, menus, relatórios e regras do sistema central."
)

with st.form("cadastro_filial_v24", clear_on_submit=False):
    st.subheader("Identificação da filial")
    c1, c2 = st.columns([1, 3])
    codigo = c1.text_input("Código da filial *", placeholder="Ex.: ARACI-01")
    nome = c2.text_input("Nome da tesouraria/filial *", placeholder="Ex.: Tesouraria APLB Araci")

    c3, c4, c5 = st.columns([2, 2, 1])
    cnpj = c3.text_input("CNPJ", placeholder="Opcional")
    cidade = c4.text_input("Município")
    uf = c5.text_input("UF", max_chars=2)

    st.subheader("Responsável e contato")
    c6, c7, c8 = st.columns(3)
    responsavel = c6.text_input("Responsável pela tesouraria")
    telefone = c7.text_input("Telefone")
    email = c8.text_input("E-mail de contato da filial")

    st.subheader("Acesso inicial do administrador da filial")
    st.caption("A nova filial já nasce no padrão V26: login por e-mail, sem conta admin/123.")
    a1, a2 = st.columns(2)
    admin_email = a1.text_input("E-mail de login do administrador *")
    admin_senha = a2.text_input("Senha inicial do administrador *", type="password", help="Mínimo de 10 caracteres, com letra e número.")
    admin_confirma = st.text_input("Confirmar senha inicial *", type="password")

    ambiente = st.selectbox(
        "Ambiente",
        ["PRODUCAO", "TESTE"],
        help="Use PRODUCAO para filiais oficiais. TESTE serve para simulações sem efeito na operação oficial.",
    )
    observacao = st.text_area("Observações")

    confirmar = st.checkbox(
        "Confirmo que esta filial deve usar o mesmo código-base e a mesma versão estrutural da Central."
    )
    salvar = st.form_submit_button("➕ Criar Tesouraria Filiada", type="primary", width="stretch")

if salvar:
    if not confirmar:
        st.error("Marque a confirmação antes de criar a filial.")
    elif admin_senha != admin_confirma:
        st.error("A confirmação da senha inicial não confere.")
    else:
        try:
            tid, uid = criar_tesouraria_com_admin(
                codigo, nome, admin_email, admin_senha, "FILIADA", ambiente, cnpj, cidade, uf,
                responsavel, telefone, email, observacao,
            )
            t = obter_tesouraria(tid)
            st.success(
                f"Tesouraria criada com sucesso: {t['nome']} (ID {tid}). "
                f"Ela já está vinculada ao código-base {t['versao_sistema']} e possui administrador por e-mail (usuário #{uid})."
            )
            st.caption(
                "A filial já pode entrar com o e-mail cadastrado. Outros usuários podem ser criados e vinculados em Usuários e Permissões."
            )
        except Exception as e:
            st.error(str(e))
