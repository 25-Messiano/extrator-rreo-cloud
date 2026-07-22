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
