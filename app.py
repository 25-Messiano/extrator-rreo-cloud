from __future__ import annotations

import os
import streamlit as st

st.set_page_config(
    page_title="Extrator RREO Cloud",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

def configurada(*nomes: str) -> bool:
    return any(bool(os.getenv(nome, "").strip()) for nome in nomes)

cloud_ok = configurada("GOOGLE_SERVICE_ACCOUNT_JSON", "GCP_KEY")
gemini_ok = configurada("GEMINI_API_KEY", "GOOGLE_API_KEY")

st.title("Extrator RREO Cloud")
st.caption("Extração de dados do RREO municipal com Google Cloud Storage, Gemini e Excel.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Armazenamento", "Cloud Storage")
c2.metric("Banco", "SQLite")
c3.metric("Credenciais GCS", "Configuradas" if cloud_ok else "Pendentes")
c4.metric("Gemini", "Configurado" if gemini_ok else "Pendente")

st.info("Use o menu lateral para abrir o Painel, Histórico, Configurações e Arquivos Cloud.")

st.subheader("Fluxo operacional")
st.markdown("""
1. Os PDFs são listados e baixados do Google Cloud Storage.
2. O sistema identifica o município e extrai as linhas do RREO.
3. O Gemini seleciona o valor da coluna **Receitas Realizadas Até o Bimestre (b)**.
4. O Excel é preenchido, enviado ao Cloud Storage e liberado para download.
""")

st.subheader("Configuração")
if cloud_ok:
    st.success("Credenciais do Google Cloud Storage encontradas.")
else:
    st.warning("Configure GOOGLE_SERVICE_ACCOUNT_JSON ou GCP_KEY no Render.")
if gemini_ok:
    st.success("Chave do Gemini encontrada.")
else:
    st.warning("Configure GEMINI_API_KEY no Render.")
