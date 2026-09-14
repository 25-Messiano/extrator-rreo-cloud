import streamlit as st
from datetime import date
from ui.common import require_login,topbar
from ui.help_modulos import botao_ajuda
from services.financeiro import fechar_mes,reabrir_mes
from services.administracao import diagnostico_fechamento,status_fechamentos

u=require_login("FECHAR");topbar("Fechamento Mensal","V15 • pré-fechamento, bloqueio da competência, snapshot e reabertura auditada")
botao_ajuda("fechamento")
hoje=date.today();c1,c2=st.columns(2);ano=int(c1.number_input("Ano",2020,2050,hoje.year));mes=int(c2.selectbox("Mês",list(range(1,13)),index=hoje.month-1))
diag=diagnostico_fechamento(ano,mes)
st.subheader(f"Competência {ano:04d}-{mes:02d}")
a,b,c,d=st.columns(4)
a.metric("Lançamentos",diag["quantidade_lancamentos"]);b.metric("Entradas",f"R$ {diag['total_entradas']:,.2f}");c.metric("Saídas",f"R$ {diag['total_saidas']:,.2f}");d.metric("Resultado",f"R$ {diag['resultado']:,.2f}")
if diag["status_periodo"]=="FECHADO":st.success("🔒 Competência FECHADA. Lançamentos, correções, cancelamentos e estornos deste período estão bloqueados.")
elif diag["bloqueios"]:
    st.error("Não pode fechar ainda: " + "; ".join(diag["bloqueios"]) + ".")
else:st.success("Pré-fechamento sem pendências impeditivas.")
if diag["movimentos_bancarios_nao_conciliados"]:st.warning(f"Há {diag['movimentos_bancarios_nao_conciliados']} movimento(s) bancário(s) ainda não conciliado(s). Revise a Conciliação antes de confirmar.")

t1,t2=st.tabs(["Fechar","Reabrir"])
with t1:
    st.caption("Ao fechar, os status APROVADO/CONCILIADO são preservados no snapshot e os lançamentos passam a FECHADO.")
    ciencia=st.checkbox("Confirmo que revisei lançamentos, extratos, entradas, saídas e conciliação desta competência.")
    if st.button("Fechar competência",type="primary",disabled=(not diag["pode_fechar"] or not ciencia)):
        try:fechar_mes(ano,mes,u["id"]);st.success("Competência fechada e snapshot registrado.");st.rerun()
        except Exception as e:st.error(str(e))
with t2:
    st.caption("Reabertura é exclusiva do Administrador, exige motivo e fica registrada na Auditoria. Os status anteriores são restaurados pelo snapshot.")
    if u.get("perfil")!="ADMINISTRADOR":
        st.info("Seu perfil pode consultar/fechar conforme permissão, mas somente Administrador pode reabrir uma competência fechada.")
    else:
        motivo=st.text_area("Motivo obrigatório da reabertura")
        if st.button("Reabrir competência",disabled=(diag["status_periodo"]!="FECHADO" or not motivo.strip())):
            try:reabrir_mes(ano,mes,u["id"],motivo);st.success("Competência reaberta e status restaurados.");st.rerun()
            except Exception as e:st.error(str(e))
st.subheader("Histórico de fechamentos");st.dataframe(status_fechamentos(),width="stretch",hide_index=True)
