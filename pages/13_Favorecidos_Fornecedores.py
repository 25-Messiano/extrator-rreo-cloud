import streamlit as st
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_favorecidos,salvar_favorecido
u=require_login("CADASTROS");topbar("Pessoas e Entidades","Cadastro único para colaboradores, fornecedores, prestadores e demais favorecidos")
botao_ajuda("favorecidos")
@st.dialog("Nova pessoa / entidade")
def novo():
    tipo=st.selectbox("Tipo",["COLABORADOR","FORNECEDOR","PRESTADOR","ENTIDADE","SINDICATO/NUCLEO","ORGAO_PUBLICO","OUTRO"])
    nome=st.text_input("Nome / Razão social *");doc=st.text_input("CPF/CNPJ/Documento")
    c1,c2=st.columns(2);email=c1.text_input("E-mail");tel=c2.text_input("Telefone")
    pix=st.text_input("Chave PIX")
    b1,b2,b3=st.columns(3);banco=b1.text_input("Banco");agencia=b2.text_input("Agência");conta=b3.text_input("Conta")
    obs=st.text_area("Observação")
    if st.button("Salvar cadastro",type="primary"):
        try:
            rid=salvar_favorecido(nome,doc,tipo,email,tel,obs,u["id"],pix,banco,agencia,conta);st.success(f"Cadastro #{rid} salvo. O código individual foi gerado automaticamente.");st.rerun()
        except Exception as exc:st.error(str(exc))
if st.button("+ Nova pessoa / entidade",type="primary"):novo()
st.info("O código deste cadastro identifica QUEM participa do movimento. Ele não substitui o Código APLB/DRE, que identifica a natureza contábil.")
st.dataframe(listar_favorecidos(False),width="stretch",hide_index=True)
