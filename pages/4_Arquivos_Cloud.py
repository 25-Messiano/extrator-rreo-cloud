from __future__ import annotations

from datetime import datetime
import streamlit as st

from integrations.google_storage import (
    BUCKET_NAME, download_bytes, health_check, list_pdfs, list_results, list_states
)

st.set_page_config(page_title="Arquivos Cloud", page_icon="☁️", layout="wide")
st.title("☁️ Arquivos do Cloud Storage")
st.caption(f"Bucket configurado: `{BUCKET_NAME}`")

if st.button("Testar conexão", type="primary"):
    result = health_check()
    if result.get("ok"):
        st.success(f"Conectado ao bucket: {result['bucket']}")
    else:
        st.error(result.get("message", "Falha desconhecida."))

status = health_check()
if not status.get("ok"):
    st.warning("A listagem ficará disponível após configurar as credenciais do Cloud Storage.")
    st.stop()

aba_pdfs, aba_resultados = st.tabs(["PDFs de entrada", "Planilhas processadas"])

with aba_pdfs:
    estados = list_states()
    if not estados:
        st.info("Nenhuma pasta de estado encontrada.")
    else:
        estado = st.selectbox("Estado", estados, key="cloud_estado_pdf")
        pdfs = list_pdfs(estado)
        st.metric("PDFs encontrados", len(pdfs))
        st.dataframe([
            {"Arquivo": f["name"], "Tamanho (KB)": round(f["size"] / 1024, 1),
             "Atualizado": f["updated"]}
            for f in pdfs
        ], use_container_width=True, hide_index=True)

with aba_resultados:
    estados = list_states()
    filtro = st.selectbox("Filtrar por UF", ["Todos"] + estados, key="cloud_estado_resultado")
    resultados = list_results(None if filtro == "Todos" else filtro)
    st.metric("Planilhas encontradas", len(resultados))
    if resultados:
        nomes = [f["name"] for f in resultados]
        escolhido = st.selectbox("Selecione uma planilha", nomes)
        item = next(f for f in resultados if f["name"] == escolhido)
        st.write(f"Caminho: `{item['blob_name']}`")
        dados = download_bytes(item["blob_name"])
        st.download_button("Baixar planilha", data=dados, file_name=item["name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
