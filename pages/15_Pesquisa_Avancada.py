import streamlit as st
import pandas as pd
from datetime import date,timedelta
from ui.common import require_login,topbar,code_options
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_codigos,listar_lancamentos
from services.exportacao import dataframe_excel_bytes

require_login("CONSULTAR");topbar("Pesquisa Avançada","Filtros combináveis sobre a base oficial")
botao_ajuda("pesquisa")
cod=code_options(listar_codigos());c1,c2,c3,c4=st.columns(4);inicio=c1.date_input("De",date.today()-timedelta(days=365));fim=c2.date_input("Até",date.today());bc=c3.selectbox("B/C",["Todos","B","C"]);nat=c4.selectbox("Natureza",["Todas","ENTRADA","SAIDA"])
c5,c6,c7,c8=st.columns(4);ck=c5.selectbox("Código",["Todos"]+list(cod));status=c6.selectbox("Status",["Todos","RASCUNHO","EM_CONFERENCIA","APROVADO","CONCILIADO","FECHADO"]);vmin=c7.number_input("Valor mínimo",min_value=0.0,step=10.0);vmax=c8.number_input("Valor máximo (0 = sem limite)",min_value=0.0,step=10.0)
texto=st.text_input("Pesquisar em código, descrição, especificação, favorecido ou documento")
rows=listar_lancamentos(inicio,fim,None if bc=="Todos" else bc,None if nat=="Todas" else nat,cod.get(ck),None if status=="Todos" else status,texto or None,vmin if vmin>0 else None,vmax if vmax>0 else None,10000)
fav=st.text_input("Favorecido contém",key="pesq_fav")
conta=st.text_input("Conta/Banco/Caixa contém",key="pesq_conta")
if fav: rows=[r for r in rows if fav.casefold() in (r.get("favorecido") or "").casefold()]
if conta: rows=[r for r in rows if conta.casefold() in (r.get("conta") or "").casefold()]
st.caption(f"{len(rows)} resultado(s)");st.dataframe(rows,width="stretch",hide_index=True)
if rows:
    st.download_button("📊 Exportar resultado em Excel",dataframe_excel_bytes(pd.DataFrame(rows),"Pesquisa"),file_name="pesquisa_avancada.xlsx")
