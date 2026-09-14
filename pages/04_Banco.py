import streamlit as st
from ui.common import require_login,topbar,brl
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_lancamentos,saldos
require_login("CONSULTAR");topbar("Banco","Movimentação das contas bancárias")
botao_ajuda("banco")
s=saldos();st.metric("Saldo Banco",brl(s.get("B",0)));rows=listar_lancamentos(origem_bc="B",limit=3000);st.dataframe(rows,width="stretch",hide_index=True)
