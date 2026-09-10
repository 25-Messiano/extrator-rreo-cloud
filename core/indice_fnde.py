from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from core.identificacao_arquivos import (
    codigo_candidato_no_texto,
    identificar_municipio,
    normalizar_codigo_ibge,
)


def codigo_ibge_do_nome(name: str) -> str:
    """Compatibilidade: retorna apenas um codigo oficial de 7 digitos."""
    from core.identificacao_arquivos import codigo_ibge_no_texto
    return codigo_ibge_no_texto(name)


def _timestamp(valor: Any) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, datetime):
        return valor.timestamp()
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _forca_metodo(metodo: str) -> int:
    return {
        "IBGE_NOME": 100,
        "NOME_OFICIAL_IBGE_ARQUIVO_DIVERGENTE": 98,
        "NOME_NORMALIZADO": 95,
        "SIMILARIDADE_IBGE_ARQUIVO_DIVERGENTE": 90,
        "SIMILARIDADE": 88,
        "IBGE": 80,
    }.get(str(metodo or ""), 0)


def _mesmo_conteudo(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Detecta copia binaria quando o Cloud fornece hash confiavel."""
    ha = str(a.get("md5_hash") or "").strip()
    hb = str(b.get("md5_hash") or "").strip()
    return bool(ha and hb and ha == hb)


def _selecionar_candidato(candidatos: list[dict[str, Any]]) -> dict[str, Any]:
    """Escolhe um arquivo por municipio sem alterar a identidade oficial.

    Maior confianca de associacao vence; em empate, prefere o upload mais
    recente. Os demais ficam fora do processamento e registrados na auditoria.
    """
    return max(
        candidatos,
        key=lambda item: (
            _forca_metodo(str(item.get("metodo_identificacao") or "")),
            float(item.get("confianca_identificacao") or 0.0),
            _timestamp(item.get("updated")),
            int(item.get("size") or 0),
            str(item.get("name") or ""),
        ),
    )


def build_fnde_index(
    files: Iterable[dict[str, Any]],
    uf: str = "",
    municipios: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Indexa FNDE usando a planilha-base como autoridade municipal.

    O filename pode ajudar a localizar o PDF, mas nunca corrige/sobrescreve
    nome, UF ou IBGE oficiais da planilha-base. Se o codigo no Cloud estiver
    errado e o nome do municipio estiver correto, o arquivo e associado pelo
    nome e a divergencia fica registrada.

    Duplicatas sao eliminadas *da fila de processamento*, nao apagadas do
    Cloud. Copias binarias sao marcadas como DUPLICADO_IDENTICO; arquivos
    diferentes para o mesmo municipio ficam como DUPLICADO_CONFLITANTE e um
    unico candidato e selecionado de forma deterministica.
    """
    lista_municipios = list(municipios or [])
    uf_norm = str(uf or "").upper().strip()
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalidos: list[dict[str, Any]] = []

    for item in files:
        nome = str(item.get("name") or "")
        if not lista_municipios:
            # Sem base oficial nao ha como cumprir a regra de autoridade.
            invalidos.append({"arquivo": nome, "motivo": "PLANILHA_BASE_MUNICIPIOS_AUSENTE"})
            continue

        resultado = identificar_municipio(nome, lista_municipios, uf_norm)
        if resultado.ambiguo:
            invalidos.append({
                "arquivo": nome,
                "motivo": "MUNICIPIO_AMBIGUO",
                "confianca": resultado.confianca,
            })
            continue
        if not resultado.identificado:
            invalidos.append({
                "arquivo": nome,
                "motivo": "MUNICIPIO_NAO_IDENTIFICADO",
                "nome_normalizado": resultado.nome_normalizado,
            })
            continue

        code_oficial = normalizar_codigo_ibge(resultado.codigo_ibge)
        if not code_oficial:
            invalidos.append({"arquivo": nome, "motivo": "IBGE_OFICIAL_AUSENTE_NA_BASE"})
            continue

        codigo_arquivo = codigo_candidato_no_texto(nome)
        divergencia_ibge = bool(codigo_arquivo and codigo_arquivo != code_oficial)
        enriched = dict(item)
        enriched.update({
            # IDENTIDADE OFICIAL: sempre vem da planilha-base.
            "codigo_ibge": code_oficial,
            "municipio_oficial": resultado.municipio,
            "uf": resultado.uf or uf_norm,
            # Evidencia do arquivo serve apenas para auditoria.
            "codigo_ibge_arquivo": codigo_arquivo,
            "ibge_arquivo_divergente": divergencia_ibge,
            "municipio_arquivo": resultado.nome_normalizado,
            "metodo_identificacao": resultado.metodo,
            "confianca_identificacao": resultado.confianca,
        })
        grupos[code_oficial].append(enriched)

    por_ibge: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []

    for code, candidatos in grupos.items():
        selecionado = _selecionar_candidato(candidatos)
        ignorados: list[dict[str, Any]] = []
        conflito = False

        for item in candidatos:
            if item is selecionado:
                continue
            identico = _mesmo_conteudo(selecionado, item)
            status = "DUPLICADO_IDENTICO" if identico else "DUPLICADO_CONFLITANTE"
            conflito = conflito or not identico
            registro = {
                "codigo_ibge": code,
                "municipio": selecionado.get("municipio_oficial", ""),
                "selecionado": selecionado.get("name"),
                "ignorado": item.get("name"),
                "status": status,
                "motivo_selecao": selecionado.get("metodo_identificacao", ""),
            }
            duplicados.append(registro)
            ignorados.append(registro)

        escolhido = dict(selecionado)
        escolhido["duplicados_ignorados"] = ignorados
        escolhido["duplicado_conflitante"] = conflito
        escolhido["quantidade_candidatos"] = len(candidatos)
        por_ibge[code] = escolhido

    return {
        "por_ibge": por_ibge,
        "duplicados": duplicados,
        "invalidos": invalidos,
        "total": len(por_ibge),
    }
