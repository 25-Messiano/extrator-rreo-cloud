import streamlit as st
from ui.common import require_login, require_admin, topbar
from services.tenancy import listar_tesourarias
user=require_login("CONFIGURAR"); require_admin(user)
topbar("Ambiente de Teste","Área isolada para testar lançamentos, códigos e relatórios sem alterar tesourarias oficiais")
t=st.session_state.get("tesouraria") or {}
if t.get("ambiente")!="TESTE":
    st.warning("A unidade ativa não é de TESTE. Selecione 'AMBIENTE DE TESTE' no menu lateral para trabalhar isoladamente.")
else:
    st.success("Ambiente isolado ativo. Os lançamentos criados aqui recebem o ID desta unidade de teste e não entram nos relatórios das tesourarias de produção.")
    st.page_link("pages/02_Lancamentos.py",label="➕ Criar lançamento de teste")
    st.page_link("pages/23_Relatorio_Movimento_Financeiro.py",label="📊 Conferir relatório de teste")
    st.caption("Códigos/Grupos DRE e Configurações são globais e ficam somente leitura/bloqueados neste ambiente para proteger a produção.")
