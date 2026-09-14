import streamlit as st
from ui.common import require_login,topbar,db_badge
from ui.help_modulos import botao_ajuda
from config.settings import settings
from services.administracao import listar_configs,set_config
u=require_login("CONFIGURAR");topbar("Configurações","Parâmetros não secretos administráveis pela interface")
botao_ajuda("config")
ten=st.session_state.get("tesouraria") or {}
if ten.get("ambiente")=="TESTE":
    st.warning("Configurações do sistema são globais. No Ambiente de Teste esta página fica bloqueada para evitar alterações que afetem todas as filiais.")
    st.stop()
db_badge();st.write({"ambiente":settings.app_env,"cloud_backup_configurado":bool(settings.cloud_backup_bucket),"alerta_programador_configurado":bool(settings.programador_alert_webhook_url),"ia_configurada":bool(settings.openai_api_key)})
st.caption("Senhas, tokens e credenciais continuam exclusivamente nas Environment Variables do Render.")
st.subheader("Parâmetros do sistema")
chave=st.text_input("Chave",placeholder="ex.: cidade_relatorio");valor=st.text_area("Valor")
if st.button("Salvar parâmetro",type="primary",disabled=not chave.strip()):set_config(chave.strip(),valor,u["id"]);st.success("Configuração salva.")
st.dataframe(listar_configs(),width="stretch",hide_index=True)
