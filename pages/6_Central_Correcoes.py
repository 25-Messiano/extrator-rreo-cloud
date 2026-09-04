from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st

from core.central_correcoes import (
    correction_preset,
    generate_pending_report,
    load_catalog,
    rebuild_index_from_state_spreadsheets,
    upload_pending_report,
)
from core.maestro_ia import ExtractionCase, make_case_id, observe_case, status_snapshot
from integrations.google_storage import health_check
from ui.theme import apply_theme, metric_card, render_sidebar

st.set_page_config(page_title="Central de Correções", page_icon="🛠️", layout="wide", initial_sidebar_state="expanded")
apply_theme()
render_sidebar()

st.markdown(
    '<div class="hero-row"><div><div class="hero-title">Central de Correções</div>'
    '<div class="hero-sub">Conferência pós-processamento, reconstrução de JSONs, pendências e correções por município.</div>'
    '</div><span class="online">● Sistema Online</span></div>',
    unsafe_allow_html=True,
)

maestro_status = status_snapshot()
st.caption(
    f"🧠 MAESTRO IA · Modo sombra={'SIM' if maestro_status.get('shadow_mode') else 'NÃO'} · "
    f"OpenAI live={'SIM' if maestro_status.get('live_ai') else 'NÃO'} · "
    f"Memória operacional: {maestro_status.get('memory', {}).get('cases', 0)} caso(s)."
)

status = health_check()
if not status.get("ok"):
    st.error("Cloud Storage indisponível.")
    st.code(status.get("message", "Erro desconhecido"))
    st.stop()

year = st.selectbox("Ano de referência", list(range(2030, 2022, -1)), index=list(range(2030, 2022, -1)).index(2025))
bimestre = st.selectbox("Bimestre RREO para conferência dos PDFs", [1,2,3,4,5,6], index=5, format_func=lambda v: f"B{v}")

st.markdown("### 1. Reconstrução do índice de correções")
st.caption(
    "Lê somente as planilhas estaduais já existentes no Cloud e cria JSONs técnicos por UF. "
    "Nenhuma planilha processada é alterada nesta etapa."
)
if st.button("🔄 Reconstruir índice a partir das planilhas existentes", type="primary", width="stretch"):
    bar = st.progress(0.0, text="Localizando planilhas estaduais...")
    def on_progress(pos: int, total: int, uf: str) -> None:
        bar.progress(pos / max(total, 1), text=f"Reconstruindo {uf}: {pos}/{total}")
    try:
        catalog = rebuild_index_from_state_spreadsheets(year, progress=on_progress, annotate_pdfs=True, bimestre=bimestre)
        st.session_state[f"central_catalog_{year}"] = catalog
        bar.empty()
        st.success(
            f"Índice reconstruído: {catalog.get('total_municipios', 0)} município(s) em "
            f"{len(catalog.get('ufs', []))} UF(s). "
            f"Planilhas estaduais encontradas: {catalog.get('planilhas_estaduais_encontradas', 0)}."
        )
    except Exception as error:
        bar.empty()
        st.error("Não foi possível reconstruir o índice de correções.")
        st.exception(error)

catalog = st.session_state.get(f"central_catalog_{year}") or load_catalog(year)
if not catalog:
    st.info("Ainda não existe catálogo de correções para este ano. Use o botão acima para reconstruí-lo a partir das planilhas estaduais.")
    st.stop()

records = list(catalog.get("municipios", []))
pendentes = [r for r in records if r.get("status_geral") != "DADOS_PRESENTES"]
parciais = [r for r in records if r.get("status_geral") == "PARCIAL"]
sem_dados = [r for r in records if r.get("status_geral") in {"PENDENTE", "SEM_DADOS"}]

m1, m2, m3, m4 = st.columns(4)
with m1: metric_card("🗺️", "Municípios indexados", str(len(records)), "Catálogo", "blue")
with m2: metric_card("⚠️", "Pendências", str(len(pendentes)), "Revisar", "purple")
with m3: metric_card("🟡", "Parciais", str(len(parciais)), "Conferir", "blue")
with m4: metric_card("🔴", "Sem dados", str(len(sem_dados)), "Prioridade", "green")

st.markdown("### 2. Pendências e conferência")
ufs = sorted({str(r.get("uf") or "") for r in records if r.get("uf")})
f1, f2, f3 = st.columns(3)
with f1:
    uf_filter = st.selectbox("Estado", ["Todos"] + ufs)
with f2:
    source_filter = st.selectbox("Fonte", ["Todas", "RREO", "FNDE"])
with f3:
    status_filter = st.selectbox("Status", ["Todos", "PENDENTE", "PARCIAL", "DADOS_PRESENTES", "SEM_DADOS"])

filtered = []
for r in records:
    if uf_filter != "Todos" and r.get("uf") != uf_filter:
        continue
    if status_filter != "Todos" and r.get("status_geral") != status_filter:
        continue
    if source_filter == "RREO" and r.get("status_rreo") == "NA":
        continue
    if source_filter == "FNDE" and r.get("status_fnde") == "NA":
        continue
    filtered.append(r)

view = pd.DataFrame([
    {
        "UF": r.get("uf", ""),
        "IBGE": r.get("codigo_ibge", ""),
        "Município": r.get("municipio", ""),
        "Status": r.get("status_geral", ""),
        "RREO": r.get("status_rreo", ""),
        "PDF RREO": "SIM" if r.get("pdf_rreo") is True else ("NÃO" if r.get("pdf_rreo") is False else "N/D"),
        "Erro RREO": r.get("erro_rreo", ""),
        "FNDE": r.get("status_fnde", ""),
        "PDF FNDE": "SIM" if r.get("pdf_fnde") is True else ("NÃO" if r.get("pdf_fnde") is False else "N/D"),
        "Erro FNDE": r.get("erro_fnde", ""),
    }
    for r in filtered
])
st.dataframe(view, width="stretch", hide_index=True, height=430)

if st.button("📊 Gerar Relatório de Pendências", width="stretch"):
    try:
        with tempfile.TemporaryDirectory(prefix="central_correcoes_") as td:
            filename = f"PENDENCIAS_BRASIL_{year}.xlsx"
            path = generate_pending_report(year, records, Path(td) / filename)
            payload = path.read_bytes()
            cloud = upload_pending_report(year, path)
        st.session_state[f"pending_report_{year}"] = {"name": filename, "bytes": payload, "cloud": cloud.get("blob_name", "")}
        st.success("Relatório de pendências gerado e salvo no Cloud.")
    except Exception as error:
        st.error("Falha ao gerar o relatório de pendências.")
        st.exception(error)

report = st.session_state.get(f"pending_report_{year}")
if report:
    st.caption(f"Cloud: `{report.get('cloud', '')}`")
    st.download_button(
        "⬇ Baixar Relatório de Pendências",
        data=report["bytes"],
        file_name=report["name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

st.markdown("### 3. Corrigir município")
st.caption(
    "A Central prepara a correção e abre o mesmo motor oficial de extração em Rodada de Correção. "
    "Isso evita manter dois extratores diferentes no aplicativo."
)
if not filtered:
    st.info("Nenhum município disponível com os filtros atuais.")
else:
    by_key = {f"{r.get('codigo_ibge')} | {r.get('municipio')}/{r.get('uf')}": r for r in filtered}
    chosen_key = st.selectbox("Município para correção", list(by_key))
    chosen = by_key[chosen_key]
    available_sources = []
    if chosen.get("status_rreo") != "NA": available_sources.append("RREO")
    if chosen.get("status_fnde") != "NA": available_sources.append("FNDE")
    if len(available_sources) == 2: available_sources.append("RREO+FNDE")
    source = st.selectbox("Fonte a corrigir", available_sources or ["RREO"])

    if st.button("🛠️ Abrir no Painel em Rodada de Correção", type="primary", width="stretch"):
        observe_case(ExtractionCase(
            case_id=make_case_id(source, year, str(chosen.get("uf") or ""), str(chosen.get("codigo_ibge") or "")),
            source=source,
            year=year,
            uf=str(chosen.get("uf") or ""),
            ibge=str(chosen.get("codigo_ibge") or ""),
            municipality=str(chosen.get("municipio") or ""),
            operation="CENTRAL_CORRECOES",
            status=str(chosen.get("status_geral") or "PENDENTE"),
            error=str(chosen.get("erro_rreo") or chosen.get("erro_fnde") or ""),
            pdf_name=str(chosen.get("pdf_rreo_nome") or chosen.get("pdf_fnde_nome") or ""),
            metadata={"origem": "CENTRAL_CORRECOES", "shadow": True},
        ))
        preset = correction_preset(year, chosen, source)
        st.session_state["central_correcao_preset"] = preset
        st.session_state["execucao_escolhida_widget"] = preset["execucao"]
        st.session_state["ano_referencia_widget"] = preset["ano"]
        st.session_state["estado_cloud_widget"] = preset["estado_cloud"]
        st.session_state["tipo_rodada"] = preset["tipo_rodada"]
        st.switch_page("pages/1_Painel.py")
