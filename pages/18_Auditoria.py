import streamlit as st
import pandas as pd
from datetime import date,timedelta
from ui.common import require_login,topbar,brl
from ui.help_modulos import botao_ajuda
from services.administracao import listar_auditoria_filtrada
from services.financeiro import listar_lancamentos
from services.exportacao import dataframe_excel_bytes,json_bytes

u=require_login("AUDITORIA")
topbar("Auditoria","Histórico integral, inclusive registros cancelados que não aparecem na operação normal")
botao_ajuda("auditoria")

tab1,tab2=st.tabs(["Histórico de ações","Lançamentos cancelados"])
with tab1:
    c1,c2,c3,c4=st.columns(4)
    inicio=c1.date_input("Início",date.today()-timedelta(days=30))
    fim=c2.date_input("Fim",date.today())
    acao=c3.text_input("Ação contém")
    ent=c4.text_input("Entidade contém")
    rows=listar_auditoria_filtrada(inicio,fim,limit=5000)
    if acao: rows=[r for r in rows if acao.upper() in r["acao"].upper()]
    if ent: rows=[r for r in rows if ent.upper() in r["entidade"].upper()]
    df=pd.DataFrame(rows)
    st.dataframe(df,width="stretch",hide_index=True)
    if not df.empty:
        a,b=st.columns(2)
        a.download_button("Excel",dataframe_excel_bytes(df,"Auditoria"),"auditoria.xlsx")
        b.download_button("JSON",json_bytes(rows),"auditoria.json",mime="application/json")

with tab2:
    st.caption("Estes registros são invisíveis em Lançamentos, Banco, Caixa, Pesquisa, DRE, Relatórios e Conciliação. Permanecem somente para rastreabilidade.")
    cancelados=listar_lancamentos(status="CANCELADO",limit=10000,include_cancelados=True)
    if not cancelados:
        st.info("Nenhum lançamento cancelado.")
    else:
        tabela=[]
        for r in cancelados:
            tabela.append({
                "ID":r["id"],"Data":r["data"],"Código":r["codigo"],"B/C":r["B/C"],"Natureza":r["natureza"],
                "Especificação":r["especificacao"],"Favorecido":r["favorecido"],"Documento":r["documento"],
                "Valor":brl(r["valor"]),"Conta":r["conta"],"Origem":r["origem"],"Criado em":r["criado_em"],
            })
        st.dataframe(pd.DataFrame(tabela),width="stretch",hide_index=True)
