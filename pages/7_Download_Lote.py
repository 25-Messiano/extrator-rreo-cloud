from __future__ import annotations

import streamlit as st

from core.download_lote import (
    available_rreo_ufs, inventory_brazil, inventory_state, prepare_rreo_zip,
    signed_download_url, inventory_processed_spreadsheets,
    prepare_processed_spreadsheets_zip, latest_processed_state_spreadsheets,
)
from integrations.google_storage import RREO_SOURCE_BUCKET, BUCKET_NAME, health_check
from ui.theme import apply_theme, metric_card, render_sidebar

st.set_page_config(page_title="Download em Lote", page_icon="📦", layout="wide", initial_sidebar_state="expanded")
apply_theme(); render_sidebar()

st.markdown('<div class="hero-row"><div><div class="hero-title">Download em Lote</div>'
            '<div class="hero-sub">PDFs de origem e planilhas processadas, por Estado ou Brasil inteiro.</div>'
            '</div><span class="online">● Sistema Online</span></div>', unsafe_allow_html=True)

status = health_check()
if not status.get("ok"):
    st.error("Cloud Storage indisponível."); st.code(status.get("message", "Erro desconhecido")); st.stop()

st.info("Operação somente de leitura nos arquivos originais. Os pacotes ZIP são criados separadamente; PDFs, planilhas processadas, MASTER e dados da Central não são alterados.")

content = st.radio("O que deseja baixar?", ["PDFs RREO", "Planilhas processadas"], horizontal=True)

if content == "PDFs RREO":
    c1,c2,c3=st.columns(3)
    with c1: year=st.selectbox("Ano", list(range(2030,2022,-1)), index=list(range(2030,2022,-1)).index(2025), key="pdf_year")
    with c2: bimestre=st.selectbox("Bimestre", [1,2,3,4,5,6], index=5, format_func=lambda v:f"B{v}")
    with c3: mode=st.radio("Abrangência", ["Estado","Brasil inteiro"], horizontal=True, key="pdf_scope")
    selected_uf=None
    if mode=="Estado":
        try: ufs=available_rreo_ufs(year)
        except Exception as exc: st.error("Não foi possível listar os Estados na origem RREO."); st.exception(exc); st.stop()
        if not ufs: st.warning("Nenhum Estado RREO encontrado para o ano selecionado."); st.stop()
        selected_uf=st.selectbox("Estado (UF)", ufs, key="pdf_uf")
    key=f"pdf_inv_{mode}_{year}_{bimestre}_{selected_uf or 'BR'}"
    if st.button("🔎 Conferir PDFs disponíveis", width="stretch"):
        with st.spinner("Consultando PDFs no APPDOWELEVER..."):
            st.session_state[key]=inventory_state(selected_uf or "",year,bimestre) if mode=="Estado" else inventory_brazil(year,bimestre)
    inv=st.session_state.get(key)
    if inv:
        a,b,c,d=st.columns(4)
        with a: metric_card("📄","PDFs encontrados",str(inv.get("pdf_count",0)),"RREO","blue")
        with b: metric_card("💾","Tamanho original",f"{float(inv.get('source_bytes',0))/(1024*1024):.1f} MB","Cloud","purple")
        with c: metric_card("🗺️","Estados",str(1 if mode=="Estado" else inv.get("state_count",0)),"Abrangência","green")
        with d: metric_card("☁","Origem",RREO_SOURCE_BUCKET,"Somente leitura","blue")
        if mode=="Brasil inteiro" and inv.get("states"):
            with st.expander("Ver quantidade de PDFs por Estado"):
                cols=st.columns(4)
                for idx,(uf,values) in enumerate(sorted(inv["states"].items())): cols[idx%4].write(f"**{uf}** — {values['pdf_count']} PDF(s)")
    package_key=f"pdf_pkg_{mode}_{year}_{bimestre}_{selected_uf or 'BR'}"
    label="📦 Preparar ZIP do Estado" if mode=="Estado" else "🇧🇷 Preparar ZIP do Brasil inteiro"
    if st.button(label,type="primary",width="stretch"):
        bar=st.progress(0.0,text="Preparando lista de arquivos...")
        def progress(pos,total,current): bar.progress(pos/max(total,1),text=f"Adicionando ao ZIP: {pos}/{total} · {current}")
        try:
            pkg=prepare_rreo_zip("ESTADO" if mode=="Estado" else "BRASIL",year,bimestre,selected_uf,progress)
            st.session_state[package_key]={**pkg.to_dict(),"url":signed_download_url(pkg.blob_name,2),"count_label":"PDF(s)"}; bar.empty(); st.success(f"ZIP preparado: {pkg.filename} · {pkg.pdf_count} PDF(s).")
        except Exception as exc: bar.empty(); st.error("Não foi possível preparar o ZIP."); st.exception(exc)
else:
    c1,c2,c3=st.columns(3)
    with c1: year=st.selectbox("Ano", list(range(2030,2022,-1)), index=list(range(2030,2022,-1)).index(2025), key="xlsx_year")
    with c2: selection_label=st.selectbox("Conjunto", ["Estaduais mais recentes", "Todas as Rodadas Novas", "MASTER nacional"])
    selection={"Estaduais mais recentes":"MAIS_RECENTES","Todas as Rodadas Novas":"TODAS_RODADAS","MASTER nacional":"MASTER"}[selection_label]
    with c3:
        if selection=="MASTER": mode="Brasil inteiro"; st.text_input("Abrangência",value="Brasil inteiro",disabled=True)
        else: mode=st.radio("Abrangência",["Estado","Brasil inteiro"],horizontal=True,key="xlsx_scope")
    selected_uf=None
    if selection!="MASTER" and mode=="Estado":
        try:
            available=sorted({x["uf"] for x in latest_processed_state_spreadsheets(year)})
        except Exception as exc: st.error("Não foi possível listar as planilhas estaduais."); st.exception(exc); st.stop()
        if not available: st.warning("Nenhuma planilha estadual processada encontrada para o ano selecionado."); st.stop()
        selected_uf=st.selectbox("Estado (UF)",available,key="xlsx_uf")
    scope="ESTADO" if mode=="Estado" else "BRASIL"
    key=f"xlsx_inv_{selection}_{scope}_{year}_{selected_uf or 'BR'}"
    if st.button("🔎 Conferir planilhas disponíveis",width="stretch"):
        with st.spinner("Consultando planilhas processadas no Cloud..."):
            st.session_state[key]=inventory_processed_spreadsheets(year,scope,selected_uf,selection)
    inv=st.session_state.get(key)
    if inv:
        a,b,c,d=st.columns(4)
        with a: metric_card("📊","Planilhas encontradas",str(inv.get("xlsx_count",0)),"XLSX","blue")
        with b: metric_card("💾","Tamanho original",f"{float(inv.get('source_bytes',0))/(1024*1024):.1f} MB","Cloud","purple")
        with c: metric_card("🗺️","Estados",str(inv.get("state_count",0) or (27 if selection=="MASTER" else 0)),"Abrangência","green")
        with d: metric_card("☁","Origem",BUCKET_NAME,"Somente leitura","blue")
        with st.expander("Ver arquivos que entrarão no pacote"):
            for item in inv.get("files",[]): st.write(f"**{item.get('uf') or 'BR'}** — {item['name']}")
    package_key=f"xlsx_pkg_{selection}_{scope}_{year}_{selected_uf or 'BR'}"
    if st.button("📦 Preparar ZIP das planilhas",type="primary",width="stretch"):
        bar=st.progress(0.0,text="Preparando planilhas...")
        def progress(pos,total,current): bar.progress(pos/max(total,1),text=f"Adicionando ao ZIP: {pos}/{total} · {current}")
        try:
            pkg=prepare_processed_spreadsheets_zip(year,scope,selected_uf,selection,progress)
            st.session_state[package_key]={**pkg.to_dict(),"url":signed_download_url(pkg.blob_name,2),"count_label":"planilha(s)"}; bar.empty(); st.success(f"ZIP preparado: {pkg.filename} · {pkg.pdf_count} planilha(s).")
        except Exception as exc: bar.empty(); st.error("Não foi possível preparar o ZIP das planilhas."); st.exception(exc)

package=st.session_state.get(locals().get("package_key",""))
if package:
    st.markdown("### Pacote pronto")
    st.caption(f"Cloud: `gs://{package['bucket']}/{package['blob_name']}`")
    st.link_button(f"⬇ Baixar {package['filename']}",package["url"],type="primary",width="stretch")
    st.caption("O link é temporário por segurança. Se expirar, basta preparar o ZIP novamente.")

st.markdown('<div class="footerbar">📦 PDFs + Planilhas processadas &nbsp;•&nbsp; Estado ou Brasil inteiro &nbsp;•&nbsp; Originais preservados &nbsp;•&nbsp; v1.3.7 RREO SAFE</div>',unsafe_allow_html=True)
