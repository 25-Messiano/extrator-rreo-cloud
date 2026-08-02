from __future__ import annotations

import random
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
    find_fnde_folder,
    health_check,
    list_fnde_pdfs,
    list_pdfs,
    list_states,
    upload_result,
)
from modules.rreo import process as processar_rreo
from modules.fnde import process as processar_fnde
from core.config_manager import load_json
from core.auditoria import append_fnde_log, append_rreo_log, timestamp, write_audit, write_missing


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

CODIGOS_CONFIG = load_json("codigos_ativos.json")
SISTEMA_CONFIG = load_json("sistema.json")
PERMITIR_RREO = bool(SISTEMA_CONFIG.get("processar_rreo", True))
PERMITIR_FNDE = bool(SISTEMA_CONFIG.get("processar_fnde", True))
PROCESSAR_RREO = PERMITIR_RREO
PROCESSAR_FNDE = PERMITIR_FNDE
GERAR_LOG_RREO = bool(SISTEMA_CONFIG.get("gerar_log_rreo", SISTEMA_CONFIG.get("gerar_log_processamento", True)))
GERAR_LOG_FNDE = bool(SISTEMA_CONFIG.get("gerar_log_fnde", SISTEMA_CONFIG.get("gerar_log_processamento", True)))
GERAR_NAO_ENCONTRADOS = bool(SISTEMA_CONFIG.get("gerar_municipios_nao_encontrados", True))
GERAR_AUDITORIA = bool(SISTEMA_CONFIG.get("gerar_auditoria", True))
PROGRAMAS_FNDE_ATIVOS = [k for k, v in CODIGOS_CONFIG.get("fnde", {}).items() if v and k != "PNLD"]

PLANILHA_BASE = (
    BASE_DIR
    / "data"
    / "RREO-TCM+FNDE PLANILHA BASE.xlsx"
)

TODOS_CODIGOS_RREO = [
    "1.1", "1.2", "1.3", "1.4", "2.1", "2.1.1", "2.1.2",
    "2.2", "2.3", "2.4", "2.5", "2.6", "6.1.1", "6.2", "6.2.1",
]
CODIGOS_RREO = [
    codigo for codigo in TODOS_CODIGOS_RREO
    if CODIGOS_CONFIG.get("rreo", {}).get(codigo, False)
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
# FNDE COMBINADO E AUDITORIA
# ============================================================

def _codigo_ibge_nome_fnde(name: str) -> str:
    match = re.search(r"(?<!\d)(\d{7})(?!\d)", name)
    return match.group(1) if match else ""


def _indice_fnde_por_ibge(uf: str, year: int) -> dict[str, dict[str, Any]]:
    if not PROCESSAR_FNDE:
        return {}
    folder = find_fnde_folder(uf, year)
    if not folder:
        return {}
    return {
        code: item
        for item in list_fnde_pdfs(folder)
        if (code := _codigo_ibge_nome_fnde(item["name"]))
    }


def _processar_fnde_municipio(
    arquivo: dict[str, Any] | None,
    pasta_temporaria: Path,
) -> tuple[dict[str, float], list[str]]:
    if not arquivo:
        return {}, ["PDF FNDE não encontrado"]
    caminho = pasta_temporaria / f"fnde_{arquivo['name']}"
    download_pdf(arquivo["blob_name"], caminho)
    try:
        valores, _, resultado = processar_fnde(caminho, enviar_imagens=True)
        return valores, list(resultado.avisos)
    finally:
        caminho.unlink(missing_ok=True)


def _preencher_fnde(worksheet: Worksheet, row: int, valores: dict[str, float]) -> int:
    # Mapeamento vigente deste aplicativo: T=PNAE, U=PNATE, V=PDDE, W=QSE.
    columns = {"PNAE": 20, "PNATE": 21, "PDDE": 22, "QSE": 23}
    count = 0
    for program in PROGRAMAS_FNDE_ATIVOS:
        if program not in columns or program not in valores:
            continue
        cell = worksheet.cell(row=row, column=columns[program])
        cell.value = float(valores[program] or 0.0)
        cell.number_format = '#,##0.00'
        count += 1
    return count

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
    operacao: str = "RREO e FNDE",
) -> str:
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefixo = {
        "RREO": "RREO",
        "FNDE": "FNDE",
        "RREO e FNDE": "RREO_FNDE",
    }.get(operacao, "RREO_FNDE")

    if modo == "Todos os Estados":
        return f"{prefixo}_TODOS_OS_ESTADOS_{agora}.xlsx"

    if modo == "Município único" and municipio:
        nome = normalizar_texto(municipio["nome"]).replace(" ", "_")
        return f"{prefixo}_{municipio['codigo_ibge']}_{nome}_{uf}_{agora}.xlsx"

    return f"{prefixo}_ESTADO_{uf}_{agora}.xlsx"


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
    '<div class="hero-row"><div><div class="hero-title">Painel Único de Extração</div>'
    '<div class="hero-sub">RREO e FNDE no mesmo fluxo, com seleção de municípios, logs e auditoria.</div>'
    '</div><span class="online">● Sistema Online</span></div>',
    unsafe_allow_html=True,
)

operacoes_disponiveis = []
if PERMITIR_RREO:
    operacoes_disponiveis.append("RREO")
if PERMITIR_FNDE:
    operacoes_disponiveis.append("FNDE")
if PERMITIR_RREO and PERMITIR_FNDE:
    operacoes_disponiveis.append("RREO e FNDE")
if not operacoes_disponiveis:
    st.error("Nenhuma operação está habilitada em Configurações.")
    st.stop()

operacao = st.segmented_control(
    "Operação desejada",
    options=operacoes_disponiveis,
    default=("RREO e FNDE" if "RREO e FNDE" in operacoes_disponiveis else operacoes_disponiveis[0]),
    selection_mode="single",
) or operacoes_disponiveis[0]
PROCESSAR_RREO = operacao in {"RREO", "RREO e FNDE"}
PROCESSAR_FNDE = operacao in {"FNDE", "RREO e FNDE"}

st.caption(
    f"Operação selecionada: {operacao} | "
    + (f"Códigos RREO: {', '.join(CODIGOS_RREO)}" if PROCESSAR_RREO else "Leitura visual FNDE com Gemini/OCR")
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
if PROCESSAR_FNDE and not gemini_ok and not SISTEMA_CONFIG.get("fnde_usar_ocr_fallback", True):
    st.error("FNDE selecionado, mas Gemini e OCR fallback não estão disponíveis.")
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

st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">1.</span>Operação, Estado e Municípios</div>',unsafe_allow_html=True)
c1,c2,c3,c4=st.columns([1.15,1.45,1.7,.9])
with c1:
    modo=st.selectbox(
        "Modo de Processamento",
        ["Estado inteiro", "Município único", "Municípios selecionados", "Amostra"],
        index=0,
    )
    todos_os_estados=st.checkbox("Todos os Estados",key="todos_os_estados")
    if todos_os_estados:
        modo="Estado inteiro"
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
municipios_selecionados=list(municipios)
arquivo_selecionado=None
arquivos_selecionados=list(arquivos_pdf)
selection_note="Todos os municípios do estado."

with c3:
    if todos_os_estados:
        st.selectbox("Município", ["Todos os municípios de todos os estados"], disabled=True)
    elif modo=="Município único":
        municipio_selecionado=st.selectbox(
            "Município",
            municipios,
            format_func=lambda i:f"{i['nome']} - {i['uf']}",
        )
        municipios_selecionados=[municipio_selecionado]
        selection_note="Um município selecionado manualmente."
    elif modo=="Municípios selecionados":
        codigos_escolhidos=st.multiselect(
            "Escolha os municípios",
            options=[m["codigo_ibge"] for m in municipios],
            format_func=lambda code: next(
                f"{m['nome']} - {m['uf']} ({m['codigo_ibge']})"
                for m in municipios if m["codigo_ibge"]==code
            ),
            default=[],
            help="Pesquise pelo nome ou código IBGE e marque quantos desejar.",
        )
        codigos_set=set(codigos_escolhidos)
        municipios_selecionados=[m for m in municipios if m["codigo_ibge"] in codigos_set]
        selection_note=f"{len(municipios_selecionados)} município(s) selecionado(s) manualmente."
    elif modo=="Amostra":
        amostra_cols=st.columns([1.0,1.4])
        with amostra_cols[0]:
            quantidade_amostra=st.number_input(
                "Quantidade",
                min_value=1,
                max_value=max(1,min(len(municipios),100)),
                value=min(5,max(1,len(municipios))),
                step=1,
            )
        with amostra_cols[1]:
            criterio_amostra=st.selectbox(
                "Critério",
                ["Primeiros da lista","Aleatórios (repetível)"],
            )
        quantidade=min(int(quantidade_amostra),len(municipios))
        if criterio_amostra=="Aleatórios (repetível)":
            municipios_selecionados=random.Random(f"{estado_cloud}|{ano}|RREO").sample(municipios,quantidade)
            municipios_selecionados=sorted(municipios_selecionados,key=lambda m:normalizar_texto(m["nome"]))
        else:
            municipios_selecionados=municipios[:quantidade]
        selection_note=f"Amostra de {len(municipios_selecionados)} município(s): {criterio_amostra}."
    else:
        st.selectbox("Município",["Todos os municípios"],disabled=True)

st.markdown('</div>',unsafe_allow_html=True)

if modo=="Município único" and not todos_os_estados:
    arquivo_selecionado,nota_pdf=localizar_pdf_municipio(municipio_selecionado,arquivos_pdf)
    nomes=[a["name"] for a in arquivos_pdf]
    if nomes:
        indice=nomes.index(arquivo_selecionado["name"]) if arquivo_selecionado else 0
        nome_escolhido=st.selectbox("PDF confirmado",nomes,index=indice)
        arquivo_selecionado=next(a for a in arquivos_pdf if a["name"]==nome_escolhido)
    arquivos_selecionados=[arquivo_selecionado] if arquivo_selecionado else []
elif not todos_os_estados and modo in {"Municípios selecionados","Amostra"}:
    arquivos_selecionados=[]
    for municipio_item in municipios_selecionados:
        arquivo_item,_=localizar_pdf_municipio(municipio_item,arquivos_pdf)
        if arquivo_item and arquivo_item not in arquivos_selecionados:
            arquivos_selecionados.append(arquivo_item)

if not todos_os_estados and not municipios_selecionados:
    st.warning("Selecione pelo menos um município antes de processar.")

left,mid,right=st.columns([1.55,1.05,1.0])
with left:
    st.markdown('<div class="section-card"><div class="section-title"><span class="section-num">2.</span>Arquivos Encontrados</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    arquivos_resumo=arquivos_pdf if todos_os_estados or modo=="Estado inteiro" else arquivos_selecionados
    municipios_resumo=municipios if todos_os_estados or modo=="Estado inteiro" else municipios_selecionados
    total_size=sum(int(x.get("size") or 0) for x in arquivos_resumo if x)
    with a: st.markdown(f'<div class="mini-stat"><div class="mini-label">Municípios selecionados</div><div class="mini-value">{len(municipios_resumo)}</div></div>',unsafe_allow_html=True)
    with b: st.markdown(f'<div class="mini-stat"><div class="mini-label">PDFs localizados</div><div class="mini-value">{len(arquivos_resumo)}</div></div>',unsafe_allow_html=True)
    with c: st.markdown(f'<div class="mini-stat"><div class="mini-label">Tamanho Total</div><div class="mini-value">{total_size/1024/1024:.1f} MB</div></div>',unsafe_allow_html=True)
    with d: st.markdown(f'<div class="mini-stat"><div class="mini-label">Ano</div><div class="mini-value">{ano}</div></div>',unsafe_allow_html=True)
    preview=[]
    lista_preview=municipios if todos_os_estados or modo=="Estado inteiro" else municipios_selecionados
    for mun in lista_preview[:100]:
        arq,nota=localizar_pdf_municipio(mun,arquivos_pdf)
        preview.append({"Município":mun["nome"],"Código IBGE":mun["codigo_ibge"],"PDF":"Sim" if arq else "Não","Correspondência":f"{nota*100:.0f}%" if arq else "-"})
    st.dataframe(pd.DataFrame(preview),use_container_width=True,hide_index=True,height=330)
    st.caption(f"Exibindo {min(100,len(preview))} de {len(lista_preview)} município(s) selecionado(s).")
    st.info(selection_note)
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
    quantidade_selecionada=(len(municipios) if todos_os_estados or modo=="Estado inteiro" else len(municipios_selecionados))
    st.write("**Resumo antes de iniciar**")
    st.caption(
        f"Estado: {'TODOS' if todos_os_estados else uf} | Modo: {modo} | "
        f"Municípios selecionados: {quantidade_selecionada} | "
        f"Operação: {operacao} | RREO: {'SIM' if PROCESSAR_RREO else 'NÃO'} | FNDE: {'SIM' if PROCESSAR_FNDE else 'NÃO'}"
    )
    executar=st.button(
        "▶ Processar agora",
        type="primary",
        use_container_width=True,
        disabled=(not todos_os_estados and not municipios_selecionados),
    )
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
        st.download_button("⬇ Download",data=result["bytes"],file_name=result["name"],mime=result.get("mime","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),use_container_width=True)
        st.caption(result["cloud"])
    else:
        st.caption("O arquivo Excel aparecerá aqui após o processamento.")
    st.markdown('</div>',unsafe_allow_html=True)

if executar:
    pasta_temporaria = Path(
        tempfile.mkdtemp(prefix="rreo_cloud_")
    )

    try:
        # Um único fluxo para os três modos:
        # 1) Município; 2) Estado; 3) Todos os Estados.
        # A diferença entre eles é apenas a lista de trabalhos montada abaixo.
        trabalhos: list[dict[str, Any]] = []

        if todos_os_estados:
            modo_execucao = "Todos os Estados"
            uf_saida = "BRASIL"
            municipio_saida = None

            workbook_nacional = load_workbook(
                PLANILHA_BASE,
                read_only=False,
                data_only=False,
            )
            worksheet_nacional = escolher_aba_principal(
                workbook_nacional
            )

            try:
                for estado_item in estados_cloud:
                    uf_item = extrair_uf(estado_item)

                    if not uf_item:
                        logs.append(
                            f"{datetime.now().strftime('%H:%M:%S')}  "
                            f"UF não identificada: {estado_item}"
                        )
                        continue

                    arquivos_item = carregar_pdfs_estado(estado_item)
                    municipios_item = carregar_municipios(
                        worksheet_nacional,
                        uf_item,
                    )

                    trabalhos.append(
                        {
                            "estado_cloud": estado_item,
                            "uf": uf_item,
                            "arquivos": arquivos_item,
                            "municipios": municipios_item,
                        }
                    )
            finally:
                workbook_nacional.close()

        else:
            modo_execucao = modo
            uf_saida = uf
            municipio_saida = municipio_selecionado

            trabalhos.append(
                {
                    "estado_cloud": estado_cloud,
                    "uf": uf,
                    "arquivos": (
                        arquivos_pdf
                        if modo == "Estado inteiro"
                        else arquivos_selecionados
                    ),
                    "municipios": (
                        municipios
                        if modo == "Estado inteiro"
                        else municipios_selecionados
                    ),
                }
            )

        # A planilha-base é copiada e aberta uma única vez, independentemente
        # do modo escolhido. Assim, a estrutura de saída permanece a mesma.
        caminho_saida = pasta_temporaria / gerar_nome_saida(
            uf_saida,
            modo_execucao,
            municipio_saida,
            operacao,
        )

        shutil.copy2(
            PLANILHA_BASE,
            caminho_saida,
        )

        workbook = load_workbook(caminho_saida)
        worksheet = escolher_aba_principal(workbook)
        colunas_codigos = localizar_colunas_codigos(
            worksheet,
            CODIGOS_RREO,
        )

        total = sum(len(trabalho["municipios"]) for trabalho in trabalhos)

        state.update({
            "status": "Em andamento", "progress": 0, "current": "Preparando...",
            "success": 0, "errors": 0, "total": total,
        })

        divergencias: list[dict[str, Any]] = []
        missing_rows: list[dict[str, Any]] = []
        processed_ibge: set[str] = set()
        metrics = {
            "PDFs encontrados": sum(len(t["arquivos"]) for t in trabalhos),
            "PDFs processados": 0,
            "Municípios preenchidos": 0,
            "Municípios pendentes": 0,
            "Campos preenchidos": 0,
            "Campos vazios": 0,
            "Erros críticos": 0,
            "Avisos": 0,
            "Upload Drive": "PENDENTE",
            "Operação": operacao,
            "RREO habilitado": "SIM" if PROCESSAR_RREO else "NÃO",
            "FNDE habilitado": "SIM" if PROCESSAR_FNDE else "NÃO",
            "Códigos RREO ativos": ", ".join(CODIGOS_RREO) if PROCESSAR_RREO else "",
            "Programas FNDE ativos": ", ".join(PROGRAMAS_FNDE_ATIVOS) if PROCESSAR_FNDE else "",
            "Data/hora de início": timestamp(),
        }
        progress_slot = st.progress(0, text="Iniciando...")
        status_slot = st.empty()
        processados = 0

        for trabalho in trabalhos:
            uf_item = trabalho["uf"]
            arquivos_rreo = trabalho["arquivos"]
            municipios_item = trabalho["municipios"]
            indice_fnde = _indice_fnde_por_ibge(uf_item, ano) if PROCESSAR_FNDE else {}

            logs.append(f"{datetime.now().strftime('%H:%M:%S')}  Iniciando {uf_item} - {operacao}")
            logbox.code("\n".join(logs[-12:]), language=None)

            for municipio_encontrado in municipios_item:
                processados += 1
                codigo_ibge = municipio_encontrado["codigo_ibge"]
                arquivo_rreo, nota_rreo = localizar_pdf_municipio(municipio_encontrado, arquivos_rreo)
                arquivo_fnde = indice_fnde.get(codigo_ibge)
                identificacao = f"{codigo_ibge} - {municipio_encontrado['nome']}/{uf_item}"
                state["current"] = identificacao
                status_slot.info(f"Processando {processados} de {total}: {identificacao}")

                rreo_values: dict[str, float | None] = {}
                fnde_values: dict[str, float] = {}
                fnde_warnings: list[str] = []
                erros_municipio: list[str] = []
                rreo_count = 0
                fnde_count = 0

                try:
                    if PROCESSAR_RREO:
                        if arquivo_rreo:
                            rreo_values, _ = processar_um_pdf(arquivo_rreo, pasta_temporaria)
                            rreo_count = preencher_resultados(
                                worksheet, municipio_encontrado["row"], rreo_values, colunas_codigos
                            )
                            metrics["PDFs processados"] += 1
                        else:
                            erros_municipio.append("PDF RREO não encontrado")

                    if PROCESSAR_FNDE:
                        if arquivo_fnde:
                            fnde_values, fnde_warnings = _processar_fnde_municipio(arquivo_fnde, pasta_temporaria)
                            fnde_count = _preencher_fnde(
                                worksheet, municipio_encontrado["row"], fnde_values
                            )
                            metrics["PDFs processados"] += 1
                        else:
                            erros_municipio.append("PDF FNDE não encontrado")

                    filled = rreo_count + fnde_count
                    expected = (len(CODIGOS_RREO) if PROCESSAR_RREO else 0) + (
                        len(PROGRAMAS_FNDE_ATIVOS) if PROCESSAR_FNDE else 0
                    )
                    metrics["Campos preenchidos"] += filled
                    metrics["Campos vazios"] += max(expected - filled, 0)
                    metrics["Avisos"] += len(fnde_warnings)

                    if GERAR_LOG_RREO and PROCESSAR_RREO:
                        found_codes = [c for c, v in rreo_values.items() if v is not None]
                        missing_codes = [c for c in CODIGOS_RREO if rreo_values.get(c) is None]
                        append_rreo_log(workbook, {
                            "Data/Hora": timestamp(),
                            "PDF RREO": arquivo_rreo["name"] if arquivo_rreo else "",
                            "Município": municipio_encontrado["nome"],
                            "Código IBGE": codigo_ibge, "UF": uf_item, "Ano": ano,
                            "Estado/Lote": trabalho["estado_cloud"],
                            "Linha da planilha": municipio_encontrado["row"],
                            "Campos RREO preenchidos": rreo_count,
                            "Códigos encontrados": ", ".join(found_codes),
                            "Códigos ausentes": ", ".join(missing_codes),
                            "Status": "OK" if rreo_count else "PARCIAL",
                            "Erro resumido": "PDF RREO não encontrado" if not arquivo_rreo else "",
                            "Método de extração": "GEMINI_TEXTO_COM_FALLBACK_LOCAL",
                        })

                    if GERAR_LOG_FNDE and PROCESSAR_FNDE:
                        found_fnde = [k for k, v in fnde_values.items() if float(v or 0.0) != 0.0]
                        missing_fnde = [k for k in PROGRAMAS_FNDE_ATIVOS if k not in found_fnde]
                        append_fnde_log(workbook, {
                            "Data/Hora": timestamp(),
                            "PDF FNDE": arquivo_fnde["name"] if arquivo_fnde else "",
                            "Município": municipio_encontrado["nome"],
                            "Código IBGE": codigo_ibge, "UF": uf_item, "Ano": ano,
                            "Estado/Lote": trabalho["estado_cloud"],
                            "Linha da planilha": municipio_encontrado["row"],
                            "Campos FNDE preenchidos": fnde_count,
                            "Programas encontrados": ", ".join(found_fnde),
                            "Programas ausentes": ", ".join(missing_fnde),
                            "Valores extraídos": "; ".join(f"{k}={v:.2f}" for k, v in fnde_values.items()),
                            "Status": "OK" if fnde_count else "PARCIAL",
                            "Avisos": "; ".join(fnde_warnings),
                            "Erro resumido": "PDF FNDE não encontrado" if not arquivo_fnde else "",
                        })

                    if filled > 0:
                        state["success"] += 1
                        metrics["Municípios preenchidos"] += 1
                        processed_ibge.add(codigo_ibge)
                    else:
                        state["errors"] += 1
                        metrics["Erros críticos"] += 1

                    if erros_municipio:
                        divergencias.append({
                            "UF": uf_item, "Código IBGE": codigo_ibge,
                            "Município": municipio_encontrado["nome"],
                            "problema": "; ".join(erros_municipio),
                            "nota": nota_rreo if arquivo_rreo else 0,
                        })

                except Exception as error:
                    state["errors"] += 1
                    metrics["Erros críticos"] += 1
                    divergencias.append({
                        "UF": uf_item, "Código IBGE": codigo_ibge,
                        "Município": municipio_encontrado["nome"],
                        "problema": str(error), "nota": 0,
                    })
                    if GERAR_LOG_RREO and PROCESSAR_RREO:
                        append_rreo_log(workbook, {
                            "Data/Hora": timestamp(), "PDF RREO": arquivo_rreo["name"] if arquivo_rreo else "",
                            "Município": municipio_encontrado["nome"], "Código IBGE": codigo_ibge,
                            "UF": uf_item, "Ano": ano, "Estado/Lote": trabalho["estado_cloud"],
                            "Status": "ERRO", "Erro resumido": str(error),
                        })
                    if GERAR_LOG_FNDE and PROCESSAR_FNDE:
                        append_fnde_log(workbook, {
                            "Data/Hora": timestamp(), "PDF FNDE": arquivo_fnde["name"] if arquivo_fnde else "",
                            "Município": municipio_encontrado["nome"], "Código IBGE": codigo_ibge,
                            "UF": uf_item, "Ano": ano, "Estado/Lote": trabalho["estado_cloud"],
                            "Status": "ERRO", "Erro resumido": str(error),
                        })

                state["progress"] = processados / total if total else 1.0
                progress_slot.progress(state["progress"], text=f"Progresso geral: {state['progress'] * 100:.0f}%")
                logs.append(
                    f"{datetime.now().strftime('%H:%M:%S')}  {identificacao}: "
                    f"RREO={rreo_count} campo(s), FNDE={fnde_count} campo(s)"
                )
                logbox.code("\n".join(logs[-12:]), language=None)

        if GERAR_NAO_ENCONTRADOS:
            for trabalho in trabalhos:
                for municipio in trabalho["municipios"]:
                    if municipio["codigo_ibge"] in processed_ibge:
                        continue
                    arquivo, _ = localizar_pdf_municipio(municipio, trabalho["arquivos"])
                    indice_fnde_trabalho = _indice_fnde_por_ibge(trabalho["uf"], ano) if PROCESSAR_FNDE else {}
                    arquivo_fnde_pendente = indice_fnde_trabalho.get(municipio["codigo_ibge"])
                    faltas = []
                    if PROCESSAR_RREO and not arquivo:
                        faltas.append("RREO")
                    if PROCESSAR_FNDE and not arquivo_fnde_pendente:
                        faltas.append("FNDE")
                    missing_rows.append({
                        "Estado/UF": trabalho["uf"],
                        "Código IBGE": municipio["codigo_ibge"],
                        "Município da planilha-base": municipio["nome"],
                        "Situação": "SEM PDF FORNECIDO" if faltas else "PDF FORNECIDO MAS NÃO LIDO",
                        "PDF RREO correspondente": arquivo["name"] if arquivo else "",
                        "PDF FNDE correspondente": arquivo_fnde_pendente["name"] if arquivo_fnde_pendente else "",
                        "Observação": ("Faltando: " + ", ".join(faltas)) if faltas else "Não houve preenchimento seguro durante esta execução.",
                    })
            write_missing(workbook, missing_rows)
            metrics["Municípios pendentes"] = len(missing_rows)

        metrics["Data/hora de fim"] = timestamp()
        metrics["Arquivo de saída"] = caminho_saida.name
        if GERAR_AUDITORIA:
            write_audit(workbook, metrics)

        workbook.save(caminho_saida)
        workbook.close()

        resultado_cloud = upload_result(
            caminho_saida,
            uf_saida,
        )
        dados = caminho_saida.read_bytes()

        st.session_state["last_result"] = {
            "name": caminho_saida.name,
            "bytes": dados,
            "cloud": resultado_cloud["blob_name"],
            "mime": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        }

        state["status"] = "Concluído"
        state["current"] = "Finalizado"
        state["progress"] = 1.0

        logs.append(
            f"{datetime.now().strftime('%H:%M:%S')}  "
            f"Extração concluída: {state['success']} sucesso(s), "
            f"{state['errors']} erro(s)."
        )
        status_slot.success(
            "Processamento concluído. "
            "O Excel foi salvo no Cloud Storage."
        )

        if divergencias:
            st.warning("Alguns arquivos precisam de conferência.")
            st.dataframe(
                divergencias,
                use_container_width=True,
                hide_index=True,
            )

        st.rerun()

    except Exception as error:
        state["status"] = "Falha"
        logs.append(f"ERRO: {error}")
        st.exception(error)

    finally:
        shutil.rmtree(
            pasta_temporaria,
            ignore_errors=True,
        )

st.markdown('<div class="section-card"><div class="section-title">Fluxo Operacional</div><div class="flow"><div class="flow-step"><div class="flow-num">1</div><div><div class="flow-name">Listagem</div><div class="flow-desc">PDFs localizados no Google Cloud Storage</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">2</div><div><div class="flow-name">Extração</div><div class="flow-desc">Gemini lê Receitas Realizadas Até o Bimestre (b)</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">3</div><div><div class="flow-name">Geração</div><div class="flow-desc">Excel preenchido automaticamente</div></div></div><div class="flow-arrow">→</div><div class="flow-step"><div class="flow-num">4</div><div><div class="flow-name">Upload</div><div class="flow-desc">Resultado salvo e liberado</div></div></div></div></div>',unsafe_allow_html=True)
st.markdown('<div class="footerbar">● Sistema operando com Gemini &nbsp;•&nbsp; Extração inteligente &nbsp;•&nbsp; Cache de listagem &nbsp;•&nbsp; Armazenamento seguro na nuvem</div>',unsafe_allow_html=True)
