from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ui.common import brl, require_login, topbar, unit_banner
from services.financeiro import listar_codigos, listar_contas, listar_favorecidos, listar_centros_custo, listar_grupos, listar_vinculos
from services.fluxo_caixa import (
    CENARIOS, FREQUENCIAS, VISOES,
    agregar_projetado, agregar_realizado, comparar_projetado_realizado,
    criar_previsao, detectar_alertas_deficit, excel_bytes, listar_projetado,
    listar_realizado, pdf_bytes, resumo_projetado, resumo_realizado, saldo_abertura,
)

u = require_login("FLUXO")
topbar("Fluxo de Caixa", "Realizado, projetado, cenários, alertas e comparação")
unit_banner(compact=True)


@st.dialog("❓ Como usar o Fluxo de Caixa", width="large")
def ajuda_fluxo_caixa():
    st.markdown("""
### Finalidade
O **Fluxo de Caixa** mostra como o dinheiro entrou, saiu e deverá se comportar no futuro dentro da tesouraria ativa. A Central não mistura movimentações entre filiais: cada unidade consulta apenas os próprios dados.

### 1. Fluxo de Caixa Realizado
O realizado é formado **somente por lançamentos oficiais**: aprovados, conciliados ou fechados. Rascunhos e itens ainda em conferência não entram no realizado.

Você pode analisar o período por **dia, semana, mês, trimestre, semestre ou ano** e filtrar por:
- **Banco/Caixa**;
- **Código** do Plano de Códigos da filial;
- **DRE** vinculada ao código;
- **Centro de custo**;
- **Favorecido**;
- **Tipo**: Entrada ou Saída.

Os indicadores mostram **entradas, saídas, resultado líquido, saldo inicial e saldo final**. Quando filtros de classificação estiverem ativos, o saldo deve ser interpretado como o efeito daquele recorte sobre o saldo de abertura selecionado.

### 2. Fluxo de Caixa Projetado
O projetado registra fatos que ainda deverão acontecer. Cada previsão pode informar:
- **data prevista** e valor;
- **Entrada ou Saída**;
- conta de **Banco/Caixa**, quando conhecida;
- **Código**, cuja vinculação determina a DRE;
- **Centro de custo**;
- **Favorecido**;
- **cenário**: Realista, Pessimista ou Otimista;
- **recorrência e frequência**: semanal, quinzenal, mensal, bimestral, trimestral, semestral ou anual;
- data final da recorrência;
- probabilidade da previsão.

Uma previsão recorrente permanece como um único cadastro-base. O sistema projeta suas ocorrências até a data final informada, sem criar lançamentos financeiros oficiais.

### 3. Cenários
Use **REALISTA** para a expectativa principal, **PESSIMISTA** para uma hipótese conservadora e **OTIMISTA** para uma hipótese favorável. Os cenários são separados para evitar que valores incompatíveis sejam somados como se fossem uma única previsão.

### 4. Projetado x Realizado
A aba de comparação confronta o que foi previsto com o que efetivamente entrou ou saiu. O desvio ajuda a identificar meses em que a execução ficou acima ou abaixo da previsão.

### 5. Alertas
O sistema sinaliza **DÉFICIT** quando o saldo projetado fica negativo. Também pode indicar **SALDO INSUFICIENTE** quando as saídas pressionam o caixa e a margem restante fica muito baixa.

### 6. Datas
Todas as datas exibidas ao usuário seguem o padrão brasileiro **DD/MM/AAAA**. Internamente o banco pode armazenar datas no formato técnico próprio do banco, sem alterar a apresentação da interface e dos relatórios.

### 7. Relatórios
As visões de realizado e projetado podem ser exportadas em **PDF e Excel**, mantendo os filtros aplicados. Os gráficos são auxiliares; os valores oficiais continuam vindo dos lançamentos e previsões registrados no sistema.

> **Fluxo recomendado:** lançar/conferir → acompanhar realizado → cadastrar previsões → escolher cenário → comparar projetado x realizado → agir sobre alertas de déficit.
""")


c_help_left, c_help = st.columns([12, 1])
with c_help:
    if st.button("❓", key="ajuda_fluxo_caixa", help="Regras e instruções de uso do Fluxo de Caixa", width="stretch"):
        ajuda_fluxo_caixa()

hoje = date.today()
inicio_padrao = hoje.replace(day=1)
fim_padrao = hoje + timedelta(days=90)

st.markdown("### Período de análise")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    inicio = st.date_input("Início", inicio_padrao, format="DD/MM/YYYY", key="fluxo_inicio")
with c2:
    fim = st.date_input("Fim", fim_padrao, format="DD/MM/YYYY", key="fluxo_fim")
with c3:
    visao = st.selectbox("Visão", list(VISOES), index=2)
if fim < inicio:
    st.error("A data final não pode ser anterior à data inicial.")
    st.stop()

codigos = listar_codigos()
contas = listar_contas()
favs = listar_favorecidos()
centros = listar_centros_custo()
grupos = [g for g in listar_grupos() if g.get("ativo", True)]
vinculos = listar_vinculos()

codigo_opts = {"Todos": None, **{f"{x['codigo']} - {x['descricao']}": x['id'] for x in codigos}}
conta_opts = {"Todas": None, **{f"{x['tipo']} · {x['nome']}": x['id'] for x in contas}}
fav_opts = {"Todos": None, **{f"{x['nome']} · {x.get('tipo','')}": x['id'] for x in favs}}
centro_opts = {"Todos": None, **{f"{x['codigo']} - {x['nome']}": x['id'] for x in centros}}
dre_opts = {"Todas": None, **{f"{x['codigo_grupo']} - {x['nome']}": x['id'] for x in grupos}}

def dre_do_codigo(cid):
    for v in vinculos:
        if v.get("codigo_id") == cid and v.get("ativo", True):
            return f"{v.get('grupo','')} - {v.get('grupo_nome','')}"
    return "Sem grupo DRE vinculado"


def _df_realizado(rows):
    return pd.DataFrame([{
        "Data": r["data_formatada"], "Tipo": r["natureza"], "Banco/Caixa": r["origem"], "Conta": r["conta"],
        "Código": r["codigo"], "DRE": r["dre"], "Centro de custo": r["centro_custo"],
        "Favorecido": r["favorecido"], "Tipo favorecido": r["favorecido_tipo"],
        "Descrição": r["descricao"], "Valor (R$)": r["valor"], "Status": r["status"],
    } for r in rows])


def _df_agregado(rows):
    return pd.DataFrame([{
        "Período": r["período"], "Entradas (R$)": r["entradas"], "Saídas (R$)": r["saídas"],
        "Resultado (R$)": r["resultado"], "Saldo (R$)": r["saldo"],
    } for r in rows])


def _df_projetado(rows):
    return pd.DataFrame([{
        "Data prevista": r["data_formatada"], "Cenário": r["cenario"], "Tipo": r["natureza"],
        "Conta": r["conta"], "Código": r["codigo"], "DRE": r["dre"], "Centro de custo": r["centro_custo"],
        "Favorecido": r["favorecido"], "Tipo favorecido": r["favorecido_tipo"], "Descrição": r["descricao"],
        "Valor (R$)": r["valor"], "Probabilidade": f"{r['probabilidade']*100:.0f}%",
        "Valor ponderado (R$)": r["valor_ponderado"], "Frequência": r["frequencia"],
        "Recorrente": "SIM" if r["recorrente"] else "NÃO",
        "Fim recorrência": r["fim_recorrencia"].strftime("%d/%m/%Y") if r.get("fim_recorrencia") else "",
        "Status": r["status"],
    } for r in rows])


t1, t2, t3, t4 = st.tabs([
    "💵 Realizado", "🔮 Projetado", "⚖️ Projetado x Realizado", "➕ Nova previsão"
])

with t1:
    st.markdown("#### FLUXO DE CAIXA REALIZADO")
    st.caption("Origem: lançamentos oficiais. Use os filtros abaixo para analisar a execução financeira da unidade.")
    with st.expander("🔎 Filtros do realizado", expanded=True):
        f1, f2, f3 = st.columns(3)
        origem_rot = f1.selectbox("Banco/Caixa", ["Todos", "Banco", "Caixa"], key="real_origem")
        codigo_rot = f2.selectbox("Código", list(codigo_opts), key="real_codigo")
        dre_rot = f3.selectbox("DRE", list(dre_opts), key="real_dre")
        f4, f5, f6 = st.columns(3)
        centro_rot = f4.selectbox("Centro de custo", list(centro_opts), key="real_cc")
        fav_rot = f5.selectbox("Favorecido", list(fav_opts), key="real_fav")
        nat_rot = f6.selectbox("Tipo", ["Todos", "ENTRADA", "SAIDA"], key="real_nat")
    origem_bc = {"Banco": "B", "Caixa": "C"}.get(origem_rot)
    real = listar_realizado(
        inicio, fim, origem_bc=origem_bc, codigo_id=codigo_opts[codigo_rot], grupo_dre_id=dre_opts[dre_rot],
        centro_custo_id=centro_opts[centro_rot], favorecido_id=fav_opts[fav_rot], natureza=None if nat_rot == "Todos" else nat_rot,
    )
    abertura = saldo_abertura(inicio, origem_bc)
    res = resumo_realizado(real, abertura)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Entradas", brl(res["entradas"]))
    m2.metric("Saídas", brl(res["saidas"]))
    m3.metric("Resultado", brl(res["resultado"]))
    m4.metric("Saldo inicial", brl(res["saldo_inicial"]))
    m5.metric("Saldo final", brl(res["saldo_final"]))
    agg = agregar_realizado(real, visao, abertura)
    if agg:
        dfa = _df_agregado(agg)
        st.dataframe(dfa, width="stretch", hide_index=True)
        graf = pd.DataFrame(agg).set_index("período")[["entradas", "saídas"]]
        st.bar_chart(graf)
        st.line_chart(pd.DataFrame(agg).set_index("período")[["saldo"]])
        with st.expander("📋 Lançamentos que compõem o realizado"):
            st.dataframe(_df_realizado(real), width="stretch", hide_index=True)
    else:
        st.info("Sem movimentos oficiais no período e filtros selecionados.")
    rel_real = _df_realizado(real).to_dict("records") if real else []
    d1, d2 = st.columns(2)
    d1.download_button("📄 PDF do realizado", pdf_bytes(real, "Fluxo de Caixa Realizado"), "fluxo_caixa_realizado.pdf", "application/pdf", width="stretch")
    d2.download_button("📊 Excel do realizado", excel_bytes(rel_real, "Realizado"), "fluxo_caixa_realizado.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

with t2:
    st.markdown("#### FLUXO DE CAIXA PROJETADO")
    with st.expander("🔎 Filtros do projetado", expanded=True):
        p1, p2, p3 = st.columns(3)
        cen_rot = p1.selectbox("Cenário", ["Todos"] + list(CENARIOS), key="proj_cenario")
        pcod_rot = p2.selectbox("Código", list(codigo_opts), key="proj_codigo")
        pdre_rot = p3.selectbox("DRE", list(dre_opts), key="proj_dre")
        p4, p5, p6 = st.columns(3)
        pcc_rot = p4.selectbox("Centro de custo", list(centro_opts), key="proj_cc")
        pfav_rot = p5.selectbox("Favorecido", list(fav_opts), key="proj_fav")
        pnat_rot = p6.selectbox("Tipo", ["Todos", "ENTRADA", "SAIDA"], key="proj_nat")
        p7, _ = st.columns([1, 2])
        pconta_rot = p7.selectbox("Conta Banco/Caixa", list(conta_opts), key="proj_conta")
    proj = listar_projetado(
        inicio, fim, cenario=None if cen_rot == "Todos" else cen_rot, natureza=None if pnat_rot == "Todos" else pnat_rot,
        codigo_id=codigo_opts[pcod_rot], grupo_dre_id=dre_opts[pdre_rot], centro_custo_id=centro_opts[pcc_rot],
        favorecido_id=fav_opts[pfav_rot], conta_id=conta_opts[pconta_rot],
    )
    abertura_proj = saldo_abertura(inicio)
    rp = resumo_projetado(proj, abertura_proj)
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Entradas projetadas", brl(rp["entradas"]))
    a2.metric("Saídas projetadas", brl(rp["saidas"]))
    a3.metric("Resultado projetado", brl(rp["resultado"]))
    a4.metric("Saldo de abertura", brl(rp["saldo_inicial"]))
    a5.metric("Saldo projetado", brl(rp["saldo_final"]))
    agg_p = agregar_projetado(proj, visao, abertura_proj)
    alertas = detectar_alertas_deficit(agg_p)
    if alertas:
        st.error("⚠️ Há período(s) com risco de déficit ou saldo insuficiente neste cenário.")
        st.dataframe(pd.DataFrame([{"Período": a["período"], "Alerta": a["tipo"], "Saldo projetado (R$)": a["saldo"]} for a in alertas]), width="stretch", hide_index=True)
    else:
        st.success("Nenhum déficit projetado nos filtros selecionados.")
    if agg_p:
        st.dataframe(_df_agregado(agg_p), width="stretch", hide_index=True)
        st.bar_chart(pd.DataFrame(agg_p).set_index("período")[["entradas", "saídas"]])
        st.line_chart(pd.DataFrame(agg_p).set_index("período")[["saldo"]])
        with st.expander("📋 Ocorrências previstas no período"):
            st.dataframe(_df_projetado(proj), width="stretch", hide_index=True)
    else:
        st.info("Sem previsões para o período e filtros selecionados.")
    rel_proj = _df_projetado(proj).to_dict("records") if proj else []
    q1, q2 = st.columns(2)
    q1.download_button("📄 PDF do projetado", pdf_bytes(proj, "Fluxo de Caixa Projetado", [
        ("data_formatada", "Data"), ("cenario", "Cenário"), ("natureza", "Tipo"), ("codigo", "Código"),
        ("dre", "DRE"), ("centro_custo", "Centro"), ("favorecido", "Favorecido"), ("valor_ponderado", "Valor ponderado")
    ]), "fluxo_caixa_projetado.pdf", "application/pdf", width="stretch")
    q2.download_button("📊 Excel do projetado", excel_bytes(rel_proj, "Projetado"), "fluxo_caixa_projetado.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

with t3:
    st.markdown("#### COMPARATIVO PROJETADO x REALIZADO")
    st.caption("Escolha um cenário. O realizado vem dos lançamentos oficiais; o projetado vem das previsões cadastradas.")
    cen_comp = st.selectbox("Cenário para comparação", list(CENARIOS), key="comp_cenario")
    real_comp = listar_realizado(inicio, fim)
    proj_comp = listar_projetado(inicio, fim, cenario=cen_comp)
    comp = comparar_projetado_realizado(real_comp, proj_comp, visao)
    if comp:
        dfc = pd.DataFrame(comp)
        st.dataframe(dfc.rename(columns={
            "período": "Período", "realizado_entradas": "Entradas realizadas", "projetado_entradas": "Entradas projetadas",
            "realizado_saídas": "Saídas realizadas", "projetado_saídas": "Saídas projetadas",
            "realizado_resultado": "Resultado realizado", "projetado_resultado": "Resultado projetado", "desvio_resultado": "Desvio do resultado",
        }), width="stretch", hide_index=True)
        st.bar_chart(dfc.set_index("período")[["realizado_resultado", "projetado_resultado"]])
        st.download_button("📊 Excel comparativo", excel_bytes(dfc.to_dict("records"), "Comparativo"), "fluxo_projetado_x_realizado.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    else:
        st.info("Não há dados realizados nem projetados no período.")

with t4:
    st.markdown("#### NOVA PREVISÃO")
    st.caption("A previsão não cria lançamento oficial. Ela serve para planejamento e comparação futura.")
    cod_prev = {"— Sem código —": None, **{f"{x['codigo']} - {x['descricao']}": x['id'] for x in codigos}}
    conta_prev = {"— Não definida —": None, **{f"{x['tipo']} · {x['nome']}": x['id'] for x in contas}}
    cc_prev = {"— Não definido —": None, **{f"{x['codigo']} - {x['nome']}": x['id'] for x in centros}}
    fav_prev = {"— Não definido —": None, **{f"{x['nome']} · {x.get('tipo','')}": x['id'] for x in favs}}
    with st.form("nova_previsao_v265"):
        n1, n2, n3 = st.columns(3)
        dt = n1.date_input("Data prevista", hoje, format="DD/MM/YYYY")
        nat = n2.selectbox("Tipo", ["ENTRADA", "SAIDA"])
        valor = n3.number_input("Valor previsto", min_value=0.01, step=0.01)
        n4, n5, n6 = st.columns(3)
        conta_rot = n4.selectbox("Conta Banco/Caixa", list(conta_prev))
        cod_rot = n5.selectbox("Código", list(cod_prev))
        cen = n6.selectbox("Cenário", list(CENARIOS))
        cid = cod_prev[cod_rot]
        st.caption(f"DRE do código selecionado: **{dre_do_codigo(cid) if cid else 'Definida quando um código vinculado à DRE for selecionado'}**")
        n7, n8 = st.columns(2)
        cc_rot = n7.selectbox("Centro de custo", list(cc_prev))
        fav_rot = n8.selectbox("Favorecido", list(fav_prev))
        desc = st.text_area("Descrição da previsão")
        rec = st.checkbox("Esta previsão é recorrente")
        n9, n10, n11 = st.columns(3)
        freq = n9.selectbox("Frequência", list(FREQUENCIAS), index=3 if rec else 0, disabled=not rec)
        fim_rec = n10.date_input("Até", dt, min_value=dt, format="DD/MM/YYYY", disabled=not rec)
        prob = n11.slider("Probabilidade (%)", 0, 100, 100)
        ok = st.form_submit_button("Salvar previsão", type="primary", width="stretch")
    if ok:
        try:
            rid = criar_previsao(
                dt, nat, valor, desc, cid, recorrencia=freq, probabilidade=prob/100, usuario_id=u["id"],
                conta_id=conta_prev[conta_rot], centro_custo_id=cc_prev[cc_rot], favorecido_id=fav_prev[fav_rot],
                cenario=cen, frequencia=freq, recorrente=rec, data_fim_recorrencia=fim_rec if rec else None,
            )
            st.success(f"Previsão #{rid} criada com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
