from __future__ import annotations

import streamlit as st

from core.download_lote import (
    available_rreo_ufs,
    inventory_brazil,
    inventory_state,
    prepare_rreo_zip,
    signed_download_url,
)
from integrations.google_storage import RREO_SOURCE_BUCKET, health_check
from ui.theme import apply_theme, metric_card, render_sidebar

st.set_page_config(
    page_title="Download em Lote",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
render_sidebar()

st.markdown(
    '<div class="hero-row"><div><div class="hero-title">Download em Lote</div>'
    '<div class="hero-sub">Baixe todos os PDFs RREO de um Estado ou do Brasil inteiro em um único ZIP.</div>'
    '</div><span class="online">● Sistema Online</span></div>',
    unsafe_allow_html=True,
)

status = health_check()
if not status.get("ok"):
    st.error("Cloud Storage indisponível.")
    st.code(status.get("message", "Erro desconhecido"))
    st.stop()

st.info(
    "Os PDFs originais são somente lidos. O ZIP é criado separadamente e salvo no Cloud de resultados. "
    "Nenhum PDF, planilha ou dado processado é alterado."
)

c1, c2, c3 = st.columns(3)
with c1:
    year = st.selectbox("Ano", list(range(2030, 2022, -1)), index=list(range(2030, 2022, -1)).index(2025))
with c2:
    bimestre = st.selectbox("Bimestre", [1, 2, 3, 4, 5, 6], index=5, format_func=lambda v: f"B{v}")
with c3:
    mode = st.radio("Tipo de download", ["Estado", "Brasil inteiro"], horizontal=True)

ufs: list[str] = []
selected_uf: str | None = None
if mode == "Estado":
    try:
        ufs = available_rreo_ufs(year)
    except Exception as exc:
        st.error("Não foi possível listar os Estados na origem RREO.")
        st.exception(exc)
        st.stop()
    if not ufs:
        st.warning("Nenhum Estado RREO encontrado para o ano selecionado.")
        st.stop()
    selected_uf = st.selectbox("Estado (UF)", ufs)

inventory_key = f"download_lote_inventory_{mode}_{year}_{bimestre}_{selected_uf or 'BR'}"
if st.button("🔎 Conferir arquivos disponíveis", width="stretch"):
    with st.spinner("Consultando PDFs no APPDOWELEVER..."):
        if mode == "Estado":
            inv = inventory_state(selected_uf or "", year, bimestre)
        else:
            inv = inventory_brazil(year, bimestre)
        st.session_state[inventory_key] = inv

inv = st.session_state.get(inventory_key)
if inv:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        metric_card("📄", "PDFs encontrados", str(inv.get("pdf_count", 0)), "RREO", "blue")
    with m2:
        size_mb = float(inv.get("source_bytes", 0)) / (1024 * 1024)
        metric_card("💾", "Tamanho original", f"{size_mb:.1f} MB", "Cloud", "purple")
    with m3:
        state_count = 1 if mode == "Estado" else int(inv.get("state_count", 0))
        metric_card("🗺️", "Estados", str(state_count), "Selecionados", "green")
    with m4:
        metric_card("☁", "Origem", RREO_SOURCE_BUCKET, f"2025/B{bimestre}" if year == 2025 else f"{year}/B{bimestre}", "blue")

    if mode == "Brasil inteiro" and inv.get("states"):
        with st.expander("Ver quantidade de PDFs por Estado"):
            cols = st.columns(4)
            for idx, (uf, values) in enumerate(sorted(inv["states"].items())):
                cols[idx % 4].write(f"**{uf}** — {values['pdf_count']} PDF(s)")

package_key = f"download_lote_package_{mode}_{year}_{bimestre}_{selected_uf or 'BR'}"
label = "📦 Preparar ZIP do Estado" if mode == "Estado" else "🇧🇷 Preparar ZIP do Brasil inteiro"

if st.button(label, type="primary", width="stretch"):
    bar = st.progress(0.0, text="Preparando lista de arquivos...")

    def on_progress(pos: int, total: int, current: str) -> None:
        bar.progress(pos / max(total, 1), text=f"Adicionando ao ZIP: {pos}/{total} · {current}")

    try:
        package = prepare_rreo_zip(
            "ESTADO" if mode == "Estado" else "BRASIL",
            year=year,
            bimestre=bimestre,
            uf=selected_uf,
            progress=on_progress,
        )
        url = signed_download_url(package.blob_name, hours=2)
        st.session_state[package_key] = {**package.to_dict(), "url": url}
        bar.empty()
        st.success(
            f"ZIP preparado: {package.filename} · {package.pdf_count} PDF(s) · "
            f"{package.zip_bytes / (1024 * 1024):.1f} MB."
        )
    except Exception as exc:
        bar.empty()
        st.error("Não foi possível preparar o ZIP.")
        st.exception(exc)

package = st.session_state.get(package_key)
if package:
    st.markdown("### ZIP pronto")
    st.caption(f"Cloud: `gs://{package['bucket']}/{package['blob_name']}`")
    st.link_button(
        f"⬇ Baixar {package['filename']}",
        package["url"],
        type="primary",
        width="stretch",
    )
    st.caption("O link é temporário por segurança. Se expirar, basta preparar o ZIP novamente.")

st.markdown(
    '<div class="footerbar">📦 Estado ou Brasil inteiro &nbsp;•&nbsp; ZIP sem carregar todos os PDFs na RAM '
    '&nbsp;•&nbsp; Originais preservados &nbsp;•&nbsp; Resultado salvo no Cloud</div>',
    unsafe_allow_html=True,
)
