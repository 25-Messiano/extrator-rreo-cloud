import streamlit as st

from ui.common import brl, db_badge, require_login, tenant_identity
from services.financeiro import saldos, listar_lancamentos
from services.security import permitido
from services.tenancy import listar_tesourarias, app_version
from services.prestacoes import listar_prestacoes
from services.email_service import email_configurado
from services.administracao import listar_usuarios

st.set_page_config(page_title="TESOURARIA APLB", page_icon="💰", layout="wide")

OBJETIVO_SISTEMA = (
    "🎯 OBJETIVO — Sistema completo para gestão financeira, contábil, patrimonial e de relatórios da APLB, "
    "com controle de lançamentos, Banco/Caixa, códigos oficiais, DRE, importação inteligente de extratos, "
    "conciliação, fluxo de caixa realizado e projetado, patrimônio, usuários, auditoria e backup seguro no Cloud."
)
user=require_login("CONSULTAR")

# V25.6: a pagina inicial muda integralmente conforme o contexto autenticado.
# ADMINISTRADOR ve somente a Central; perfis de filial/teste veem somente a
# unidade operacional em que autenticaram.
if st.session_state.get("portal_profile") == "ADMINISTRADOR":
    st.title("CENTRAL DAS TESOURARIAS")
    st.caption(f"Auditoria, administração e supervisao das unidades · Código-base {app_version()}")
    st.info(OBJETIVO_SISTEMA)
    rows=listar_tesourarias(None, True)
    filiais=[x for x in rows if x.get("tipo")=="FILIADA" and x.get("ambiente")=="PRODUCAO"]
    testes=[x for x in rows if x.get("ambiente")=="TESTE"]
    prest=listar_prestacoes()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Filiais cadastradas",len(filiais))
    c2.metric("Filiais ativas",len([x for x in filiais if x.get("ativa")]))
    c3.metric("Ambientes de teste",len(testes))
    c4.metric("Prestações pendentes",len([x for x in prest if x.get("status") in ("ENVIADA","EM_AUDITORIA")]))
    usuarios=listar_usuarios()
    sem_email=[x for x in usuarios if not (x.get("email") or "").strip()]
    c5,c6=st.columns(2)
    c5.metric("Usuários sem e-mail de login", len(sem_email))
    c6.metric("Recuperação por e-mail", "ATIVA" if email_configurado() else "CONFIGURAR SMTP")
    if sem_email:
        st.warning("Existem contas antigas sem e-mail. Cada usuário deve usar ‘Primeiro acesso / ativar e-mail’ uma única vez antes de usar o login V26.")
    if not email_configurado():
        st.warning("O login por e-mail funciona, mas o envio de recuperação ainda depende da configuração SMTP no Render. Enquanto o SMTP não estiver configurado, ‘Esqueci minha senha’ não enviará mensagens.")
    st.info("A Central não possui saldo, lançamentos, extratos ou movimento financeiro próprio. Para operar uma filial, troque de usuário e autentique uma conta vinculada à unidade.")
    st.subheader("Ações da Central")
    c1,c2,c3,c4=st.columns(4)
    c1.page_link("pages/30_Central_Tesourarias.py",label="🏢 Tesourarias Filiadas",width="stretch")
    c2.page_link("pages/31_Prestacoes_Contas.py",label="📥 Prestações de Contas",width="stretch")
    c3.page_link("pages/19_Usuarios_Permissoes.py",label="👥 Usuários e Permissões",width="stretch")
    c4.page_link("pages/36_Diagnostico_Isolamento.py",label="🛡️ Diagnóstico",width="stretch")
    st.stop()

tenant=st.session_state.get("tesouraria") or {}
ident=tenant_identity(tenant)
st.title(ident["titulo_operacional"])
st.caption(ident["linha_identificacao"])
st.caption("Gestão financeira, tesouraria, conciliação, relatórios, fluxo de caixa e patrimonio")
st.info(OBJETIVO_SISTEMA)

s=saldos()
c1,c2,c3,c4=st.columns(4)
c1.metric("Saldo Banco",brl(s.get("B",0)))
c2.metric("Saldo Caixa",brl(s.get("C",0)))
c3.metric("Saldo Geral",brl(s.get("GERAL",0)))
c4.metric("Usuario",user.get("nome",""))

db_badge()

st.subheader("Atalhos")
atalhos=[]
if permitido(user["perfil"],"LANCAR",user["id"]):
    atalhos.append(("pages/02_Lancamentos.py","➕ Novo lançamento"))
if permitido(user["perfil"],"IMPORTAR",user["id"]):
    atalhos.append(("pages/06_Extratos_Bancarios.py","🏦 Importar extrato"))
if permitido(user["perfil"],"CONFERIR",user["id"]):
    atalhos.append(("pages/08_Conferencia.py","✅ Conferência"))
if permitido(user["perfil"],"RELATORIOS",user["id"]):
    atalhos.append(("pages/23_Relatorio_Movimento_Financeiro.py","📊 Relatórios"))
if atalhos:
    cols=st.columns(min(4,len(atalhos)))
    for col,(pagina,label) in zip(cols,atalhos):
        col.page_link(pagina,label=label,width="stretch")
else:
    st.caption("Seu perfil nao possui atalhos operacionais.")

st.subheader("Lançamentos recentes")
rows=listar_lancamentos(limit=10)
if rows: st.dataframe(rows,width="stretch",hide_index=True)
else: st.info("Ainda nao ha lançamentos oficiais.")
