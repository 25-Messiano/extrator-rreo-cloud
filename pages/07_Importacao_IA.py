import streamlit as st
import pandas as pd
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.ai_extrato import disponivel, MODEL
from services.importacao_extrato import listar_importacoes,listar_itens,reprocessar_importacao_com_ia

u=require_login("IMPORTAR")
topbar("Importação Inteligente / IA","OpenAI + regras locais, sempre sujeita à conferência humana")
botao_ajuda("ia")

if disponivel():
    st.success(f"IA REAL ATIVA — modelo {MODEL}. A chave está protegida no ambiente do Render.")
else:
    st.error("OPENAI_API_KEY não configurada. A importação continua disponível apenas com regras locais.")

st.markdown("""
### Motor V13
A IA pode **ler PDF textual ou escaneado**, reconhecer movimentos, sugerir pessoa/entidade, Código APLB e especificação e atribuir confiança. Excel/CSV continuam com parser determinístico e podem receber classificação por IA.

**Barreiras de segurança:** a IA não altera a base oficial, não decide duplicidade e não libera lançamentos. Data/valor/natureza extraídos são preservados; duplicidade continua sendo validada pelo motor determinístico; todo item passa pelo **Arquivo de Conferência** antes da liberação.

**Fluxo:** `06 Extrato → IA V13 → regras/antiduplicidade → 08 Conferência → aprovação humana → base oficial → 09 Conciliação`.
""")

st.divider()
st.subheader("Reprocessar extratos já existentes com IA")
st.caption("Útil para lotes de janeiro, fevereiro e março importados antes da V12. Apenas itens ainda pendentes/corrigíveis são reclassificados; decisões humanas já tomadas são preservadas.")

imps=[x for x in listar_importacoes() if x.get("competencia") and x.get("conta_id")]
if not imps:
    st.info("Não há lotes válidos para reprocessamento.")
else:
    resumo=[]
    for x in imps:
        itens=listar_itens(x["id"])
        resumo.append({
            "ID":x["id"],"Competência":x["competencia"],"Arquivo":x["arquivo"],"Status":x["status"],
            "Itens":len(itens),"Classificados por IA":sum(1 for i in itens if i.get("origem_classificacao")=="OPENAI"),
            "Pendentes":sum(1 for i in itens if i.get("status") in ("PENDENTE","CONFERIR_DUPLICIDADE","DUPLICADO_BLOQUEADO","CORRIGIR")),
        })
    st.dataframe(pd.DataFrame(resumo),width="stretch",hide_index=True)
    opts={f"#{x['id']} | {x['competencia']} | {x['arquivo']} | {x['status']}":x["id"] for x in imps}
    iid=opts[st.selectbox("Lote para reprocessar",list(opts))]
    confirmar=st.checkbox("Confirmo que desejo reclassificar com IA apenas os itens ainda não decididos por humano")
    if st.button("Reprocessar lote com IA",type="primary",disabled=(not disponivel() or not confirmar)):
        try:
            with st.spinner("IA reclassificando os itens pendentes. Nenhum lançamento será criado automaticamente..."):
                r=reprocessar_importacao_com_ia(iid,u["id"])
            st.success(f"Reprocessamento concluído: {r['processados']} item(ns) classificados; {r['preservados']} decisão(ões) preservada(s).")
            if r["baixa_confianca"]: st.warning(f"{r['baixa_confianca']} item(ns) ficaram com confiança abaixo de 80% e exigem atenção na Conferência.")
            if r["duplicados"]: st.error(f"{r['duplicados']} duplicado(s) exato(s) foram bloqueados pelo motor determinístico.")
            if r["possiveis"]: st.warning(f"{r['possiveis']} possível(is) duplicidade(s) precisam de revisão humana.")
            st.info("Agora abra 08 Conferência e revise as sugestões antes de qualquer liberação.")
            st.rerun()
        except Exception as exc:
            st.error(f"Falha no reprocessamento: {exc}")

st.info("Confiança baixa, pessoa/código não identificados, datas fora da competência e possíveis duplicidades permanecem pendentes para revisão humana.")
