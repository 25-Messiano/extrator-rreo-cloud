import pandas as pd
import streamlit as st
from ui.common import require_login, topbar
from ui.help_modulos import botao_ajuda
from services.administracao import monitoramento_resumo

u=require_login("MONITORAR")
topbar("Monitoramento","Saúde do sistema, segurança, continuidade e pendências — somente leitura")
botao_ajuda("monitor")
r=monitoramento_resumo()

st.subheader("Painel de saúde")
icons={"NORMAL":"🟢","ATENCAO":"🟡","CRITICO":"🔴"}
rotulos={"NORMAL":"Normal","ATENCAO":"Atenção","CRITICO":"Crítico"}
cols=st.columns(len(r["saude"]))
for col,(nome,item) in zip(cols,r["saude"].items()):
    status=item.get("status") or ""
    col.markdown(f"**{nome}**")
    col.markdown(f"### {icons.get(status,'⚪')} {rotulos.get(status,status.title())}")
    col.caption(str(item.get("detalhe") or ""))

st.caption("🟢 Normal = operacional • 🟡 Atenção = requer acompanhamento • 🔴 Crítico = requer ação do administrador")

st.subheader("Atividade e operação")
c=st.columns(4)
c[0].metric("Lançamentos oficiais",r["lancamentos_oficiais"])
c[1].metric("Pendências de conferência",r["itens_conferencia_pendentes"])
c[2].metric("Importações em conferência",r["importacoes_em_conferencia"])
c[3].metric("Usuários ativos",r["usuarios_ativos"])
c=st.columns(4)
c[0].metric("Acessos 24h",r["acessos_24h"])
c[1].metric("Falhas de login 24h",r["falhas_login_24h"])
c[2].metric("Conciliações registradas",r["conciliacoes_concluidas"])
c[3].metric("Competências fechadas",r["fechamentos_ativos"])

st.subheader("Atenções do Administrador")
if not r["alertas"]:
    st.success("Nenhuma atenção operacional relevante neste momento.")
else:
    for a in r["alertas"]:
        texto=f'**{a["titulo"]}** — {a["detalhe"]}'
        if a["nivel"]=="CRITICO": st.error(texto)
        else: st.warning(texto)

st.subheader("Histórico de acessos e segurança")
c=st.columns(3)
c[0].metric("Acessos 7 dias",r["acessos_7d"]); c[0].caption(f'Falhas: {r["falhas_login_7d"]}')
c[1].metric("Acessos 30 dias",r["acessos_30d"]); c[1].caption(f'Falhas: {r["falhas_login_30d"]}')
c[2].metric("IA — itens classificados",r["itens_classificados_ia"]); c[2].caption("Indicador de uso; IA não decide conciliação")
if r["historico_7d"]:
    df=pd.DataFrame(r["historico_7d"]).set_index("dia")
    st.bar_chart(df)
else:
    st.caption("Ainda não há histórico suficiente para o gráfico de 7 dias.")

st.subheader("Continuidade")
c=st.columns(3)
ub=r.get("ultimo_backup") or {}
c[0].metric("Último backup",(ub.get("gerado_em") or "Não localizado")[:19].replace("T"," "))
c[1].metric("Último fechamento",r.get("ultimo_fechamento") or "Nenhum")
c[2].metric("Cancelados (auditoria)",r["cancelados"])
if ub:
    st.caption(f'Backup: {ub.get("total_registros",0)} registros • {ub.get("tamanho_bytes",0)/1024/1024:.2f} MB • Cloud externo: {"OK" if ub.get("cloud_ok") else "não confirmado"}.')

with st.expander("Diagnóstico técnico",expanded=False):
    st.caption("Visível apenas a perfis com permissão MONITORAR. Nenhuma ação financeira é executada nesta página.")
    st.json(r,expanded=False)
