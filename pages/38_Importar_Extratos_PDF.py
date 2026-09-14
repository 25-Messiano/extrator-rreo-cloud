import pandas as pd
import streamlit as st
from datetime import date

from ui.common import require_login, topbar
from services.importacao_extrato import sugerir_movimentos_pdf, criar_importacao
from services.ai_extrato import disponivel, extrair_pdf_com_ia, enriquecer_com_ia
from services.financeiro import listar_contas, listar_centros_custo

u = require_login("IMPORTAR")
topbar("Importar Extratos por PDF", "Vários PDFs bancários → leitura → prévia → conferência → conciliação")

hoje=date.today(); c1,c2=st.columns(2)
ano=c1.selectbox("Exercício", list(range(2026,2051)), index=max(0,min(24,hoje.year-2026)))
mes=c2.selectbox("Mês de competência", list(range(1,13)), index=hoje.month-1)
competencia=f"{ano:04d}-{mes:02d}"
contas=[x for x in listar_contas() if x["tipo"]=="BANCO" and x["ativo"]]
mapa={f"{x['nome']} | {x.get('banco') or ''} | Ag. {x.get('agencia') or '-'} | Cc. {x.get('conta') or '-'}":x["id"] for x in contas}
conta_label=st.selectbox("Conta bancária dos extratos", list(mapa) if mapa else ["Cadastre uma conta bancária primeiro"])
centros=listar_centros_custo(); cmap={f"{x['codigo']} — {x['nome']}":x['id'] for x in centros}; cc=st.selectbox("Centro de custo padrão (opcional)",["— Não informado —"]+list(cmap))
modo=st.radio("Processamento",["IA + validações (recomendado)","Somente regras locais"],horizontal=True,disabled=not disponivel())
ups=st.file_uploader("Selecione um ou vários extratos em PDF", type=["pdf"], accept_multiple_files=True)

lotes=[]
if ups:
    for up in ups:
        data=up.getvalue()
        try:
            if modo.startswith("IA") and disponivel():
                mov=extrair_pdf_com_ia(data,up.name)
                if mov: mov=enriquecer_com_ia(mov)
            else:
                mov=sugerir_movimentos_pdf(data)
            lotes.append((up,data,mov,None))
        except Exception as exc:
            lotes.append((up,data,[],str(exc)))
    resumo=[]
    for up,data,mov,erro in lotes:
        fora=sum(1 for x in mov if x["data"].strftime("%Y-%m")!=competencia)
        resumo.append({"Arquivo":up.name,"Movimentos":len(mov),"Fora da competência":fora,"Situação":erro or "PRONTO"})
    st.dataframe(pd.DataFrame(resumo),width="stretch",hide_index=True)
    for up,data,mov,erro in lotes:
        with st.expander(f"{up.name} — {len(mov)} movimento(s)"):
            if erro: st.error(erro); continue
            st.dataframe(pd.DataFrame([{"Data":x["data"],"Histórico":x.get("historico",""),"Natureza":x["natureza"],"Valor":float(x["valor"])} for x in mov]),width="stretch",hide_index=True)
    confirmar=st.checkbox("Conferi a prévia e quero gerar os lotes de conferência.")
    if st.button("Gerar lotes de extratos",type="primary",disabled=(not confirmar or not mapa)):
        criados=[];falhas=[]
        for up,data,mov,erro in lotes:
            if erro or not mov:
                falhas.append(f"{up.name}: {erro or 'nenhum movimento identificado'}");continue
            try:
                iid=criar_importacao(up.name,data,mov,u["id"],"B",competencia,mapa.get(conta_label),cmap.get(cc));criados.append((up.name,iid))
            except Exception as exc:falhas.append(f"{up.name}: {exc}")
        if criados: st.success("Lotes criados: "+", ".join(f"{n} → #{i}" for n,i in criados)+". Revise em Conferência.")
        for f in falhas: st.warning(f)

st.info("Extratos continuam passando pela Conferência e depois pela Conciliação. Nenhum PDF gera lançamento oficial automaticamente.")
