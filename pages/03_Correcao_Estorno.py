import streamlit as st
from decimal import Decimal
from ui.common import require_login,topbar,code_options,brl
from ui.help_modulos import botao_ajuda
from services.financeiro import (
    listar_lancamentos,listar_codigos,corrigir_lancamento,
    estornar_lancamento,cancelar_lancamento,
)

u=require_login("CORRIGIR")
topbar("Correção / Estorno / Cancelamento","Somente lançamentos ativos aparecem aqui; cancelados ficam exclusivamente na Auditoria")
botao_ajuda("correcao")
rows=listar_lancamentos(limit=1000)
ids={f"#{r['id']} | {r['data']} | {r['codigo']} | {r['especificacao'][:55]} | {brl(r['valor'])}":r for r in rows}
if not ids:
    st.info("Sem lançamentos ativos para corrigir, estornar ou cancelar.")
    st.stop()
sel=st.selectbox("Lançamento",list(ids))
r=ids[sel]

st.markdown("### Ficha do lançamento")
a,b,c,d=st.columns(4)
a.metric("Valor",brl(r["valor"]))
b.write(f"**Data**\n\n{r['data'].strftime('%d/%m/%Y') if hasattr(r['data'],'strftime') else r['data']}")
c.write(f"**Código**\n\n{r['codigo'] or '—'}")
d.write(f"**Status**\n\n{r['status']}")
a,b,c=st.columns(3)
a.write(f"**Banco/Caixa**\n\n{r['B/C']}")
b.write(f"**Natureza**\n\n{r['natureza']}")
c.write(f"**Conta**\n\n{r['conta'] or '—'}")
st.write(f"**Especificação:** {r['especificacao']}")
st.write(f"**Favorecido:** {r['favorecido'] or '—'}  |  **Documento:** {r['documento'] or '—'}  |  **Origem:** {r['origem']}")
st.divider()

t1,t2,t3=st.tabs(["Corrigir","Estornar","Cancelar"])
with t1:
    cod=code_options(listar_codigos())
    with st.form("corr"):
        dt=st.date_input("Data",r["data"])
        bc=st.selectbox("B/C",["B","C"],index=0 if r["B/C"]=="B" else 1)
        nat=st.selectbox("Natureza",["ENTRADA","SAIDA"],index=0 if r["natureza"]=="ENTRADA" else 1)
        opts_code=["—"]+list(cod)
        current=next((k for k in cod if k.startswith((r["codigo"] or "")+" ")),"—")
        ck=st.selectbox("Código",opts_code,index=opts_code.index(current) if current in opts_code else 0)
        esp=st.text_area("Especificação",r["especificacao"])
        valor=st.number_input("Valor",min_value=0.01,value=max(0.01,float(r["valor"])),step=0.01,key=f"valor_corr_{r['id']}")
        mot=st.text_area("Motivo da correção")
        ok=st.form_submit_button("Confirmar correção",type="primary")
    if ok:
        if not mot.strip():
            st.error("Informe o motivo.")
        else:
            try:
                corrigir_lancamento(r["id"],u["id"],mot,data_movimento=dt,origem_bc=bc,natureza=nat,codigo_aplb_id=cod.get(ck) if ck!="—" else None,especificacao=esp,valor=Decimal(str(valor)))
                st.success("Lançamento corrigido com sucesso.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
with t2:
    mot=st.text_area("Motivo do estorno",key="mot_est")
    if st.button("Gerar estorno",type="primary"):
        try:
            rid=estornar_lancamento(r["id"],u["id"],mot)
            st.success(f"Estorno #{rid} criado com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
with t3:
    st.info("Cancelar remove o lançamento de todas as telas operacionais e de todos os cálculos. O histórico fica preservado somente na Auditoria.")
    with st.form("cancelar_lancamento_form"):
        mot_cancel=st.text_area("Motivo do cancelamento",placeholder="Ex.: lançamento de teste / lançamento digitado indevidamente")
        confirmar=st.checkbox("Confirmo que este lançamento deve deixar de participar da operação e dos resultados oficiais")
        cancelar=st.form_submit_button("Cancelar lançamento",type="primary")
    if cancelar:
        if not confirmar:
            st.error("Marque a confirmação antes de cancelar.")
        else:
            try:
                cancelar_lancamento(r["id"],u["id"],mot_cancel)
                st.success("Lançamento cancelado e removido das telas operacionais. O registro permanece apenas na Auditoria.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
