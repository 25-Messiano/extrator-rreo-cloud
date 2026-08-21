from __future__ import annotations

import pandas as pd
import streamlit as st

from core.database import Database

st.set_page_config(page_title="Histórico", page_icon="🕘", layout="wide")
st.title("🕘 Histórico e atividade")
db = Database()

tab1, tab2, tab3 = st.tabs(["Execuções", "Municípios", "Histórico técnico"])

with tab1:
    jobs = db.list_jobs(200)
    if jobs:
        st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há execuções persistentes registradas.")

with tab2:
    ano = st.number_input("Ano", min_value=2023, max_value=2030, value=2025, step=1)
    activity = db.list_activity(int(ano))
    if activity:
        frame = pd.DataFrame(activity)
        uf = st.selectbox("Filtrar UF", ["TODAS"] + sorted(frame["uf"].dropna().unique().tolist()))
        status = st.selectbox("Filtrar status", ["TODOS"] + sorted(frame["status_geral"].dropna().unique().tolist()))
        if uf != "TODAS":
            frame = frame[frame["uf"] == uf]
        if status != "TODOS":
            frame = frame[frame["status_geral"] == status]
        st.dataframe(frame, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum município registrado para esse ano.")

with tab3:
    rows = db.list_history(200)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há processamentos técnicos registrados.")
