from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ui.common import require_login, brl, db_badge, tenant_identity
from ui.help_modulos import botao_ajuda
from services.financeiro import resumo_dashboard, serie_mensal_dashboard, listar_lancamentos


user = require_login("CONSULTAR")
ident = tenant_identity()

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1500px;}
    .dash-title {font-size: 2.2rem; font-weight: 750; margin-bottom: .1rem; color: #1f2937;}
    .dash-sub {color:#64748b; margin-bottom:1rem;}
    .dash-card {
        background:#ffffff; border:1px solid #e7ebf0; border-radius:14px;
        padding:18px 18px 14px 18px; min-height:120px;
        box-shadow:0 2px 8px rgba(15,23,42,.04);
    }
    .dash-label {font-size:.78rem; color:#64748b; text-transform:uppercase; letter-spacing:.04em; font-weight:700;}
    .dash-value {font-size:1.65rem; font-weight:750; color:#0f172a; margin-top:9px;}
    .dash-note {font-size:.78rem; color:#94a3b8; margin-top:6px;}
    .dash-section {
        background:#ffffff; border:1px solid #e7ebf0; border-radius:14px;
        padding:18px; box-shadow:0 2px 8px rgba(15,23,42,.035);
    }
    .status-ok {color:#15803d; font-weight:700;}
    .status-warn {color:#b45309; font-weight:700;}
    div[data-testid="stMetric"] {background:white; border:1px solid #e7ebf0; padding:14px; border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Cabeçalho
c_title, c_user = st.columns([5, 1.35])
with c_title:
    st.markdown(f'<div class="dash-title">{ident["titulo_operacional"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dash-sub">{ident["linha_identificacao"]}<br>Dashboard financeiro • visão consolidada de Banco, Caixa, pendências e fluxo.</div>', unsafe_allow_html=True)
with c_user:
    st.caption(f"Usuário: **{user.get('nome','')}**")
    st.caption(f"Perfil: **{user.get('perfil','')}**")
    if st.button("Sair", width="stretch"):
        st.session_state.clear()
        st.rerun()

botao_ajuda("dashboard")
st.info(
    "🎯 OBJETIVO — Sistema completo para gestão financeira, contábil, patrimonial e de relatórios da APLB, "
    "com controle de lançamentos, Banco/Caixa, códigos oficiais, DRE, importação inteligente de extratos, "
    "conciliação, fluxo de caixa realizado e projetado, patrimônio, usuários, auditoria e backup seguro no Cloud."
)

# Período do painel
hoje = date.today()
meses = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
col_a, col_m, col_refresh = st.columns([1, 1.4, 4.6])
with col_a:
    ano = st.number_input("Exercício", min_value=2000, max_value=2100, value=hoje.year, step=1)
with col_m:
    mes = st.selectbox("Mês de referência", list(meses), index=hoje.month - 1, format_func=lambda x: meses[x])
with col_refresh:
    st.write("")
    st.write("")
    if st.button("↻ Atualizar painel"):
        st.rerun()

r = resumo_dashboard(int(ano), int(mes))

# Cards principais
cards = [
    ("Saldo Banco", brl(r["saldo_banco"]), "Saldo oficial acumulado"),
    ("Saldo Caixa", brl(r["saldo_caixa"]), "Saldo oficial acumulado"),
    ("Saldo Total", brl(r["saldo_total"]), "Banco + Caixa"),
    ("Entradas no mês", brl(r["entradas_mes"]), f"{meses[int(mes)]}/{int(ano)}"),
    ("Saídas no mês", brl(r["saidas_mes"]), f"{meses[int(mes)]}/{int(ano)}"),
    ("Resultado do mês", brl(r["resultado_mes"]), "Entradas − saídas"),
]
cols = st.columns(6)
for col, (label, value, note) in zip(cols, cards):
    with col:
        st.markdown(
            f'<div class="dash-card"><div class="dash-label">{label}</div>'
            f'<div class="dash-value">{value}</div><div class="dash-note">{note}</div></div>',
            unsafe_allow_html=True,
        )

st.write("")

# Ações rápidas
st.subheader("Ações rápidas")
a1, a2, a3, a4, a5 = st.columns(5)
with a1:
    st.page_link("pages/02_Lancamentos.py", label="＋ Novo lançamento", icon="🧾", width="stretch")
with a2:
    st.page_link("pages/06_Extratos_Bancarios.py", label="Importar extrato", icon="🏦", width="stretch")
with a3:
    st.page_link("pages/08_Conferencia.py", label="Conferir importações", icon="✅", width="stretch")
with a4:
    st.page_link("pages/10_Fluxo_de_Caixa.py", label="Fluxo de caixa", icon="📈", width="stretch")
with a5:
    st.page_link("pages/16_Relatorios_DRE.py", label="Relatórios / DRE", icon="📊", width="stretch")

st.write("")

# Indicadores operacionais
st.subheader("Situação operacional")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Pendentes de conferência", r["itens_conferencia_pendentes"])
s2.metric("Conciliações pendentes", r["conciliacoes_pendentes"])
s3.metric("Lançamentos em rascunho", r["lancamentos_rascunho"])
s4.metric("Importações em conferência", r["importacoes_em_conferencia"])

# Gráfico + resumo de fluxo
left, right = st.columns([1.8, 1])
with left:
    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    st.markdown("### Movimento dos últimos 6 meses")
    serie = serie_mensal_dashboard(int(ano), int(mes), meses=6)
    if serie:
        df = pd.DataFrame(serie)
        df_chart = df.set_index("periodo")[["entradas", "saidas"]]
        st.bar_chart(df_chart, height=280)
    else:
        st.info("Ainda não há movimentação oficial suficiente para o gráfico.")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    st.markdown("### Fluxo projetado")
    st.metric("Entradas previstas", brl(r["projetado_entradas"]))
    st.metric("Saídas previstas", brl(r["projetado_saidas"]))
    st.metric("Saldo projetado", brl(r["saldo_projetado"]))
    if r["saldo_projetado"] < 0:
        st.warning("A projeção indica saldo negativo para o período.")
    else:
        st.success("A projeção mantém saldo não negativo.")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")

# Movimentos recentes + integridade
left2, right2 = st.columns([2.2, 1])
with left2:
    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    st.markdown("### Lançamentos recentes")
    rows = listar_lancamentos(limit=12)
    if rows:
        df = pd.DataFrame(rows)
        preferred = ["data", "codigo", "B/C", "natureza", "especificacao", "valor", "status"]
        cols_presentes = [c for c in preferred if c in df.columns]
        df = df[cols_presentes].copy()
        if "valor" in df.columns:
            df["valor"] = df["valor"].map(brl)
        st.dataframe(df, width="stretch", hide_index=True, height=390)
    else:
        st.info("Ainda não existem lançamentos.")
    st.markdown('</div>', unsafe_allow_html=True)

with right2:
    st.markdown('<div class="dash-section">', unsafe_allow_html=True)
    st.markdown("### Saúde do sistema")
    db_badge()
    if r["periodo_fechado"]:
        st.info(f"🔒 {meses[int(mes)]}/{int(ano)} está FECHADO.")
    else:
        st.success(f"🔓 {meses[int(mes)]}/{int(ano)} está ABERTO.")
    st.write(f"**Lançamentos oficiais:** {r['total_lancamentos_oficiais']}")
    st.write(f"**Códigos ativos:** {r['codigos_ativos']}")
    st.write(f"**Contas ativas:** {r['contas_ativas']}")
    st.write(f"**Bens patrimoniais ativos:** {r['patrimonio_ativo']}")
    st.caption("Os indicadores são calculados diretamente da base oficial.")
    st.markdown('</div>', unsafe_allow_html=True)
