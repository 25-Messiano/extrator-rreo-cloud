from __future__ import annotations

from typing import Any, Iterable

from core.identificacao_arquivos import (
    identificar_municipio,
    nome_municipio_do_arquivo,
    normalizar_codigo_ibge,
    normalizar_texto,
)


def municipio_do_nome_arquivo(nome_arquivo: str) -> str:
    return nome_municipio_do_arquivo(nome_arquivo)


def build_rreo_index(
    files: Iterable[dict[str, Any]],
    uf: str = "",
    municipios: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cria indice RREO tolerante, preservando seguranca por UF."""
    por_nome_uf: dict[str, dict[str, Any]] = {}
    por_ibge: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []
    invalidos: list[dict[str, Any]] = []
    uf_normalizada = str(uf or "").upper().strip()
    lista_municipios = list(municipios or [])

    for item in files:
        nome_arquivo = str(item.get("name") or "")
        resultado = identificar_municipio(nome_arquivo, lista_municipios, uf_normalizada) if lista_municipios else None

        if resultado and resultado.identificado and not resultado.ambiguo:
            nome_municipio = normalizar_texto(resultado.municipio)
            code = normalizar_codigo_ibge(resultado.codigo_ibge)
            metodo = resultado.metodo
            confianca = resultado.confianca
            item_uf = resultado.uf or uf_normalizada
        else:
            nome_municipio = nome_municipio_do_arquivo(nome_arquivo, uf_normalizada)
            code = ""
            metodo = "NOME_NORMALIZADO_ARQUIVO" if nome_municipio else "NAO_IDENTIFICADO"
            confianca = 1.0 if nome_municipio else 0.0
            item_uf = uf_normalizada

        if not nome_municipio:
            invalidos.append({"arquivo": nome_arquivo, "motivo": "MUNICIPIO_AUSENTE_NO_NOME"})
            continue

        chave = f"{normalizar_texto(nome_municipio)}|{item_uf}"
        enriched = dict(item)
        enriched.update({
            "municipio_arquivo": normalizar_texto(nome_municipio),
            "uf": item_uf,
            "codigo_ibge": code,
            "chave_nome_uf": chave,
            "metodo_identificacao": metodo,
            "confianca_identificacao": confianca,
        })

        if chave in por_nome_uf:
            duplicados.append({
                "chave": chave,
                "primeiro": por_nome_uf[chave].get("name"),
                "duplicado": nome_arquivo,
            })
        else:
            por_nome_uf[chave] = enriched
        if code and code not in por_ibge:
            por_ibge[code] = enriched

    return {
        "uf": uf_normalizada,
        "por_nome_uf": por_nome_uf,
        "por_ibge": por_ibge,
        "duplicados": duplicados,
        "invalidos": invalidos,
        "total": len(por_nome_uf),
    }


def localizar_por_municipio(
    index: dict[str, Any],
    nome: str,
    uf: str,
    codigo_ibge: str = "",
) -> dict[str, Any] | None:
    code = normalizar_codigo_ibge(codigo_ibge)
    if code:
        item = (index or {}).get("por_ibge", {}).get(code)
        if item:
            return item
    chave = f"{normalizar_texto(nome)}|{str(uf or '').upper()}"
    return (index or {}).get("por_nome_uf", {}).get(chave)
