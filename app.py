from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

from integrations.google_storage import health_check
from ui.theme import apply_theme, metric_card, render_sidebar

st.set_page_config(page_title="Extrator RREO Cloud", page_icon="☁️", layout="wide", initial_sidebar_state="expanded")
apply_theme()
render_sidebar()

cloud_env = bool((os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GCP_KEY") or "").strip())
gemini_ok = bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())
cloud_status = health_check() if cloud_env else {"ok": False}

st.markdown(
    f'<div class="hero-row"><div><div class="hero-title">Painel de Extração</div><div class="hero-sub">Extração de dados do RREO municipal com Google Cloud Storage, Gemini e Excel.</div></div><div><span style="color:#536179;font-size:12px;margin-right:14px">◷ {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</span><span class="online">● Sistema Online</span></div></div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
with c1: metric_card("☁", "Armazenamento", "Cloud Storage", "Conectado" if cloud_status.get("ok") else "Verificar", "blue")
with c2: metric_card("🗄", "Banco de Dados", "SQLite", "Ativo", "purple")
with c3: metric_card("🛡", "Credenciais GCS", "Configuradas" if cloud_env else "Pendentes", "OK" if cloud_env else "Atenção", "green")
with c4: metric_card("✦", "Gemini API", "Configurado" if gemini_ok else "Pendente", "OK" if gemini_ok else "Atenção", "blue")

st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">1.</span>Começar uma extração</div>', unsafe_allow_html=True)
a,b = st.columns([3,1])
with a:
    st.markdown("Selecione o estado, o município e o ano no painel operacional. O sistema lista os PDFs, processa os dados e gera a planilha automaticamente.")
with b:
    st.page_link("pages/1_Painel.py", label="Abrir Painel de Extração", icon="▶️", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-card"><div class="section-title">Fluxo Operacional</div><div class="flow"><div class="flow-step"><div class="flow-num">1</div><div><div class="flow-name">Listagem</div><div class="flow-desc">PDFs localizados no Cloud Storage</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">2</div><div><div class="flow-name">Extração</div><div class="flow-desc">Gemini identifica as linhas do RREO</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">3</div><div><div class="flow-name">Geração</div><div class="flow-desc">Excel preenchido com os dados</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">4</div><div><div class="flow-name">Upload</div><div class="flow-desc">Resultado salvo e liberado</div></div></div></div></div>', unsafe_allow_html=True)

if not cloud_status.get("ok"):
    st.warning("A interface está ativa, mas a conexão com o Cloud Storage precisa ser verificada.")

st.markdown('<div class="footerbar">● Sistema operando com Gemini &nbsp;•&nbsp; Extração inteligente de dados &nbsp;•&nbsp; Processamento em lote &nbsp;•&nbsp; Armazenamento seguro na nuvem</div>', unsafe_allow_html=True)
