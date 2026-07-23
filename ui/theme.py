from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --navy:#0b1730; --blue:#2f5bea; --purple:#7c3aed; --green:#16a34a; --muted:#64748b; }
        .stApp { background:#f7f9fc; color:#12213a; }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1730 0%,#111f3e 100%); }
        [data-testid="stSidebar"] * { color:#e8eefc !important; }
        [data-testid="stSidebarNav"] { display:none; }
        .block-container { max-width:1500px; padding-top:1.2rem; padding-bottom:2rem; }
        h1,h2,h3 { color:#13213b; letter-spacing:-.02em; }
        .brand {display:flex; gap:12px; align-items:center; padding:12px 4px 22px 4px; border-bottom:1px solid rgba(255,255,255,.10); margin-bottom:18px;}
        .brand-icon{width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,#2f5bea,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 10px 25px rgba(47,91,234,.25)}
        .brand-title{font-weight:800;font-size:20px;line-height:1.05}.brand-sub{font-size:11px;color:#aab7d4!important;margin-top:3px}
        .side-label{font-size:10px!important;font-weight:800;letter-spacing:.12em;color:#8796b8!important;margin:12px 0 7px}
        .side-status{font-size:12px;padding:7px 0;color:#cbd6ee!important}.dot{display:inline-block;width:9px;height:9px;border-radius:999px;background:#22c55e;margin-right:8px;box-shadow:0 0 0 3px rgba(34,197,94,.13)}
        .hero-row{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}.hero-title{font-size:31px;font-weight:850;color:#13213b}.hero-sub{color:#6b7890;font-size:13px;margin-top:5px}.online{display:inline-flex;align-items:center;gap:7px;background:#eaf8ef;color:#16833b;padding:7px 12px;border-radius:8px;font-weight:700;font-size:12px}
        .card{background:#fff;border:1px solid #e2e8f2;border-radius:13px;padding:16px 17px;box-shadow:0 3px 12px rgba(15,23,42,.045);height:100%}
        .metric-card{display:flex;gap:13px;align-items:center}.metric-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px;background:#edf2ff}.metric-label{font-size:11px;color:#526079}.metric-value{font-size:21px;font-weight:800;color:#14213d;margin:2px 0}.metric-ok{font-size:11px;color:#16a34a;font-weight:700}
        .section-card{background:#fff;border:1px solid #dfe6f1;border-radius:13px;padding:16px 17px;box-shadow:0 3px 12px rgba(15,23,42,.035);margin:12px 0}.section-title{font-weight:800;color:#17233d;font-size:14px;margin-bottom:12px}.section-num{color:#2f5bea;margin-right:7px}
        .mini-stat{background:#fbfcff;border:1px solid #e7ebf3;border-radius:10px;padding:11px 12px}.mini-label{font-size:10px;color:#6a768c}.mini-value{font-size:18px;font-weight:800;color:#17233d;margin-top:3px}
        .flow{display:flex;align-items:center;gap:12px;justify-content:space-between}.flow-step{flex:1;display:flex;gap:11px;align-items:center}.flow-num{width:24px;height:24px;border-radius:50%;background:#2f5bea;color:white;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800}.flow-name{font-weight:750;font-size:12px;color:#1a2741}.flow-desc{font-size:10px;color:#718096;line-height:1.35}.flow-arrow{color:#8896ae;font-size:20px}
        div[data-testid="stButton"] > button[kind="primary"]{background:linear-gradient(90deg,#2f5bea,#3b64ec);border:none;border-radius:8px;font-weight:750;min-height:42px}
        div[data-testid="stDownloadButton"] > button{background:#16a34a;color:white;border:none;border-radius:8px;font-weight:750;min-height:42px}
        .stSelectbox div[data-baseweb="select"]>div,.stTextInput input{border-radius:8px!important;border-color:#d7deea!important;background:white!important}
        [data-testid="stDataFrame"]{border:1px solid #e3e8f1;border-radius:10px;overflow:hidden}
        .footerbar{background:linear-gradient(90deg,#eef3ff,#f4efff);border:1px solid #dde6fb;border-radius:9px;padding:10px 13px;color:#31529b;font-size:11px;margin-top:14px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand"><div class="brand-icon">☁</div><div><div class="brand-title">Extrator<br>RREO Cloud</div><div class="brand-sub">Dados públicos inteligentes</div></div></div>
            <div class="side-label">NAVEGAÇÃO</div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("app.py", label="Painel inicial", icon="🏠")
        st.page_link("pages/1_Painel.py", label="Painel de extração", icon="📊")
        st.page_link("pages/4_Arquivos_Cloud.py", label="Arquivos Cloud", icon="📁")
        st.page_link("pages/2_Historico.py", label="Histórico", icon="🕘")
        st.page_link("pages/3_Configuracoes.py", label="Configurações", icon="⚙️")
        st.markdown(
            """
            <div style="height:120px"></div><div class="side-label">CREDENCIAIS</div>
            <div class="side-status"><span class="dot"></span>Cloud Storage conectado</div>
            <div class="side-status"><span class="dot"></span>SQLite ativo</div>
            <div class="side-status"><span class="dot"></span>Gemini configurado</div>
            <div style="margin-top:34px;font-size:10px;color:#8391ae!important">VERSÃO</div><div style="font-size:12px;margin-top:5px">v1.1.0</div>
            """,
            unsafe_allow_html=True,
        )


def metric_card(icon: str, label: str, value: str, status: str, tone: str = "blue") -> None:
    bg = {"blue":"#edf2ff","purple":"#f3edff","green":"#eaf8ef"}.get(tone,"#edf2ff")
    st.markdown(
        f'<div class="card metric-card"><div class="metric-icon" style="background:{bg}">{icon}</div><div><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-ok">{status} &nbsp;●</div></div></div>',
        unsafe_allow_html=True,
    )

