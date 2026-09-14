import streamlit as st
from ui.common import require_login, topbar, unit_banner
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_codigos, salvar_codigo, definir_codigo_ativo

u=require_login("CADASTROS")
ten=st.session_state.get("tesouraria") or {}
topbar("Plano de Codigos", "Cada filial administra seu proprio plano de codigos. A estrutura da DRE e editada somente pela Central.")
botao_ajuda("codigos")
unit_banner(compact=True)

@st.dialog("Novo codigo")
def novo_codigo():
    codigo=st.text_input("Codigo",placeholder="Ex.: 0703")
    desc=st.text_input("Descricao")
    c1,c2=st.columns(2)
    pe=c1.checkbox("Permitir em ENTRADA / Receita",value=False)
    ps=c2.checkbox("Permitir em SAIDA / Despesa",value=True)
    gp=st.checkbox("Gerar/identificar patrimônio", value=False, help="Quando marcado, saídas com este código aparecem no módulo Patrimônio para cadastro do bem. Não cria o bem automaticamente.")
    obs=st.text_area("Observacao")
    if st.button("Salvar codigo",type="primary",width="stretch"):
        try:
            rid=salvar_codigo(codigo,desc,observacao=obs,usuario_id=u["id"],permite_entrada=pe,permite_saida=ps,gera_patrimonio=gp)
            st.success(f"Codigo #{rid} criado nesta filial.");st.rerun()
        except Exception as exc:st.error(str(exc))

if st.button("+ Novo codigo",type="primary"):novo_codigo()
rows=listar_codigos(False)
st.caption("Estes codigos pertencem exclusivamente a esta unidade. Outra filial pode usar codigos diferentes ou o mesmo numero com outra descricao.")
st.dataframe(rows,width="stretch",hide_index=True)
if rows:
    labels={f"{c['codigo']} - {c['descricao']}":c for c in rows}
    c=labels[st.selectbox("Codigo para administrar",list(labels))]
    with st.form("editar_codigo"):
        a,b=st.columns(2)
        codigo=a.text_input("Codigo",value=c["codigo"]);desc=b.text_input("Descricao",value=c["descricao"])
        e1,e2=st.columns(2)
        pe=e1.checkbox("Permitir em ENTRADA / Receita",value=bool(c.get("permite_entrada")))
        ps=e2.checkbox("Permitir em SAIDA / Despesa",value=bool(c.get("permite_saida")))
        gp=st.checkbox("Gerar/identificar patrimônio", value=bool(c.get("gera_patrimonio")), help="As saídas com este código serão oferecidas no módulo Patrimônio para cadastro do bem.")
        obs=st.text_area("Observacao",value=c.get("observacao") or "")
        if st.form_submit_button("Salvar alteracoes",type="primary"):
            try:
                salvar_codigo(codigo,desc,observacao=obs,codigo_id=c["id"],usuario_id=u["id"],ativo=c["ativo"],permite_entrada=pe,permite_saida=ps,gera_patrimonio=gp)
                st.success("Codigo atualizado somente nesta filial.");st.rerun()
            except Exception as exc:st.error(str(exc))
    acao="Inativar codigo" if c["ativo"] else "Reativar codigo"
    if st.button(acao):
        definir_codigo_ativo(c["id"],not c["ativo"],u["id"]);st.rerun()

st.info("A filial administra o seu Plano de Codigos. O enquadramento desses codigos na DRE oficial e feito exclusivamente pela Central de Auditoria.")
