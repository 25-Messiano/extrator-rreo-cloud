import streamlit as st
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_centros_custo,salvar_centro_custo
u=require_login("CONFIGURAR");topbar("Centros de Custo","Cadastro livre para classificar lançamentos sem alterar códigos contábeis")
botao_ajuda("centros")
@st.dialog("Novo centro de custo")
def novo():
    codigo=st.text_input("Código");nome=st.text_input("Nome");desc=st.text_area("Descrição")
    if st.button("Salvar",type="primary"):
        try: salvar_centro_custo(codigo,nome,desc,usuario_id=u["id"]);st.success("Centro de custo cadastrado.")
        except Exception as e:st.error(str(e))
if st.button("+ Novo centro de custo",type="primary"):novo()
rows=listar_centros_custo(False);st.dataframe(rows,width="stretch",hide_index=True)
if rows:
    mp={f"{x['codigo']} — {x['nome']}":x for x in rows};sel=mp[st.selectbox("Editar",list(mp))]
    with st.form("edit_cc"):
        codigo=st.text_input("Código",sel["codigo"]);nome=st.text_input("Nome",sel["nome"]);desc=st.text_area("Descrição",sel["descricao"]);ativo=st.checkbox("Ativo",sel["ativo"])
        if st.form_submit_button("Salvar alterações"):
            try:salvar_centro_custo(codigo,nome,desc,sel["id"],ativo,u["id"]);st.success("Atualizado.");st.rerun()
            except Exception as e:st.error(str(e))
