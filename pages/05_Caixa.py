import streamlit as st
from ui.common import require_login,topbar,brl
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_lancamentos,saldos
require_login("CONSULTAR");topbar("Caixa","Movimentação em espécie")
botao_ajuda("caixa")
s=saldos();st.metric("Saldo Caixa",brl(s.get("C",0)));rows=listar_lancamentos(origem_bc="C",limit=3000);st.dataframe(rows,width="stretch",hide_index=True)
