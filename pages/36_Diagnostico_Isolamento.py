import pandas as pd
import streamlit as st
from ui.common import require_login, require_admin, topbar
from services.tenancy import diagnostico_isolamento

u=require_login("AUDITORIA")
if u.get("perfil") not in ("ADMINISTRADOR","AUDITORIA"):
    st.error("Acesso restrito à Central de Auditoria."); st.stop()
topbar("Diagnóstico de Isolamento","Conferência de separação entre Central, Ambiente de Teste e tesourarias filiadas")

d=diagnostico_isolamento()
if d["ok"]:
    st.success("Estrutura de propriedade direta sem inconsistências: nenhum registro operacional órfão e a CENTRAL permanece sem movimento próprio.")
else:
    for p in d["problemas"]: st.error(p)

cols=["codigo","nome","tipo","ambiente","lancamentos","contas_financeiras","saldos_iniciais","favorecidos","centros_custo","fluxo_projetado","patrimonio","importacoes_extrato","fechamentos_mensais","prestacoes_contas"]
rows=[]
for x in d["unidades"]:
    rows.append({
        "Código":x["codigo"],"Unidade":x["nome"],"Tipo":x["tipo"],"Ambiente":x["ambiente"],
        "Lançamentos":x["lancamentos"],"Contas":x["contas_financeiras"],"Saldos iniciais":x["saldos_iniciais"],
        "Favorecidos":x["favorecidos"],"Centros":x["centros_custo"],"Fluxo projetado":x["fluxo_projetado"],
        "Patrimônio":x["patrimonio"],"Importações":x["importacoes_extrato"],"Fechamentos":x["fechamentos_mensais"],"Prestações":x["prestacoes_contas"],
    })
st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
st.caption("A CENTRAL deve permanecer zerada nas colunas operacionais. O AMBIENTE DE TESTE pode ter dados próprios de simulação, mas eles não podem aparecer nas filiais de PRODUÇÃO.")
if d["orfaos"]:
    st.warning("Registros sem unidade proprietária: "+str(d["orfaos"]))
