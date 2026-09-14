from pathlib import Path
import pandas as pd
import streamlit as st

from ui.common import require_login, require_admin, topbar, brl
from services.tenancy import listar_tesourarias, app_version
from services.migracao_tesouraria import (
    previsualizar_migracao,
    gerar_backup_pre_migracao,
    executar_migracao,
)

user = require_login("USUARIOS")
require_admin(user)
topbar("Migração de Dados da Central", "Transfira os dados operacionais legados para a primeira Tesouraria Filiada")

st.warning(
    "A CENTRAL é somente administração e auditoria. Ela não deve possuir lançamentos, contas, saldos, "
    "extratos, fechamentos ou prestações de uma filial. Esta rotina transfere a propriedade dos dados, "
    "sem recriar lançamentos e sem alterar valores."
)
st.info(
    f"Código-base {app_version()}: a migração muda somente a unidade proprietária dos dados. "
    "Todas as filiais continuam usando a mesma estrutura e a mesma versão do sistema."
)

filiais = [
    x for x in listar_tesourarias(None, incluir_inativas=False)
    if x.get("tipo") == "FILIADA" and x.get("ambiente") == "PRODUCAO"
]

if not filiais:
    st.error("Nenhuma Tesouraria Filiada de PRODUÇÃO está cadastrada. Cadastre a filial antes de migrar.")
    st.stop()

destino = st.selectbox(
    "Tesouraria que receberá os dados antigos *",
    filiais,
    format_func=lambda x: f"{x['codigo']} — {x['nome']} (ID {x['id']})",
)

try:
    previa = previsualizar_migracao(destino["id"])
except Exception as e:
    st.error(str(e)); st.stop()

st.subheader("1. Conferência antes da migração")
c1, c2, c3 = st.columns(3)
c1.metric("Origem", "CENTRAL")
c2.metric("Destino", destino["codigo"])
c3.metric("Registros diretos pendentes", previa["total_registros_diretos"])

nomes = {
    "contas_financeiras": "Contas financeiras",
    "saldos_iniciais": "Saldos iniciais",
    "centros_custo": "Centros de custo",
    "lancamentos": "Lançamentos",
    "fluxo_projetado": "Fluxo projetado",
    "patrimonio": "Patrimônio",
    "importacoes_extrato": "Extratos/importações",
    "fechamentos_mensais": "Fechamentos mensais",
    "prestacoes_contas": "Prestações de contas",
}
linhas=[]
for tabela, qtd in previa["contagens"].items():
    linhas.append({
        "Grupo de dados": nomes.get(tabela, tabela),
        "Na CENTRAL": qtd,
        "Já existentes no destino": previa["destino_existente"].get(tabela, 0),
    })
st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)

st.caption(
    f"Registros vinculados que acompanham os pais automaticamente: "
    f"{previa['itens_conferencia_vinculados']} itens de extrato, "
    f"{previa['conciliacoes_vinculadas']} conciliações e "
    f"{previa['carga_inicial_vinculada']} itens da carga inicial."
)

if previa["totais_lancamentos"]:
    st.markdown("#### Totais financeiros que serão preservados")
    tf=[]
    for r in previa["totais_lancamentos"]:
        tf.append({
            "Origem": "Banco" if r["origem"] == "B" else "Caixa",
            "Natureza": r["natureza"],
            "Quantidade": r["quantidade"],
            "Total": brl(r["total"]),
        })
    st.dataframe(pd.DataFrame(tf), width="stretch", hide_index=True)

if previa["conflitos_fechamento"] or previa["conflitos_prestacao"]:
    st.error(
        f"Migração bloqueada: há {previa['conflitos_fechamento']} conflito(s) de fechamento e "
        f"{previa['conflitos_prestacao']} conflito(s) de prestação no destino."
    )
    st.stop()

if previa["total_registros_diretos"] == 0:
    st.success("A CENTRAL já está sem registros operacionais pendentes. Nenhuma migração é necessária.")
    st.stop()

st.subheader("2. Backup obrigatório")
st.write("Antes da migração, gere e valide um backup do estado atual.")
if st.button("💾 Gerar backup pré-migração", type="primary"):
    try:
        b = gerar_backup_pre_migracao()
        st.session_state["backup_migracao_v25"] = b
        st.success(f"Backup criado e validado: {b['nome']}")
    except Exception as e:
        st.error(str(e))

backup = st.session_state.get("backup_migracao_v25")
if backup:
    p = Path(backup["path"])
    if p.exists():
        st.success(f"Backup pronto: {backup['nome']} — {backup['validacao']['total_registros']} registros no pacote.")
        st.download_button(
            "⬇️ Baixar backup antes de migrar",
            data=p.read_bytes(),
            file_name=p.name,
            mime="application/zip",
        )
    else:
        st.warning("O arquivo de backup não está mais disponível nesta instância. Gere outro antes de migrar.")
        backup = None

st.subheader("3. Confirmação e execução")
frase = f"MIGRAR {destino['codigo']}"
st.caption(f"Digite exatamente **{frase}**. A operação é transacional: se houver erro, nenhuma tabela é migrada parcialmente.")
confirmacao = st.text_input("Confirmação", placeholder=frase)
confirmar_checkbox = st.checkbox(
    f"Confirmo que {destino['nome']} é a filial correta para receber os dados operacionais atualmente vinculados à CENTRAL."
)

if st.button("🔁 Executar migração definitiva", type="primary", disabled=not(bool(backup) and confirmar_checkbox)):
    try:
        resultado = executar_migracao(
            destino["id"], confirmacao, user["id"], backup_path=backup["path"]
        )
        st.session_state["resultado_migracao_v25"] = resultado
        st.success(
            f"Migração concluída. Os dados operacionais agora pertencem a {resultado['destino']} ({resultado['destino_codigo']})."
        )
        st.balloons()
    except Exception as e:
        st.error(str(e))

resultado = st.session_state.get("resultado_migracao_v25")
if resultado:
    st.markdown("### Resultado da última migração")
    st.json({
        "destino": resultado["destino"],
        "codigo": resultado["destino_codigo"],
        "registros_alterados": resultado["alterados"],
        "backup": Path(resultado["backup"]).name,
        "executado_em": resultado["executado_em"],
    })
    st.info(
        "Agora selecione a filial no campo 'Unidade operacional ativa' e confira Dashboard, Banco, Caixa, "
        "Extratos e relatórios. A CENTRAL permanece apenas como camada administrativa/auditora."
    )
