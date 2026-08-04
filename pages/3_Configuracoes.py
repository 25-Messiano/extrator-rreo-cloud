from __future__ import annotations

import streamlit as st

from core.config_manager import load_json, save_json
from core.database import Database

st.set_page_config(page_title="Configurações", page_icon="🔧", layout="wide")
st.title("🔧 Configurações permanentes")

codes = load_json("codigos_ativos.json")
system = load_json("sistema.json")

with st.form("config_form"):
    st.subheader("RREO")
    rreo_cols = st.columns(3)
    for index, code in enumerate(codes["rreo"]):
        codes["rreo"][code] = rreo_cols[index % 3].checkbox(code, value=codes["rreo"][code], key=f"rreo_{code}")

    st.subheader("FNDE")
    fnde_cols = st.columns(3)
    for index, code in enumerate(codes["fnde"]):
        codes["fnde"][code] = fnde_cols[index % 3].checkbox(code, value=codes["fnde"][code], key=f"fnde_{code}")

    st.subheader("Atividades requeridas")
    a1, a2, a3 = st.columns(3)
    system["processar_rreo"] = a1.checkbox(
        "Processar RREO", value=system.get("processar_rreo", True)
    )
    system["processar_fnde"] = a2.checkbox(
        "Processar FNDE junto com o RREO", value=system.get("processar_fnde", True)
    )
    system["fnde_todos_estados"] = a3.checkbox(
        "Permitir Todos os Estados no painel FNDE", value=system.get("fnde_todos_estados", False)
    )

    b1, b2, b3 = st.columns(3)
    system["gerar_log_rreo"] = b1.checkbox(
        "Gerar aba LOG_RREO", value=system.get("gerar_log_rreo", True)
    )
    system["gerar_municipios_nao_encontrados"] = b2.checkbox(
        "Gerar MUNICIPIOS_NAO_ENCONTRADOS",
        value=system.get("gerar_municipios_nao_encontrados", True),
    )
    system["gerar_auditoria"] = b3.checkbox(
        "Gerar aba AUDITORIA", value=system.get("gerar_auditoria", True)
    )

    st.caption(
        "O Painel RREO executará somente as operações marcadas. "
        "Quando RREO e FNDE estiverem marcados, ambos serão processados no mesmo Excel."
    )

    st.subheader("Extração visual e auditoria")
    c1, c2, c3 = st.columns(3)
    system["gerar_log_fnde"] = c1.checkbox(
        "Gerar aba LOG_FNDE", value=system.get("gerar_log_fnde", True)
    )
    system["fnde_gemini_vision_principal"] = c2.checkbox(
        "Gemini Vision como leitura principal do FNDE",
        value=system.get("fnde_gemini_vision_principal", True),
    )
    system["fnde_usar_ocr_fallback"] = c3.checkbox(
        "Usar OCR local quando o Gemini falhar",
        value=system.get("fnde_usar_ocr_fallback", True),
    )
    d1, d2, d3 = st.columns(3)
    system["fnde_salvar_incremental"] = d1.checkbox(
        "Salvar progresso incremental",
        value=system.get("fnde_salvar_incremental", True),
    )
    system["fnde_descartar_temporarios"] = d2.checkbox(
        "Descartar temporários após validação",
        value=system.get("fnde_descartar_temporarios", True),
    )
    system["fnde_checkpoint_intervalo"] = d3.number_input(
        "Checkpoint a cada N PDFs", min_value=1, max_value=100,
        value=int(system.get("fnde_checkpoint_intervalo", 10)), step=1,
    )

    st.subheader("Processamento em lotes e desempenho")
    l1, l2, l3 = st.columns(3)
    system["processamento_em_lotes"] = l1.checkbox(
        "Processar em lotes", value=system.get("processamento_em_lotes", True)
    )
    system["retomar_processamento"] = l2.checkbox(
        "Retomar processamento interrompido", value=system.get("retomar_processamento", True)
    )
    system["salvar_checkpoint_cloud"] = l3.checkbox(
        "Salvar checkpoints no Cloud", value=system.get("salvar_checkpoint_cloud", True)
    )

    m1, m2, m3 = st.columns(3)
    system["tamanho_lote"] = m1.number_input(
        "Municípios por lote", min_value=1, max_value=50,
        value=int(system.get("tamanho_lote", 10)), step=1,
    )
    system["workers_rreo"] = m2.number_input(
        "RREO simultâneos", min_value=1, max_value=8,
        value=int(system.get("workers_rreo", 4)), step=1,
    )
    system["workers_fnde"] = m3.number_input(
        "FNDE/OCR simultâneos", min_value=1, max_value=4,
        value=int(system.get("workers_fnde", 2)), step=1,
    )

    n1, n2, n3 = st.columns(3)
    system["gemini_concorrencia"] = n1.number_input(
        "Chamadas Gemini simultâneas", min_value=1, max_value=2,
        value=int(system.get("gemini_concorrencia", 1)), step=1,
        help="Para o Render atual, mantenha 1.",
    )
    system["checkpoint_cada"] = n2.number_input(
        "Checkpoint a cada N municípios", min_value=1, max_value=100,
        value=int(system.get("checkpoint_cada", 10)), step=1,
    )
    system["atualizar_tela_cada"] = n3.number_input(
        "Atualizar tela a cada N municípios", min_value=1, max_value=50,
        value=int(system.get("atualizar_tela_cada", 5)), step=1,
    )

    system["ocr_primeiro_fnde"] = st.checkbox(
        "Usar OCR primeiro e Gemini apenas nas exceções",
        value=system.get("ocr_primeiro_fnde", True),
    )
    st.caption(
        "Configuração recomendada para o Render atual: lote 10, RREO 4, "
        "FNDE/OCR 2, Gemini 1 e atualização da tela a cada 5 municípios."
    )

    st.subheader("Sistema")
    system["modo_economico"] = st.checkbox("Modo econômico", value=system.get("modo_economico", True))
    system["usar_gemini"] = st.checkbox("Usar Gemini para interpretar as tabelas", value=system.get("usar_gemini", True))
    system["evitar_reprocessamento"] = st.checkbox("Evitar reprocessamento por hash", value=system.get("evitar_reprocessamento", True))
    submitted = st.form_submit_button("Salvar configurações", type="primary")

if submitted:
    save_json("codigos_ativos.json", codes)
    save_json("sistema.json", system)
    db = Database()
    db.set_config("codigos_ativos", codes)
    db.set_config("sistema", system)
    st.success("Configurações salvas.")


st.markdown("### Arquitetura dos índices")
st.info("RREO: município interno + UF. FNDE: código IBGE no nome. A fusão ocorre somente no plano de processamento usando a planilha-base.")
