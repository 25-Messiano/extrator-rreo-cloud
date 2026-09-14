import streamlit as st
from pathlib import Path

from ui.common import require_login, topbar
from ui.help_modulos import botao_ajuda
from services.backup import (
    gerar_snapshot_config,
    gerar_backup_completo,
    status_ultimo_backup,
    validar_backup,
    testar_restauracao,
    restaurar_backup_producao,
)
from config.settings import settings

u = require_login("BACKUP")
topbar("Backup / Recuperação", "Backup integral versionado + validação + teste de restauração")
botao_ajuda("backup")

st.subheader("Proteção dos dados")
ultimo = status_ultimo_backup()
if ultimo:
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Último backup", ultimo.get("gerado_em", "-")[:19].replace("T"," "))
    c2.metric("Registros", ultimo.get("total_registros", 0))
    c3.metric("Tamanho", f"{ultimo.get('tamanho_bytes',0)/1024/1024:.2f} MB")
    c4.metric("Cloud externo", "OK" if ultimo.get("cloud_ok") else "Não configurado/Falhou")
    st.caption(ultimo.get("cloud_mensagem", ""))
else:
    st.warning("Ainda não há backup V14 registrado nesta instância.")

c1, c2 = st.columns(2)
if c1.button("Gerar snapshot estrutural"):
    p = gerar_snapshot_config()
    st.success(f"Snapshot gerado: {p.name}")
    st.download_button("Baixar snapshot", p.read_bytes(), p.name, mime="application/json")

if c2.button("Gerar backup completo agora", type="primary"):
    with st.spinner("Gerando pacote integral e checksums..."):
        p = gerar_backup_completo()
    st.success(f"Backup concluído: {p.name}")
    st.download_button("Baixar backup completo", p.read_bytes(), p.name, mime="application/zip")

st.info(
    "O backup diário é gerado automaticamente. No Render, o disco do serviço não deve ser tratado como cofre permanente. "
    "Para cópia externa automática, configure CLOUD_BACKUP_BUCKET, CLOUD_BACKUP_ACCESS_KEY e CLOUD_BACKUP_SECRET_KEY "
    "(S3/R2/armazenamento compatível)."
)
st.write({"cloud_bucket_configurado": bool(settings.cloud_backup_bucket)})

st.divider()
st.subheader("Validar / testar recuperação")
up = st.file_uploader("Selecione um backup V14 (.zip)", type=["zip"], key="backup_restore")
if up:
    data = up.getvalue()
    if st.button("Validar integridade"):
        try:
            r = validar_backup(data)
            st.success(f"Backup íntegro. {r['total_registros']} registros no pacote.")
            st.json(r["contagens"], expanded=False)
        except Exception as exc:
            st.error(str(exc))
    if st.button("Simular restauração (não altera produção)"):
        try:
            with st.spinner("Restaurando em banco temporário isolado..."):
                r = testar_restauracao(data)
            st.success(r["mensagem"])
            st.write({"registros_restaurados": r["total_registros"]})
        except Exception as exc:
            st.error(str(exc))

    with st.expander("Recuperação de desastre — restauração real", expanded=False):
        st.error("Esta operação substitui os dados do banco atual pelo conteúdo do backup. Use apenas em recuperação de desastre.")
        confirm = st.text_input("Digite exatamente: RESTAURAR PRODUCAO", key="restore_confirm")
        if st.button("Restaurar banco de produção", type="primary"):
            try:
                r = restaurar_backup_producao(data, confirm)
                st.success(f"Restauração concluída: {r['total_registros']} registros.")
            except Exception as exc:
                st.error(str(exc))

st.divider()
for f in [Path("docs/RECOVERY_MASTER.txt"), Path("tesouraria_aplb_recovery_master.py")]:
    if f.exists():
        st.download_button(f"Baixar {f.name}", f.read_bytes(), f.name)
