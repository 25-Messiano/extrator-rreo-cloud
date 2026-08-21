from __future__ import annotations

from datetime import datetime

import streamlit as st

from integrations.google_storage import (
    BUCKET_NAME,
    download_bytes,
    health_check,
    list_pdfs,
    list_results,
    list_states,
)


# ==========================================================
# Configuração da página
# ==========================================================

st.set_page_config(
    page_title="Arquivos Cloud",
    page_icon="☁️",
    layout="wide",
)


# ==========================================================
# Título da página
# ==========================================================

st.title("☁️ Arquivos do Cloud Storage")
st.caption(f"Bucket configurado: `{BUCKET_NAME}`")


# ==========================================================
# Botão de teste da conexão
# ==========================================================

if st.button("Testar conexão", type="primary"):
    result = health_check()

    if result.get("ok"):
        st.success(f"Conectado ao bucket: {result['bucket']}")
    else:
        st.error(result.get("message", "Falha desconhecida."))


# ==========================================================
# Verificação da conexão
# ==========================================================

status = health_check()

if not status.get("ok"):
    st.warning(
        "A listagem ficará disponível após configurar "
        "as credenciais do Cloud Storage."
    )
    st.stop()


# ==========================================================
# Acessos rápidos + abas
# ==========================================================

st.markdown("### 🔗 Acessos rápidos")
link_github, link_render, link_cloud = st.columns(3)

with link_github:
    st.link_button(
        "🐙 Abrir GitHub do projeto",
        "https://github.com/25-Messiano/extrator-rreo-cloud/tree/main?search=1",
        use_container_width=True,
    )

with link_render:
    st.link_button(
        "🚀 Abrir painel do Render",
        "https://dashboard.render.com/web/srv-d9g2kdflk1mc739qi49g",
        use_container_width=True,
    )

with link_cloud:
    st.link_button(
        "📤 Enviar novos PDFs",
        (
            "https://console.cloud.google.com/storage/browser/"
            "maestro-rreo-arquivos"
            "?project=maestro-rreo"
        ),
        use_container_width=True,
    )

# ==========================================================
# Links externos de consulta (somente informativos)
# ==========================================================

consulta_siop, consulta_fnde, consulta_tcm = st.columns(3)

with consulta_siop:
    st.markdown(
        "**SIOP**  \n"
        "[https://www.fnde.gov.br/siope/relatorioRREOMunicipal2006.do]"
        "(https://www.fnde.gov.br/siope/relatorioRREOMunicipal2006.do)"
    )

with consulta_fnde:
    st.markdown(
        "**FNDE**  \n"
        "[https://www.fnde.gov.br/sigefweb/index.php/liberacoes]"
        "(https://www.fnde.gov.br/sigefweb/index.php/liberacoes)"
    )

with consulta_tcm:
    st.markdown(
        "**TCM**  \n"
        "[https://e.tcm.ba.gov.br/epp/ConsultaPublica/listView.seam]"
        "(https://e.tcm.ba.gov.br/epp/ConsultaPublica/listView.seam)"
    )

_, consulta_bb, _ = st.columns(3)
with consulta_bb:
    st.markdown(
        "**BB - BANCO DO BRASIL**  \n"
        "[https://demonstrativos.apps.bb.com.br/arrecadacao-federal]"
        "(https://demonstrativos.apps.bb.com.br/arrecadacao-federal)"
    )

st.markdown("---")
aba_pdfs, aba_resultados = st.tabs(
    [
        "PDFs de entrada",
        "Planilhas processadas",
    ]
)

# ==========================================================
# Aba: PDFs de entrada
# ==========================================================

with aba_pdfs:
    estados = list_states()

    if not estados:
        st.info("Nenhuma pasta de estado encontrada.")
    else:
        estado = st.selectbox(
            "Estado",
            estados,
            key="cloud_estado_pdf",
        )

        pdfs = list_pdfs(estado)

        st.metric(
            "PDFs encontrados",
            len(pdfs),
        )

        st.dataframe(
            [
                {
                    "Arquivo": arquivo["name"],
                    "Tamanho (KB)": round(
                        arquivo["size"] / 1024,
                        1,
                    ),
                    "Atualizado": arquivo["updated"],
                }
                for arquivo in pdfs
            ],
            use_container_width=True,
            hide_index=True,
        )


# ==========================================================
# Aba: Planilhas processadas
# ==========================================================

with aba_resultados:
    estados = list_states()

    filtro = st.selectbox(
        "Filtrar por UF",
        ["Todos"] + estados,
        key="cloud_estado_resultado",
    )

    resultados = list_results(
        None if filtro == "Todos" else filtro
    )

    st.metric(
        "Planilhas encontradas",
        len(resultados),
    )

    if resultados:
        nomes = [
            arquivo["name"]
            for arquivo in resultados
        ]

        escolhido = st.selectbox(
            "Selecione uma planilha",
            nomes,
        )

        item = next(
            arquivo
            for arquivo in resultados
            if arquivo["name"] == escolhido
        )

        st.write(
            f"Caminho: `{item['blob_name']}`"
        )

        dados = download_bytes(
            item["blob_name"]
        )

        st.download_button(
            "Baixar planilha",
            data=dados,
            file_name=item["name"],
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
