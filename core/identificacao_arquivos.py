from __future__ import annotations

"""Identificacao unificada e tolerante de arquivos RREO/FNDE.

Prioridade de associacao:
1. codigo IBGE municipal de 7 digitos;
2. nome oficial normalizado + UF;
3. similaridade alta dentro da mesma UF, com bloqueio de ambiguidades.

A regra e deliberadamente conservadora: quando dois municipios ficam muito
proximos na pontuacao, nenhum e escolhido automaticamente.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable, Mapping

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
}

ESTADO_PARA_UF = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE",
    "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}

IBGE_RE = re.compile(r"(?<!\d)(\d{7})(?!\d)")
ANO_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# Marcadores que descrevem o documento e nao o municipio.
RUIDO = {
    "RREO", "FNDE", "MUNICIPAL", "MUNICIPIO", "MUNICIPIOS", "RELATORIO",
    "RELATORIOS", "PDF", "SIGEFWEB", "SIOPE", "ARQUIVO", "ARQUIVOS",
    "ESTADO", "ESTADOS", "BRASIL", "EXTRATO", "DEMONSTRATIVO",
}


@dataclass(frozen=True)
class ResultadoIdentificacao:
    codigo_ibge: str = ""
    municipio: str = ""
    uf: str = ""
    metodo: str = "NAO_IDENTIFICADO"
    confianca: float = 0.0
    ambiguo: bool = False
    nome_normalizado: str = ""

    @property
    def identificado(self) -> bool:
        return bool(self.codigo_ibge or self.municipio)


def normalizar_texto(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.upper()
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return " ".join(texto.split())


def normalizar_codigo_ibge(valor: Any) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos if len(digitos) == 7 else ""


def codigo_ibge_no_texto(valor: Any) -> str:
    match = IBGE_RE.search(str(valor or ""))
    return normalizar_codigo_ibge(match.group(1)) if match else ""


def identificar_uf(valor: Any, uf_esperada: str = "") -> str:
    esperada = str(uf_esperada or "").upper().strip()
    if esperada in UF_VALIDAS:
        return esperada

    texto = normalizar_texto(valor)
    if not texto:
        return ""

    tokens = texto.split()
    # Prioriza siglas explicitas como tokens completos, inclusive antes/depois do ano.
    for token in reversed(tokens):
        if token in UF_VALIDAS:
            return token

    for estado, uf in sorted(ESTADO_PARA_UF.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?:^| ){re.escape(estado)}(?: |$)", texto):
            return uf
    return ""


def _nome_base(valor: Any, uf: str = "") -> str:
    stem = Path(str(valor or "")).stem
    texto = normalizar_texto(stem)
    if not texto:
        return ""

    texto = IBGE_RE.sub(" ", texto)
    texto = ANO_RE.sub(" ", texto)
    tokens = []
    uf_norm = str(uf or "").upper().strip()
    for token in texto.split():
        if token in RUIDO:
            continue
        if token in UF_VALIDAS:
            continue
        if uf_norm and token == uf_norm:
            continue
        tokens.append(token)
    return " ".join(tokens).strip()


def nome_municipio_do_arquivo(valor: Any, uf: str = "") -> str:
    """Retorna a parte do filename que provavelmente representa o municipio."""
    return _nome_base(valor, uf)


def similaridade(a: Any, b: Any) -> float:
    a_norm = normalizar_texto(a)
    b_norm = normalizar_texto(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _campo(item: Any, nome: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(nome, default)
    return getattr(item, nome, default)


def _municipios_da_uf(municipios: Iterable[Any], uf: str) -> list[Any]:
    target = str(uf or "").upper().strip()
    return [m for m in municipios if str(_campo(m, "uf", "")).upper().strip() == target]


def identificar_municipio(
    nome_arquivo: str,
    municipios: Iterable[Any],
    uf: str = "",
    *,
    limite_similaridade: float = 0.90,
    margem_ambiguidade: float = 0.04,
) -> ResultadoIdentificacao:
    """Associa um arquivo a municipio oficial com regras em camadas."""
    todos = list(municipios)
    uf_detectada = identificar_uf(nome_arquivo, uf)
    candidatos = _municipios_da_uf(todos, uf_detectada) if uf_detectada else todos

    codigo = codigo_ibge_no_texto(nome_arquivo)
    if codigo:
        por_codigo = [m for m in todos if normalizar_codigo_ibge(_campo(m, "codigo_ibge")) == codigo]
        if len(por_codigo) == 1:
            m = por_codigo[0]
            return ResultadoIdentificacao(
                codigo_ibge=codigo,
                municipio=str(_campo(m, "nome", "")),
                uf=str(_campo(m, "uf", uf_detectada)).upper(),
                metodo="IBGE",
                confianca=1.0,
                nome_normalizado=normalizar_texto(_campo(m, "nome", "")),
            )

    nome_base = nome_municipio_do_arquivo(nome_arquivo, uf_detectada)
    if not nome_base or not candidatos:
        return ResultadoIdentificacao(uf=uf_detectada, nome_normalizado=nome_base)

    exatos = [m for m in candidatos if normalizar_texto(_campo(m, "nome", "")) == nome_base]
    if len(exatos) == 1:
        m = exatos[0]
        return ResultadoIdentificacao(
            codigo_ibge=normalizar_codigo_ibge(_campo(m, "codigo_ibge")),
            municipio=str(_campo(m, "nome", "")),
            uf=str(_campo(m, "uf", uf_detectada)).upper(),
            metodo="NOME_NORMALIZADO",
            confianca=1.0,
            nome_normalizado=nome_base,
        )

    pontuados = sorted(
        ((similaridade(nome_base, _campo(m, "nome", "")), m) for m in candidatos),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not pontuados or pontuados[0][0] < limite_similaridade:
        return ResultadoIdentificacao(uf=uf_detectada, confianca=pontuados[0][0] if pontuados else 0.0, nome_normalizado=nome_base)

    melhor_nota, melhor = pontuados[0]
    segunda_nota = pontuados[1][0] if len(pontuados) > 1 else 0.0
    if segunda_nota >= limite_similaridade and (melhor_nota - segunda_nota) < margem_ambiguidade:
        return ResultadoIdentificacao(
            uf=uf_detectada,
            metodo="AMBIGUO",
            confianca=melhor_nota,
            ambiguo=True,
            nome_normalizado=nome_base,
        )

    return ResultadoIdentificacao(
        codigo_ibge=normalizar_codigo_ibge(_campo(melhor, "codigo_ibge")),
        municipio=str(_campo(melhor, "nome", "")),
        uf=str(_campo(melhor, "uf", uf_detectada)).upper(),
        metodo="SIMILARIDADE",
        confianca=melhor_nota,
        nome_normalizado=nome_base,
    )

