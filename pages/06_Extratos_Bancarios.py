import streamlit as st
from datetime import date
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.importacao_extrato import ler_excel_extrato,ler_csv_extrato,sugerir_movimentos_pdf,criar_importacao
from services.ai_extrato import disponivel, extrair_pdf_com_ia, enriquecer_com_ia
from services.financeiro import listar_contas,listar_centros_custo

u=require_login("IMPORTAR");topbar("Extratos Bancários","Competência + conta → extração → IA → conferência obrigatória")
botao_ajuda("extratos")
hoje=date.today(); c1,c2=st.columns(2)
ano=c1.selectbox("Exercício",list(range(2026,2051)),index=max(0,min(24,hoje.year-2026)))
mes=c2.selectbox("Mês de competência",list(range(1,13)),index=hoje.month-1,format_func=lambda m:["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][m-1])
competencia=f"{ano:04d}-{mes:02d}"
contas=[x for x in listar_contas() if x["tipo"]=="BANCO" and x["ativo"]]; mapa={f"{x['nome']} | {x.get('banco') or ''} | Ag. {x.get('agencia') or '-'} | Cc. {x.get('conta') or '-'}":x["id"] for x in contas}
conta_label=st.selectbox("Conta bancária do extrato",list(mapa) if mapa else ["Cadastre uma conta bancária primeiro"])
centros=listar_centros_custo(); cmap={f"{x['codigo']} — {x['nome']}":x['id'] for x in centros}; cc=st.selectbox("Centro de custo padrão do lote (opcional)",["— Não informado —"]+list(cmap))
modo=st.radio("Processamento",["IA + validações (recomendado)","Somente regras locais"],horizontal=True,disabled=not disponivel())
up=st.file_uploader("Selecione o extrato",type=["xlsx","xls","csv","pdf"])
if up:
    data=up.getvalue();name=up.name.lower()
    try:
        if name.endswith((".xlsx",".xls")): mov=ler_excel_extrato(data)
        elif name.endswith(".csv"): mov=ler_csv_extrato(data)
        else:
            if modo.startswith("IA") and disponivel():
                with st.spinner("IA lendo o PDF/scan completo..."): mov=extrair_pdf_com_ia(data,up.name)
            else:
                mov=sugerir_movimentos_pdf(data)
        if modo.startswith("IA") and disponivel() and mov:
            with st.spinner("IA classificando Código APLB e pessoa/entidade..."): mov=enriquecer_com_ia(mov)
        fora=[x for x in mov if x["data"].strftime("%Y-%m")!=competencia]
        st.success(f"{len(mov)} movimento(s) identificado(s).")
        if fora: st.warning(f"ATENÇÃO: {len(fora)} movimento(s) têm data fora de {competencia}. Conferência obrigatória.")
        preview=[]
        for x in mov:
            preview.append({"data":x["data"],"histórico":x.get("historico",""),"valor":float(x["valor"]),"natureza":x["natureza"],"pessoa IA":x.get("favorecido",""),"código IA":x.get("codigo_ia",""),"confiança":x.get("confianca_ia",0),"origem":x.get("origem_classificacao",x.get("origem_extracao","LOCAL"))})
        st.dataframe(preview,width="stretch",hide_index=True)
        if not mov: st.warning("Nenhum movimento foi identificado. Não será criado lote vazio.")
        if st.button("Gerar arquivo de conferência",type="primary",disabled=(not mov or not mapa)):
            iid=criar_importacao(up.name,data,mov,u["id"],"B",competencia,mapa.get(conta_label),cmap.get(cc));st.success(f"Importação #{iid} criada. Revise em 08 Conferência antes de liberar.")
    except Exception as exc: st.error(f"Falha no processamento: {exc}")
st.info("A IA nunca lança diretamente. Duplicado exato é bloqueado pelo motor determinístico; coincidências, baixa confiança e divergências ficam para conferência humana.")
