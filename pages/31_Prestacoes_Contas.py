import streamlit as st
from ui.common import require_login, topbar, brl
from services.prestacoes import criar_prestacao, listar_prestacoes, decidir_prestacao

user=require_login("RELATORIOS")
ten=st.session_state.get("tesouraria") or {}
topbar("Prestações de Contas","Envio pelas tesourarias e decisão formal da Central de Auditoria")
if ten.get("ambiente")=="TESTE": st.warning("Você está no AMBIENTE DE TESTE. Nada daqui representa prestação oficial.")
if ten.get("tipo") != "CENTRAL" and ten.get("ambiente")=="PRODUCAO":
    st.subheader("Enviar nova prestação da unidade ativa")
    with st.form("enviar_prestacao"):
        comp=st.text_input("Competência (AAAA-MM)")
        obs=st.text_area("Observação do envio")
        ok=st.form_submit_button("Enviar para a Central",type="primary")
    if ok:
        try:
            rid=criar_prestacao(ten['id'],comp,user['id'],obs); st.success(f"Prestação enviada para auditoria (protocolo {rid})."); st.rerun()
        except Exception as e: st.error(str(e))

st.subheader("Histórico")
central=user.get("perfil") in ("ADMINISTRADOR","AUDITORIA")
rows=listar_prestacoes(None if central else ten.get("id"))
if rows: st.dataframe(rows,width="stretch",hide_index=True)
else: st.info("Nenhuma prestação cadastrada.")
if central and rows:
    st.subheader("Analisar prestação")
    pend=[x for x in rows if x['status'] in ('ENVIADA','EM_AUDITORIA')]
    if pend:
        item=st.selectbox("Prestação",pend,format_func=lambda x:f"#{x['id']} - {x['tesouraria']} - {x['competencia']} v{x['versao']}")
        decisao=st.selectbox("Decisão",["APROVADA","DEVOLVIDA","REJEITADA"])
        parecer=st.text_area("Parecer / justificativa")
        if st.button("Registrar decisão",type="primary"):
            try: decidir_prestacao(item['id'],decisao,parecer,user['id']); st.success("Decisão registrada com trilha de auditoria."); st.rerun()
            except Exception as e: st.error(str(e))
    else: st.success("Não há prestações aguardando decisão.")
