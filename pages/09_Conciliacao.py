import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import select

from ui.common import require_login, topbar
from ui.help_modulos import botao_ajuda
from database.db import session_scope
from models.entities import ContaFinanceira, Lancamento, Conciliacao
from services.financeiro import STATUS_OFICIAIS
from services.auditoria import registrar_auditoria
from services.conciliacao import diagnostico_periodo, executar_conciliacao
from services.tenancy import tenant_where, get_active_tesouraria_id
from services.exportacao import dataframe_excel_bytes

u = require_login("CONCILIAR")
topbar("Conciliação Bancária", "Data + Entrada/Saída + Valor, com conferência global dos totais")
botao_ajuda("conciliacao")

hoje = date.today()
c1,c2,c3 = st.columns(3)
ano = c1.selectbox("Ano", list(range(2026,2051)), index=max(0,min(24,hoje.year-2026)))
mes = c2.selectbox("Mês", list(range(1,13)), index=hoje.month-1)
with session_scope() as s:
    contas = s.scalars(select(ContaFinanceira).where(ContaFinanceira.ativo.is_(True), tenant_where(ContaFinanceira.tesouraria_id)).order_by(ContaFinanceira.nome)).all()
opts = {"Todas as contas": None}
opts.update({f"{x.nome} | {x.banco or ''} {x.conta or ''}".strip(): x.id for x in contas})
conta_label = c3.selectbox("Conta bancária", list(opts))
conta_id = opts[conta_label]
comp = f"{ano:04d}-{mes:02d}"

st.caption("Regra V14: a IA não decide a conciliação. O núcleo compara data + natureza (entrada/saída) + valor. Descrição/favorecido/documento só desempata quando há mais de um candidato.")

diag = diagnostico_periodo(comp, conta_id)
t = diag["totais"]
st.subheader("Conferência global do período")
r1,r2 = st.columns(2)
with r1:
    st.markdown("**Entradas de Banco**")
    a,b,c = st.columns(3)
    a.metric("Extrato", f"R$ {t['entrada_extrato']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
    b.metric("Base oficial", f"R$ {t['entrada_base']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
    c.metric("Diferença", f"R$ {t['dif_entrada']:,.2f}".replace(",","X").replace(".",",").replace("X","."), delta=None)
    if abs(t["dif_entrada"]) < 0.005:
        st.success("Totais de entrada conciliados")
    else:
        st.warning("Há divergência nas entradas")
with r2:
    st.markdown("**Saídas de Banco**")
    a,b,c = st.columns(3)
    a.metric("Extrato", f"R$ {t['saida_extrato']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
    b.metric("Base oficial", f"R$ {t['saida_base']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
    c.metric("Diferença", f"R$ {t['dif_saida']:,.2f}".replace(",","X").replace(".",",").replace("X","."), delta=None)
    if abs(t["dif_saida"]) < 0.005:
        st.success("Totais de saída conciliados")
    else:
        st.warning("Há divergência nas saídas")

m1,m2,m3 = st.columns(3)
m1.metric("Conciliáveis", diag["conciliaveis"])
m2.metric("Ambíguos", diag["ambiguos"])
m3.metric("Sem correspondência", diag["sem_correspondencia"])

if st.button("Executar conciliação segura", type="primary"):
    n, novo = executar_conciliacao(comp, u["id"], conta_id)
    st.success(f"{n} correspondência(s) única(s) conciliada(s). Nenhum lançamento foi criado automaticamente.")
    st.rerun()

with st.expander("Ver comparação linha a linha", expanded=False):
    st.dataframe(diag["matches"], width="stretch", hide_index=True)
with st.expander("Ver conferência diária dos totais", expanded=False):
    st.dataframe(diag["diario"], width="stretch", hide_index=True)

st.subheader("Relatório de divergências")
divergencias=[x for x in diag["matches"] if x["situacao"] != "CONCILIAVEL"]
if divergencias:
    dfd=pd.DataFrame(divergencias)
    st.dataframe(dfd,width="stretch",hide_index=True)
    st.download_button("📊 Baixar divergências em Excel",dataframe_excel_bytes(dfd,"Divergencias"),file_name=f"divergencias_conciliacao_{comp}.xlsx")
else:
    st.success("Nenhuma divergência linha a linha neste filtro.")

st.divider()
st.subheader("Revisão manual de lançamentos")
with session_scope() as s:
    q = select(Lancamento).where(Lancamento.competencia==comp, Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id)).order_by(Lancamento.data_movimento.desc())
    if conta_id:
        q = q.where(Lancamento.conta_financeira_id==conta_id)
    lancs = s.scalars(q).all()
    cons = {x.lancamento_id:x for x in s.scalars(select(Conciliacao).join(Lancamento, Lancamento.id==Conciliacao.lancamento_id).where(tenant_where(Lancamento.tesouraria_id))).all()}
rows = [{"id":l.id,"data":l.data_movimento,"natureza":l.natureza,"valor":float(l.valor),"especificacao":l.especificacao,"status_conciliacao":cons.get(l.id).status if cons.get(l.id) else "PENDENTE"} for l in lancs]
st.dataframe(rows,width="stretch",hide_index=True)
if rows:
    mp={f"#{r['id']} | {r['data']} | R$ {r['valor']:.2f} | {r['especificacao'][:45]}":r for r in rows}
    r=mp[st.selectbox("Revisar lançamento",list(mp))]
    status=st.selectbox("Situação",["CONCILIADO","DIVERGENTE","PENDENTE"])
    obs=st.text_input("Observação")
    if st.button("Salvar revisão"):
        from datetime import datetime
        with session_scope() as s:
            c=s.scalar(select(Conciliacao).where(Conciliacao.lancamento_id==r["id"]))
            if not c:
                c=Conciliacao(lancamento_id=r["id"]);s.add(c)
            c.status=status;c.observacao=obs;c.conciliado_por=u["id"];c.conciliado_em=datetime.utcnow() if status=="CONCILIADO" else None
            l=s.get(Lancamento,r["id"])
            if not l or l.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Lançamento não pertence à unidade ativa.")
            if status=="CONCILIADO" and l.status=="APROVADO":l.status="CONCILIADO"
        registrar_auditoria(u["id"],"CONCILIAR_MANUAL","conciliacoes",r["id"],novo={"status":status,"obs":obs})
        st.success("Atualizado.");st.rerun()
