import pandas as pd
import streamlit as st

from ui.common import require_login, topbar
from services.importacao_movimento_pdf import ler_movimento_pdf, competencia_do_lote, criar_importacao_movimento

u = require_login("IMPORTAR")
topbar("Importar Movimento por PDF", "PDF mensal Banco/Caixa → prévia → conferência → base oficial")

st.info("Use os PDFs mensais do demonstrativo financeiro no mesmo padrão utilizado na carga inicial. Nada é gravado diretamente: cada arquivo vira um lote em Conferência.")
ups = st.file_uploader("Selecione um ou vários PDFs mensais", type=["pdf"], accept_multiple_files=True)

lotes = []
if ups:
    for up in ups:
        try:
            data = up.getvalue()
            mov = ler_movimento_pdf(data)
            comp = competencia_do_lote(mov) if mov else "—"
            lotes.append((up, data, mov, comp, None))
        except Exception as exc:
            lotes.append((up, up.getvalue(), [], "—", str(exc)))

    resumo = []
    for up, data, mov, comp, erro in lotes:
        resumo.append({"Arquivo": up.name, "Competência": comp, "Itens reconhecidos": len(mov), "Situação": erro or "PRONTO PARA CONFERÊNCIA"})
    st.dataframe(pd.DataFrame(resumo), width="stretch", hide_index=True)

    for up, data, mov, comp, erro in lotes:
        with st.expander(f"{up.name} — {comp} — {len(mov)} item(ns)", expanded=False):
            if erro:
                st.error(erro); continue
            preview = [{"Data": x["data"], "Código": x["codigo"], "B/C": x["origem_bc"], "Natureza": x["natureza"], "Especificação": x["historico"], "Valor": float(x["valor"])} for x in mov]
            st.dataframe(pd.DataFrame(preview), width="stretch", hide_index=True)

    confirmar = st.checkbox("Conferi a prévia. Quero gerar lotes para revisão humana em Conferência.")
    if st.button("Gerar lotes de conferência", type="primary", disabled=not confirmar):
        criados=[]; falhas=[]
        for up, data, mov, comp, erro in lotes:
            if erro or not mov:
                falhas.append(f"{up.name}: {erro or 'sem itens'}"); continue
            try:
                criados.append((up.name, criar_importacao_movimento(up.name, data, mov, u["id"])))
            except Exception as exc:
                falhas.append(f"{up.name}: {exc}")
        if criados:
            st.success("Lotes criados: " + ", ".join(f"{n} → #{i}" for n,i in criados) + ". Abra Conferência antes de liberar.")
        for f in falhas: st.warning(f)

st.warning("Linhas que o parser não reconhecer não são inventadas nem gravadas. Compare a quantidade/valores da prévia com o PDF antes de gerar o lote.")
