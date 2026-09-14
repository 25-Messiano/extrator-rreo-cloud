import pandas as pd
import streamlit as st
from sqlalchemy import select

from ui.common import require_login, topbar
from services.tenancy import (
    listar_tesourarias, vincular_usuario, atualizar_tesouraria,
    definir_tesouraria_ativa, app_version,
)
from services.prestacoes import listar_prestacoes
from database.db import session_scope
from models.entities import Usuario, UsuarioTesouraria

user = require_login("AUDITORIA" if st.session_state.get("user", {}).get("perfil") == "AUDITORIA" else "CONSULTAR")
topbar("Central de Auditoria", "Central única para todas as tesourarias filiadas")

rows = listar_tesourarias(None, True)
prest = listar_prestacoes()
prod = [x for x in rows if x["ambiente"] == "PRODUCAO"]
filiais = [x for x in prod if x["tipo"] == "FILIADA"]

st.info(
    f"Arquitetura centralizada — código-base {app_version()}. Todas as filiais usam esta mesma versão. "
    "Atualizações estruturais do aplicativo são publicadas uma única vez e passam a valer para todas as unidades."
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Filiais", len(filiais))
c2.metric("Filiais ativas", len([x for x in filiais if x["ativa"]]))
c3.metric("Versão compartilhada", app_version())
c4.metric("Prestações recebidas", len(prest))
c5.metric("Pendentes", len([x for x in prest if x["status"] in ("ENVIADA", "EM_AUDITORIA")]))

if user.get("perfil") == "ADMINISTRADOR":
    st.page_link("pages/33_Cadastrar_Tesouraria.py", label="➕ CADASTRAR NOVA TESOURARIA", icon="🏛️")

st.subheader("Tesourarias Filiadas")
if filiais:
    tabela = []
    for x in filiais:
        tabela.append({
            "Código": x["codigo"], "Tesouraria": x["nome"], "Cidade": x["cidade"], "UF": x["uf"],
            "Responsável": x["responsavel"], "Ambiente": x["ambiente"], "Ativa": x["ativa"],
            "Versão": x["versao_sistema"],
        })
    st.dataframe(pd.DataFrame(tabela), width="stretch", hide_index=True)
else:
    st.warning("Nenhuma tesouraria filiada de produção foi cadastrada ainda.")

with st.expander("🧪 Ambientes de teste"):
    teste = [x for x in rows if x["ambiente"] == "TESTE"]
    st.dataframe(pd.DataFrame(teste), width="stretch", hide_index=True) if teste else st.caption("Nenhum ambiente de teste.")

if user.get("perfil") == "ADMINISTRADOR":
    st.divider()
    tab1, tab2, tab3 = st.tabs(["✏️ Editar filial", "👥 Vincular usuários", "🔒 Ativar / Inativar"])

    editaveis = [x for x in rows if x["tipo"] == "FILIADA" and x["codigo"] != "TESTE"]
    with tab1:
        if not editaveis:
            st.caption("Cadastre uma filial para habilitar a edição.")
        else:
            x = st.selectbox("Filial para editar", editaveis, format_func=lambda r: f"{r['codigo']} — {r['nome']}", key="edit_filial")
            with st.form("editar_filial_v24"):
                nome = st.text_input("Nome", value=x["nome"])
                c1, c2, c3 = st.columns([2, 2, 1])
                cnpj = c1.text_input("CNPJ", value=x["cnpj"])
                cidade = c2.text_input("Cidade", value=x["cidade"])
                uf = c3.text_input("UF", value=x["uf"], max_chars=2)
                c4, c5, c6 = st.columns(3)
                responsavel = c4.text_input("Responsável", value=x["responsavel"])
                telefone = c5.text_input("Telefone", value=x["telefone"])
                email = c6.text_input("E-mail", value=x["email"])
                observacao = st.text_area("Observação", value=x["observacao"])
                ok = st.form_submit_button("Salvar alterações", type="primary")
            if ok:
                try:
                    atualizar_tesouraria(x["id"], nome=nome, cnpj=cnpj, cidade=cidade, uf=uf,
                                         responsavel=responsavel, telefone=telefone, email=email,
                                         observacao=observacao)
                    st.success("Cadastro atualizado. A estrutura do aplicativo continua compartilhada com todas as unidades.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        with session_scope() as s:
            users = [{"id": u.id, "nome": u.nome, "login": u.login} for u in s.scalars(
                select(Usuario).where(Usuario.ativo.is_(True)).order_by(Usuario.nome)
            ).all()]
        destinos = [x for x in rows if x["ativa"] and x["tipo"] != "CENTRAL"]
        if users and destinos:
            u = st.selectbox("Usuário", users, format_func=lambda x: f"{x['nome']} ({x['login']})", key="vinc_u")
            t = st.selectbox("Tesouraria", destinos, format_func=lambda x: f"{x['codigo']} — {x['nome']}", key="vinc_t")
            papel = st.selectbox("Papel na unidade", ["OPERADOR", "CONFERENTE", "GESTOR", "AUDITOR", "ADMIN"])
            if st.button("Vincular usuário à tesouraria", type="primary"):
                vincular_usuario(u["id"], t["id"], papel)
                st.success("Vínculo salvo. O usuário verá somente as unidades às quais estiver autorizado.")

        with session_scope() as s:
            vincs = s.execute(
                select(Usuario.nome, Usuario.login, UsuarioTesouraria.papel, UsuarioTesouraria.ativo,
                       UsuarioTesouraria.tesouraria_id)
                .join(UsuarioTesouraria, UsuarioTesouraria.usuario_id == Usuario.id)
            ).all()
        nomes = {x["id"]: x["nome"] for x in rows}
        if vincs:
            st.dataframe(pd.DataFrame([
                {"Usuário": a, "Login": b, "Tesouraria": nomes.get(e, e), "Papel": c, "Ativo": d}
                for a, b, c, d, e in vincs
            ]), width="stretch", hide_index=True)

    with tab3:
        if not editaveis:
            st.caption("Nenhuma filial disponível.")
        else:
            x = st.selectbox("Filial", editaveis, format_func=lambda r: f"{r['codigo']} — {r['nome']}", key="status_filial")
            novo_status = st.radio("Situação", ["ATIVA", "INATIVA"], index=0 if x["ativa"] else 1, horizontal=True)
            if st.button("Salvar situação"):
                try:
                    definir_tesouraria_ativa(x["id"], novo_status == "ATIVA")
                    st.success("Situação atualizada.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
