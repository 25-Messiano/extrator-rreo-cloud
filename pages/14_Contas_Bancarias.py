import streamlit as st
from datetime import date
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.financeiro import listar_contas,salvar_conta
from services.administracao import atualizar_conta,salvar_saldo_inicial,listar_saldos_iniciais
u=require_login("CADASTROS");topbar("Contas Financeiras","Cadastro, edição, ativação e saldo inicial de Banco/Caixa")
botao_ajuda("contas")
@st.dialog("Nova conta")
def nova():
    nome=st.text_input("Nome da conta");tipo=st.selectbox("Tipo",["BANCO","CAIXA"]);banco=st.text_input("Banco");ag=st.text_input("Agência");conta=st.text_input("Conta")
    if st.button("Salvar",type="primary"):
        try:salvar_conta(nome,tipo,banco,ag,conta,u["id"]);st.success("Conta cadastrada.")
        except Exception as e:st.error(str(e))
if st.button("+ Nova conta",type="primary"):nova()
rows=listar_contas(False);st.dataframe(rows,width="stretch",hide_index=True)
if rows:
    mp={f"#{x['id']} | {x['nome']} ({x['tipo']})":x for x in rows};x=mp[st.selectbox("Administrar conta",list(mp))]
    with st.form("editar_conta"):
        nome=st.text_input("Nome",x["nome"]);tipo=st.selectbox("Tipo",["BANCO","CAIXA"],index=0 if x["tipo"]=="BANCO" else 1);banco=st.text_input("Banco",x.get("banco") or "");ag=st.text_input("Agência",x.get("agencia") or "");cc=st.text_input("Conta",x.get("conta") or "");ativo=st.checkbox("Ativa",x["ativo"])
        if st.form_submit_button("Salvar alterações"):
            atualizar_conta(x["id"],nome,tipo,banco,ag,cc,ativo,u["id"]);st.success("Conta atualizada.");st.rerun()
    st.subheader("Saldo inicial / abertura")
    c1,c2,c3=st.columns(3);dt=c1.date_input("Data de referência",date(date.today().year,1,1));valor=c2.number_input("Valor",step=0.01);obs=c3.text_input("Observação")
    if st.button("Salvar saldo inicial"):salvar_saldo_inicial(x["id"],dt,valor,obs,u["id"]);st.success("Saldo inicial salvo.")
st.subheader("Histórico de saldos iniciais");st.dataframe(listar_saldos_iniciais(),width="stretch",hide_index=True)
