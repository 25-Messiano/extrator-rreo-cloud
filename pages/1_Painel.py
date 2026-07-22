from __future__ import annotations

import re
import shutil
import tempfile
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import streamlit as st
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from integrations.google_storage import (
    download_bytes,
    download_pdf,
    health_check,
    list_pdfs,
    list_states,
    upload_result,
)
from modules.rreo import process as processar_rreo


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

PLANILHA_BASE = (
    BASE_DIR
    / "data"
    / "RREO-TCM+FNDE PLANILHA BASE.xlsx"
)

CODIGOS_RREO = [
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "2.1",
    "2.1.1",
    "2.1.2",
    "2.2",
    "2.3",
    "2.4",
    "2.5",
    "2.6",
    "6.1.1",
    "6.2",
    "6.2.1",
]

CODIGOS_UF = {
    "AC": "12",
    "AL": "27",
    "AP": "16",
    "AM": "13",
    "BA": "29",
    "CE": "23",
    "DF": "53",
    "ES": "32",
    "GO": "52",
    "MA": "21",
    "MT": "51",
    "MS": "50",
    "MG": "31",
    "PA": "15",
    "PB": "25",
    "PR": "41",
    "PE": "26",
    "PI": "22",
    "RJ": "33",
    "RN": "24",
    "RS": "43",
    "RO": "11",
    "RR": "14",
    "SC": "42",
    "SP": "35",
    "SE": "28",
    "TO": "17",
}

NOMES_UF = {
    "ACRE": "AC",
    "ALAGOAS": "AL",
    "AMAPA": "AP",
    "AMAZONAS": "AM",
    "BAHIA": "BA",
    "CEARA": "CE",
    "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES",
    "GOIAS": "GO",
    "MARANHAO": "MA",
    "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG",
    "PARA": "PA",
    "PARAIBA": "PB",
    "PARANA": "PR",
    "PERNAMBUCO": "PE",
    "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO",
    "RORAIMA": "RR",
    "SANTA CATARINA": "SC",
    "SAO PAULO": "SP",
    "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar_texto(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = text.upper()

    text = re.sub(
        r"[^A-Z0-9]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def normalizar_codigo_ibge(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, float):
        value = int(value)

    return re.sub(
        r"\D",
        "",
        str(value),
    )


def extrair_uf(valor: str) -> str:
    texto = normalizar_texto(valor)

    partes = texto.split()

    for parte in reversed(partes):
        if parte in CODIGOS_UF:
            return parte

    for nome_estado, uf in NOMES_UF.items():
        if nome_estado in texto:
            return uf

    return ""


def extrair_nome_arquivo(nome_arquivo: str) -> str:
    nome = Path(nome_arquivo).stem

    nome = re.sub(
        r"(?i)^RREO[_\s-]*MUNICIPAL[_\s-]*\d{4}",
        "",
        nome,
    )

    nome = re.sub(
        r"(?i)^[_\s-]*RREO[_\s-]*",
        "",
        nome,
    )

    nome = re.sub(
        r"\s*-\s*[A-Za-z]{2}\s*$",
        "",
        nome,
    )

    return normalizar_texto(nome)


def similaridade(
    nome_a: str,
    nome_b: str,
) -> float:
    a = normalizar_texto(nome_a)
    b = normalizar_texto(nome_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.97

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


# ============================================================
# LEITURA DA PLANILHA-BASE
# ============================================================

def localizar_coluna_por_cabecalho(
    worksheet: Worksheet,
    termos: list[str],
) -> int | None:
    termos_normalizados = [
        normalizar_texto(termo)
        for termo in termos
    ]

    limite_linhas = min(
        20,
        worksheet.max_row,
    )

    for row in range(
        1,
        limite_linhas + 1,
    ):
        for column in range(
            1,
            worksheet.max_column + 1,
        ):
            value = normalizar_texto(
                worksheet.cell(
                    row=row,
                    column=column,
                ).value
            )

            if not value:
                continue

            if any(
                termo in value
                for termo in termos_normalizados
            ):
                return column

    return None


def localizar_colunas_codigos(
    worksheet: Worksheet,
    codigos: list[str],
) -> dict[str, int]:
    colunas: dict[str, int] = {}

    limite_linhas = min(
        20,
        worksheet.max_row,
    )

    codigos_ordenados = sorted(
        codigos,
        key=len,
        reverse=True,
    )

    for row in range(
        1,
        limite_linhas + 1,
    ):
        for column in range(
            1,
            worksheet.max_column + 1,
        ):
            value = normalizar_texto(
                worksheet.cell(
                    row=row,
                    column=column,
                ).value
            )

            if not value:
                continue

            for codigo in codigos_ordenados:
                codigo_normalizado = normalizar_texto(
                    codigo
                )

                padroes_aceitos = (
                    f"{codigo_normalizado} ",
                    f"{codigo_normalizado}-",
                )

                if (
                    value == codigo_normalizado
                    or value.startswith(padroes_aceitos)
                ):
                    if codigo not in colunas:
                        colunas[codigo] = column

                    break

    return colunas


def escolher_aba_principal(
    workbook: Any,
) -> Worksheet:
    melhor_aba = workbook.active
    melhor_pontuacao = -1

    for worksheet in workbook.worksheets:
        pontuacao = 0

        coluna_ibge = localizar_coluna_por_cabecalho(
            worksheet,
            ["Código IBGE", "Codigo IBGE"],
        )

        coluna_ente = localizar_coluna_por_cabecalho(
            worksheet,
            ["Ente Federado", "Município", "Municipio"],
        )

        colunas_codigos = localizar_colunas_codigos(
            worksheet,
            CODIGOS_RREO,
        )

        if coluna_ibge:
            pontuacao += 10

        if coluna_ente:
            pontuacao += 10

        pontuacao += len(colunas_codigos)

        if pontuacao > melhor_pontuacao:
            melhor_aba = worksheet
            melhor_pontuacao = pontuacao

    return melhor_aba


def carregar_municipios(
    worksheet: Worksheet,
    uf: str,
) -> list[dict[str, Any]]:
    coluna_ibge = localizar_coluna_por_cabecalho(
        worksheet,
        ["Código IBGE", "Codigo IBGE"],
    )

    coluna_ente = localizar_coluna_por_cabecalho(
        worksheet,
        ["Ente Federado", "Município", "Municipio"],
    )

    if not coluna_ibge or not coluna_ente:
        raise RuntimeError(
            "Não foi possível localizar as colunas "
            "'Código IBGE' e 'Ente Federado'."
        )

    prefixo_estado = CODIGOS_UF[uf]

    municipios: list[dict[str, Any]] = []

    for row in range(
        1,
        worksheet.max_row + 1,
    ):
        codigo = normalizar_codigo_ibge(
            worksheet.cell(
                row=row,
                column=coluna_ibge,
            ).value
        )

        ente = str(
            worksheet.cell(
                row=row,
                column=coluna_ente,
            ).value
            or ""
        ).strip()

        if len(codigo) != 7:
            continue

        if not codigo.startswith(prefixo_estado):
            continue

        if not normalizar_texto(ente).endswith(
            normalizar_texto(uf)
        ):
            continue

        nome = ente.rsplit(
            "/",
            maxsplit=1,
        )[0].strip()

        municipios.append(
            {
                "row": row,
                "codigo_ibge": codigo,
                "nome": nome,
                "uf": uf,
                "ente": ente,
                "nome_normalizado": normalizar_texto(nome),
            }
        )

    return municipios


# ============================================================
# IDENTIFICAÇÃO DO MUNICÍPIO
# ============================================================

def localizar_municipio_por_nome(
    nome_referencia: str,
    municipios: list[dict[str, Any]],
    limite_minimo: float = 0.72,
) -> tuple[dict[str, Any] | None, float]:
    melhor_municipio = None
    melhor_nota = 0.0

    for municipio in municipios:
        nota = similaridade(
            nome_referencia,
            municipio["nome"],
        )

        if nota > melhor_nota:
            melhor_nota = nota
            melhor_municipio = municipio

    if melhor_nota < limite_minimo:
        return None, melhor_nota

    return melhor_municipio, melhor_nota


def localizar_municipio_pdf(
    arquivo_pdf: dict[str, Any],
    texto_pdf: str,
    municipios: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, str]:
    nome_arquivo = extrair_nome_arquivo(
        arquivo_pdf["name"]
    )

    municipio_arquivo, nota_arquivo = (
        localizar_municipio_por_nome(
            nome_arquivo,
            municipios,
        )
    )

    if (
        municipio_arquivo is not None
        and nota_arquivo >= 0.88
    ):
        return (
            municipio_arquivo,
            nota_arquivo,
            "nome do arquivo",
        )

    texto_normalizado = normalizar_texto(
        texto_pdf[:15000]
    )

    melhor_municipio = municipio_arquivo
    melhor_nota = nota_arquivo
    origem = "nome do arquivo"

    for municipio in municipios:
        nome = municipio["nome_normalizado"]

        if nome and nome in texto_normalizado:
            return (
                municipio,
                1.0,
                "conteúdo do PDF",
            )

        nota = similaridade(
            nome,
            texto_normalizado[:1500],
        )

        if nota > melhor_nota:
            melhor_municipio = municipio
            melhor_nota = nota
            origem = "conteúdo aproximado do PDF"

    if melhor_nota < 0.72:
        return None, melhor_nota, origem

    return melhor_municipio, melhor_nota, origem


def localizar_pdf_municipio(
    municipio: dict[str, Any],
    arquivos_pdf: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float]:
    melhor_arquivo = None
    melhor_nota = 0.0

    for arquivo in arquivos_pdf:
        nome_pdf = extrair_nome_arquivo(
            arquivo["name"]
        )

        nota = similaridade(
            municipio["nome"],
            nome_pdf,
        )

        if nota > melhor_nota:
            melhor_nota = nota
            melhor_arquivo = arquivo

    if melhor_nota < 0.65:
        return None, melhor_nota

    return melhor_arquivo, melhor_nota


# ============================================================
# PROCESSAMENTO
# ============================================================

def preencher_resultados(
    worksheet: Worksheet,
    row: int,
    resultados: dict[str, float | None],
    colunas_codigos: dict[str, int],
) -> int:
    preenchidos = 0

    for codigo, valor in resultados.items():
        coluna = colunas_codigos.get(codigo)

        if coluna is None or valor is None:
            continue

        cell = worksheet.cell(
            row=row,
            column=coluna,
        )

        cell.value = valor
        cell.number_format = '#,##0.00'

        preenchidos += 1

    return preenchidos


def processar_um_pdf(
    arquivo_pdf: dict[str, Any],
    pasta_temporaria: Path,
) -> tuple[dict[str, float | None], str]:
    caminho_pdf = (
        pasta_temporaria
        / arquivo_pdf["name"]
    )

    download_pdf(
        blob_name=arquivo_pdf["blob_name"],
        destination=caminho_pdf,
    )

    resultados, texto = processar_rreo(
        caminho_pdf,
        CODIGOS_RREO,
    )

    try:
        caminho_pdf.unlink(
            missing_ok=True
        )
    except OSError:
        pass

    return resultados, texto


def gerar_nome_saida(
    uf: str,
    modo: str,
    municipio: dict[str, Any] | None = None,
) -> str:
    agora = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    if modo == "Município único" and municipio:
        nome = normalizar_texto(
            municipio["nome"]
        ).replace(
            " ",
            "_",
        )

        return (
            f"RREO_{municipio['codigo_ibge']}_"
            f"{nome}_{uf}_{agora}.xlsx"
        )

    return (
        f"RREO_ESTADO_{uf}_{agora}.xlsx"
    )


# ============================================================
# CACHE LEVE
# ============================================================

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def carregar_estados_cloud() -> list[str]:
    return list_states()


@st.cache_data(
    ttl=180,
    show_spinner=False,
)
def carregar_pdfs_estado(
    estado_cloud: str,
) -> list[dict[str, Any]]:
    return list_pdfs(
        estado_cloud
    )


# ============================================================
# INTERFACE
# ============================================================
# ============================================================
# INTERFACE
# ============================================================

import pandas as pd
from ui.theme import apply_theme, metric_card, render_sidebar

st.set_page_config(page_title="Painel de Extração", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
apply_theme()
render_sidebar()

status = health_check()
cloud_ok = bool(status.get("ok"))
gemini_ok = bool((__import__("os").getenv("GEMINI_API_KEY") or __import__("os").getenv("GOOGLE_API_KEY") or "").strip())

st.markdown(
    f'<div class="hero-row"><div><div class="hero-title">Painel de Extração</div><div class="hero-sub">Selecione o estado ou município, acompanhe o progresso e baixe o resultado.</div></div><span class="online">● Sistema Online</span></div>',
    unsafe_allow_html=True,
)

m1,m2,m3,m4=st.columns(4)
with m1: metric_card("☁","Armazenamento","Cloud Storage","Conectado" if cloud_ok else "Verificar","blue")
with m2: metric_card("🗄","Banco de Dados","SQLite","Ativo","purple")
with m3: metric_card("🛡","Credenciais GCS","Configuradas" if cloud_ok else "Pendentes","OK" if cloud_ok else "Atenção","green")
with m4: metric_card("✦","Gemini API","Configurado" if gemini_ok else "Pendente","OK" if gemini_ok else "Atenção","blue")

if not cloud_ok:
    st.error("Não foi possível conectar ao Google Cloud Storage.")
    st.code(status.get("message","Erro desconhecido."))
    st.stop()
if not PLANILHA_BASE.exists():
    st.error("A planilha-base não foi encontrada.")
    st.stop()

try:
    estados_cloud=carregar_estados_cloud()
except Exception as error:
    st.error("Não foi possível listar os estados do Cloud Storage.")
    st.exception(error)
    st.stop()
if not estados_cloud:
    st.warning("Nenhuma pasta de estado foi encontrada no bucket.")
    st.stop()

st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">1.</span>Seleção de Estado ou Município</div>',unsafe_allow_html=True)
c1,c2,c3,c4=st.columns([1.15,1.45,1.7,.9])
with c1:
    modo_curto=st.segmented_control("Modo de Processamento",options=["Estado","Município"],default="Estado")
    modo="Estado inteiro" if modo_curto=="Estado" else "Município único"
with c2:
    estado_cloud=st.selectbox("Estado (UF)",estados_cloud)
uf=extrair_uf(estado_cloud)
if not uf:
    uf=st.selectbox("UF",sorted(CODIGOS_UF))
with c4:
    ano=st.selectbox("Ano de Referência",[2025,2024,2023],index=0)

try:
    arquivos_pdf=carregar_pdfs_estado(estado_cloud)
    workbook_consulta=load_workbook(PLANILHA_BASE,read_only=False,data_only=False)
    worksheet_consulta=escolher_aba_principal(workbook_consulta)
    municipios=carregar_municipios(worksheet_consulta,uf)
    workbook_consulta.close()
except Exception as error:
    st.error("Não foi possível preparar os dados do estado.")
    st.exception(error)
    st.stop()

municipio_selecionado=None
arquivo_selecionado=None
with c3:
    if modo=="Município único":
        municipio_selecionado=st.selectbox("Município",municipios,format_func=lambda i:f"{i['nome']} - {i['uf']}")
    else:
        st.selectbox("Município (opcional)",["Todos os municípios"],disabled=True)
st.markdown('</div>',unsafe_allow_html=True)

if modo=="Município único":
    arquivo_selecionado,nota_pdf=localizar_pdf_municipio(municipio_selecionado,arquivos_pdf)
    nomes=[a["name"] for a in arquivos_pdf]
    if nomes:
        indice=nomes.index(arquivo_selecionado["name"]) if arquivo_selecionado else 0
        nome_escolhido=st.selectbox("PDF confirmado",nomes,index=indice)
        arquivo_selecionado=next(a for a in arquivos_pdf if a["name"]==nome_escolhido)

left,mid,right=st.columns([1.55,1.05,1.0])
with left:
    st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">2.</span>Arquivos Encontrados</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    total_size=sum(int(x.get("size") or 0) for x in arquivos_pdf)
    with a: st.markdown(f'<div class="mini-stat"><div class="mini-label">Municípios</div><div class="mini-value">{len(municipios)}</div></div>',unsafe_allow_html=True)
    with b: st.markdown(f'<div class="mini-stat"><div class="mini-label">PDFs</div><div class="mini-value">{len(arquivos_pdf)}</div></div>',unsafe_allow_html=True)
    with c: st.markdown(f'<div class="mini-stat"><div class="mini-label">Tamanho Total</div><div class="mini-value">{total_size/1024/1024:.1f} MB</div></div>',unsafe_allow_html=True)
    with d: st.markdown(f'<div class="mini-stat"><div class="mini-label">Ano</div><div class="mini-value">{ano}</div></div>',unsafe_allow_html=True)
    preview=[]
    for mun in municipios[:50]:
        arq,nota=localizar_pdf_municipio(mun,arquivos_pdf)
        preview.append({"Município":mun["nome"],"Código IBGE":mun["codigo_ibge"],"PDF":"Sim" if arq else "Não","Correspondência":f"{nota*100:.0f}%" if arq else "-"})
    st.dataframe(pd.DataFrame(preview),use_container_width=True,hide_index=True,height=330)
    st.caption(f"Exibindo os primeiros {min(50,len(preview))} municípios. O processamento usa a lista completa.")
    st.markdown('</div>',unsafe_allow_html=True)

with mid:
    st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">3.</span>Processamento</div>',unsafe_allow_html=True)
    state=st.session_state.setdefault("job",{"status":"Aguardando","progress":0,"current":"Nenhum","success":0,"errors":0,"total":0})
    st.write("**Situação Atual**")
    st.info(state["status"])
    st.progress(float(state["progress"]),text=f"Progresso geral: {state['progress']*100:.0f}%")
    st.write("**Município Atual**")
    st.write(state["current"])
    x,y,z=st.columns(3)
    x.metric("Concluídos",state["success"])
    y.metric("Pendentes",max(state["total"]-state["success"]-state["errors"],0))
    z.metric("Erros",state["errors"])
    executar=st.button("▶ Processar agora",type="primary",use_container_width=True)
    st.markdown('</div>',unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">4.</span>Logs do Sistema</div>',unsafe_allow_html=True)
    logbox=st.empty()
    logs=st.session_state.setdefault("logs",["Sistema pronto para iniciar.",f"{len(arquivos_pdf)} PDFs encontrados em {uf}."])
    logbox.code("\n".join(logs[-12:]),language=None)
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">5.</span>Resultado</div>',unsafe_allow_html=True)
    result=st.session_state.get("last_result")
    if result:
        st.success(result["name"])
        st.download_button("⬇ Download",data=result["bytes"],file_name=result["name"],mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        st.caption(result["cloud"])
    else:
        st.caption("O arquivo Excel aparecerá aqui após o processamento.")
    st.markdown('</div>',unsafe_allow_html=True)

if executar:
    pasta_temporaria=Path(tempfile.mkdtemp(prefix="rreo_cloud_"))
    try:
        caminho_saida=pasta_temporaria/gerar_nome_saida(uf,modo,municipio_selecionado)
        shutil.copy2(PLANILHA_BASE,caminho_saida)
        workbook=load_workbook(caminho_saida)
        worksheet=escolher_aba_principal(workbook)
        colunas_codigos=localizar_colunas_codigos(worksheet,CODIGOS_RREO)
        arquivos_processar=[arquivo_selecionado] if modo=="Município único" else arquivos_pdf
        municipios_alvo=[municipio_selecionado] if modo=="Município único" else municipios
        total=len(arquivos_processar)
        state.update({"status":"Em andamento","progress":0,"current":"Preparando...","success":0,"errors":0,"total":total})
        divergencias=[]
        progress_slot=st.progress(0,text="Iniciando...")
        status_slot=st.empty()
        for indice,arquivo_pdf in enumerate(arquivos_processar,start=1):
            state["current"]=arquivo_pdf["name"]
            logs.append(f"{datetime.now().strftime('%H:%M:%S')}  Processando {arquivo_pdf['name']}")
            logbox.code("\n".join(logs[-12:]),language=None)
            status_slot.info(f"Processando {indice} de {total}: {arquivo_pdf['name']}")
            try:
                resultados,texto_pdf=processar_um_pdf(arquivo_pdf,pasta_temporaria)
                if modo=="Município único":
                    municipio_encontrado,nota,origem=municipio_selecionado,1.0,"seleção manual"
                else:
                    municipio_encontrado,nota,origem=localizar_municipio_pdf(arquivo_pdf,texto_pdf,municipios_alvo)
                if municipio_encontrado is None:
                    state["errors"]+=1
                    divergencias.append({"arquivo":arquivo_pdf["name"],"problema":"Município não identificado","nota":nota})
                else:
                    preencher_resultados(worksheet,municipio_encontrado["row"],resultados,colunas_codigos)
                    state["success"]+=1
            except Exception as error:
                state["errors"]+=1
                divergencias.append({"arquivo":arquivo_pdf["name"],"problema":str(error),"nota":0})
            state["progress"]=indice/total
            progress_slot.progress(state["progress"],text=f"Progresso geral: {state['progress']*100:.0f}%")
        workbook.save(caminho_saida); workbook.close()
        resultado_cloud=upload_result(caminho_saida,uf)
        dados=caminho_saida.read_bytes()
        st.session_state["last_result"]={"name":caminho_saida.name,"bytes":dados,"cloud":resultado_cloud["blob_name"]}
        state["status"]="Concluído"; state["current"]="Finalizado"
        logs.append(f"{datetime.now().strftime('%H:%M:%S')}  Extração concluída: {state['success']} sucesso(s), {state['errors']} erro(s).")
        status_slot.success("Processamento concluído. O Excel foi salvo no Cloud Storage.")
        if divergencias:
            st.warning("Alguns arquivos precisam de conferência.")
            st.dataframe(divergencias,use_container_width=True,hide_index=True)
        st.rerun()
    except Exception as error:
        state["status"]="Falha"
        logs.append(f"ERRO: {error}")
        st.exception(error)
    finally:
        shutil.rmtree(pasta_temporaria,ignore_errors=True)

st.markdown('<div class="section-card"><div class="section-title">Fluxo Operacional</div><div class="flow"><div class="flow-step"><div class="flow-num">1</div><div><div class="flow-name">Listagem</div><div class="flow-desc">PDFs localizados no Google Cloud Storage</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">2</div><div><div class="flow-name">Extração</div><div class="flow-desc">Gemini lê Receitas Realizadas Até o Bimestre (b)</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">3</div><div><div class="flow-name">Geração</div><div class="flow-desc">Excel preenchido automaticamente</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">4</div><div><div class="flow-name">Upload</div><div class="flow-desc">Resultado salvo e liberado</div></div></div></div></div>',unsafe_allow_html=True)
st.markdown('<div class="footerbar">● Sistema operando com Gemini &nbsp;•&nbsp; Extração inteligente &nbsp;•&nbsp; Cache de listagem &nbsp;•&nbsp; Armazenamento seguro na nuvem</div>',unsafe_allow_html=True)
