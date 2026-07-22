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

st.set_page_config(
    page_title="Extrator RREO Cloud",
    page_icon="📊",
    layout="wide",
)

st.title("Extrator RREO Cloud")

st.caption(
    "Cloud Storage → processamento → Excel → "
    "Cloud Storage → download no computador"
)

status = health_check()

if not status.get("ok"):
    st.error(
        "Não foi possível conectar ao Google Cloud Storage."
    )

    st.code(
        status.get(
            "message",
            "Erro desconhecido.",
        )
    )

    st.stop()

st.success(
    f"Conectado ao bucket: {status['bucket']}"
)

if not PLANILHA_BASE.exists():
    st.error(
        "A planilha-base não foi encontrada."
    )

    st.code(
        str(PLANILHA_BASE)
    )

    st.stop()

try:
    estados_cloud = carregar_estados_cloud()
except Exception as error:
    st.error(
        "Não foi possível listar os estados do Cloud Storage."
    )

    st.exception(error)
    st.stop()

if not estados_cloud:
    st.warning(
        "Nenhuma pasta de estado foi encontrada no bucket."
    )

    st.stop()

coluna_1, coluna_2 = st.columns(2)

with coluna_1:
    modo = st.radio(
        "Modo de processamento",
        options=[
            "Município único",
            "Estado inteiro",
        ],
        horizontal=True,
    )

with coluna_2:
    estado_cloud = st.selectbox(
        "Estado disponível no Cloud Storage",
        options=estados_cloud,
    )

uf = extrair_uf(
    estado_cloud
)

if not uf:
    uf_manual = st.selectbox(
        "Não consegui reconhecer a UF da pasta. Selecione:",
        options=sorted(
            CODIGOS_UF.keys()
        ),
    )

    uf = uf_manual

st.info(
    f"UF reconhecida: {uf} — "
    f"código estadual IBGE: {CODIGOS_UF[uf]}"
)

try:
    arquivos_pdf = carregar_pdfs_estado(
        estado_cloud
    )
except Exception as error:
    st.error(
        "Não foi possível listar os PDFs desse estado."
    )

    st.exception(error)
    st.stop()

st.metric(
    "PDFs encontrados",
    len(arquivos_pdf),
)

if not arquivos_pdf:
    st.warning(
        "Não existem PDFs na pasta selecionada."
    )

    st.stop()

try:
    workbook_consulta = load_workbook(
        PLANILHA_BASE,
        read_only=False,
        data_only=False,
    )

    worksheet_consulta = escolher_aba_principal(
        workbook_consulta
    )

    municipios = carregar_municipios(
        worksheet_consulta,
        uf,
    )

    workbook_consulta.close()

except Exception as error:
    st.error(
        "Não foi possível ler a planilha-base."
    )

    st.exception(error)
    st.stop()

if not municipios:
    st.error(
        f"Nenhum município de {uf} foi encontrado "
        "na planilha-base."
    )

    st.stop()

municipio_selecionado = None
arquivo_selecionado = None

if modo == "Município único":
    municipio_selecionado = st.selectbox(
        "Selecione o município",
        options=municipios,
        format_func=lambda item: (
            f"{item['codigo_ibge']} — "
            f"{item['nome']}/{item['uf']}"
        ),
    )

    arquivo_selecionado, nota_pdf = (
        localizar_pdf_municipio(
            municipio_selecionado,
            arquivos_pdf,
        )
    )

    if arquivo_selecionado:
        st.write(
            "**PDF sugerido:** "
            f"`{arquivo_selecionado['name']}`"
        )

        st.caption(
            "Correspondência do nome: "
            f"{nota_pdf * 100:.1f}%"
        )

        nomes_arquivos = [
            arquivo["name"]
            for arquivo in arquivos_pdf
        ]

        nome_escolhido = st.selectbox(
            "Confirme ou altere o PDF",
            options=nomes_arquivos,
            index=nomes_arquivos.index(
                arquivo_selecionado["name"]
            ),
        )

        arquivo_selecionado = next(
            arquivo
            for arquivo in arquivos_pdf
            if arquivo["name"] == nome_escolhido
        )

    else:
        st.warning(
            "O PDF do município não foi identificado "
            "automaticamente."
        )

        nome_escolhido = st.selectbox(
            "Selecione manualmente o PDF",
            options=[
                arquivo["name"]
                for arquivo in arquivos_pdf
            ],
        )

        arquivo_selecionado = next(
            arquivo
            for arquivo in arquivos_pdf
            if arquivo["name"] == nome_escolhido
        )

st.divider()

executar = st.button(
    "Processar agora",
    type="primary",
    use_container_width=True,
)

if executar:
    pasta_temporaria = Path(
        tempfile.mkdtemp(
            prefix="rreo_cloud_"
        )
    )

    try:
        caminho_saida = (
            pasta_temporaria
            / gerar_nome_saida(
                uf=uf,
                modo=modo,
                municipio=municipio_selecionado,
            )
        )

        shutil.copy2(
            PLANILHA_BASE,
            caminho_saida,
        )

        workbook = load_workbook(
            caminho_saida
        )

        worksheet = escolher_aba_principal(
            workbook
        )

        colunas_codigos = localizar_colunas_codigos(
            worksheet,
            CODIGOS_RREO,
        )

        codigos_ausentes = [
            codigo
            for codigo in CODIGOS_RREO
            if codigo not in colunas_codigos
        ]

        if codigos_ausentes:
            st.warning(
                "Algumas colunas não foram localizadas: "
                + ", ".join(codigos_ausentes)
            )

        sucessos = 0
        falhas = 0
        divergencias: list[dict[str, Any]] = []

        if modo == "Município único":
            arquivos_processar = [
                arquivo_selecionado
            ]

            municipios_alvo = [
                municipio_selecionado
            ]

        else:
            arquivos_processar = arquivos_pdf
            municipios_alvo = municipios

        progresso = st.progress(0)

        mensagem = st.empty()

        total = len(arquivos_processar)

        for indice, arquivo_pdf in enumerate(
            arquivos_processar,
            start=1,
        ):
            mensagem.write(
                f"Processando {indice} de {total}: "
                f"{arquivo_pdf['name']}"
            )

            try:
                resultados, texto_pdf = processar_um_pdf(
                    arquivo_pdf,
                    pasta_temporaria,
                )

                if modo == "Município único":
                    municipio_encontrado = (
                        municipio_selecionado
                    )

                    nota = 1.0
                    origem = "seleção manual"

                else:
                    (
                        municipio_encontrado,
                        nota,
                        origem,
                    ) = localizar_municipio_pdf(
                        arquivo_pdf,
                        texto_pdf,
                        municipios_alvo,
                    )

                if municipio_encontrado is None:
                    falhas += 1

                    divergencias.append(
                        {
                            "arquivo": arquivo_pdf["name"],
                            "problema": (
                                "Município não identificado"
                            ),
                            "nota": nota,
                        }
                    )

                else:
                    preencher_resultados(
                        worksheet=worksheet,
                        row=municipio_encontrado["row"],
                        resultados=resultados,
                        colunas_codigos=colunas_codigos,
                    )

                    sucessos += 1

                    if nota < 0.88:
                        divergencias.append(
                            {
                                "arquivo": arquivo_pdf["name"],
                                "problema": (
                                    "Nome aproximado: "
                                    f"{municipio_encontrado['nome']}/"
                                    f"{municipio_encontrado['uf']} "
                                    f"({origem})"
                                ),
                                "nota": nota,
                            }
                        )

            except Exception as error:
                falhas += 1

                divergencias.append(
                    {
                        "arquivo": arquivo_pdf["name"],
                        "problema": str(error),
                        "nota": 0.0,
                    }
                )

            progresso.progress(
                indice / total
            )

        workbook.save(
            caminho_saida
        )

        workbook.close()

        mensagem.success(
            "Processamento concluído."
        )

        resultado_cloud = upload_result(
            local_path=caminho_saida,
            state=uf,
        )

        dados_excel = caminho_saida.read_bytes()

        st.success(
            "Planilha gerada e salva automaticamente "
            "no Google Cloud Storage."
        )

        coluna_a, coluna_b, coluna_c = st.columns(3)

        coluna_a.metric(
            "Processados",
            total,
        )

        coluna_b.metric(
            "Sucessos",
            sucessos,
        )

        coluna_c.metric(
            "Falhas",
            falhas,
        )

        st.write(
            "**Arquivo no Cloud:** "
            f"`{resultado_cloud['blob_name']}`"
        )

        st.download_button(
            label="Baixar planilha no computador",
            data=dados_excel,
            file_name=caminho_saida.name,
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        if divergencias:
            st.warning(
                "Alguns arquivos precisam de conferência."
            )

            st.dataframe(
                divergencias,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as error:
        st.error(
            "O processamento não foi concluído."
        )

        st.exception(error)

    finally:
        shutil.rmtree(
            pasta_temporaria,
            ignore_errors=True,
        )
