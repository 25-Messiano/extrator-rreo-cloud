from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from core.identificacao_arquivos import (
    codigo_candidato_no_texto,
    identificar_municipio,
    nome_municipio_do_arquivo,
    normalizar_codigo_ibge,
    normalizar_texto,
)


def municipio_do_nome_arquivo(nome_arquivo: str) -> str:
    return nome_municipio_do_arquivo(nome_arquivo)


def _timestamp(valor: Any) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, datetime):
        return valor.timestamp()
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _mesmo_conteudo(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ha = str(a.get("md5_hash") or "").strip()
    hb = str(b.get("md5_hash") or "").strip()
    return bool(ha and hb and ha == hb)


def _forca_metodo(metodo: str) -> int:
    return {
        "IBGE_NOME": 100,
        "NOME_OFICIAL_IBGE_ARQUIVO_DIVERGENTE": 98,
        "NOME_NORMALIZADO": 95,
        "SIMILARIDADE_IBGE_ARQUIVO_DIVERGENTE": 90,
        "SIMILARIDADE": 88,
        "IBGE": 80,
        "NOME_NORMALIZADO_ARQUIVO": 60,
    }.get(str(metodo or ""), 0)


def _selecionar(candidatos: list[dict[str, Any]]) -> dict[str, Any]:
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


def build_rreo_index(
    files: Iterable[dict[str, Any]],
    uf: str = "",
    municipios: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cria indice RREO preservando a identidade oficial da planilha-base.

    O nome/codigo do arquivo sao somente pistas de localizacao. Quando a base
    oficial esta disponivel, o destino de escrita sempre usa nome, UF e IBGE
    vindos dela. Duplicatas sao retiradas da fila e registradas na auditoria.
    """
    por_nome_uf: dict[str, dict[str, Any]] = {}
    por_ibge: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []
    invalidos: list[dict[str, Any]] = []
    uf_normalizada = str(uf or "").upper().strip()
    lista_municipios = list(municipios or [])
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in files:
        nome_arquivo = str(item.get("name") or "")
        resultado = identificar_municipio(nome_arquivo, lista_municipios, uf_normalizada) if lista_municipios else None

        if resultado and resultado.ambiguo:
            invalidos.append({"arquivo": nome_arquivo, "motivo": "MUNICIPIO_AMBIGUO", "confianca": resultado.confianca})
            continue

        if resultado and resultado.identificado:
            nome_oficial = str(resultado.municipio)
            nome_municipio = normalizar_texto(nome_oficial)
            code = normalizar_codigo_ibge(resultado.codigo_ibge)
            metodo = resultado.metodo
            confianca = resultado.confianca
            item_uf = resultado.uf or uf_normalizada
        else:
            # Compatibilidade defensiva quando o chamador nao fornece a base.
            nome_oficial = ""
            nome_municipio = nome_municipio_do_arquivo(nome_arquivo, uf_normalizada)
            code = ""
            metodo = "NOME_NORMALIZADO_ARQUIVO" if nome_municipio else "NAO_IDENTIFICADO"
            confianca = 1.0 if nome_municipio else 0.0
            item_uf = uf_normalizada

        if not nome_municipio:
            invalidos.append({"arquivo": nome_arquivo, "motivo": "MUNICIPIO_AUSENTE_NO_NOME"})
            continue

        codigo_arquivo = codigo_candidato_no_texto(nome_arquivo)
        enriched = dict(item)
        enriched.update({
            "municipio_oficial": nome_oficial,
            "municipio_arquivo": nome_municipio,
            "uf": item_uf,
            "codigo_ibge": code,
            "codigo_ibge_arquivo": codigo_arquivo,
            "ibge_arquivo_divergente": bool(code and codigo_arquivo and codigo_arquivo != code),
            "chave_nome_uf": f"{nome_municipio}|{item_uf}",
            "metodo_identificacao": metodo,
            "confianca_identificacao": confianca,
        })
        chave_grupo = code or enriched["chave_nome_uf"]
        grupos[chave_grupo].append(enriched)

    for _, candidatos in grupos.items():
        selecionado = _selecionar(candidatos)
        ignorados: list[dict[str, Any]] = []
        conflito = False
        for item in candidatos:
            if item is selecionado:
                continue
            identico = _mesmo_conteudo(selecionado, item)
            status = "DUPLICADO_IDENTICO" if identico else "DUPLICADO_CONFLITANTE"
            conflito = conflito or not identico
            reg = {
                "codigo_ibge": selecionado.get("codigo_ibge", ""),
                "municipio": selecionado.get("municipio_oficial") or selecionado.get("municipio_arquivo", ""),
                "selecionado": selecionado.get("name"),
                "ignorado": item.get("name"),
                "status": status,
            }
            duplicados.append(reg)
            ignorados.append(reg)

        escolhido = dict(selecionado)
        escolhido["duplicados_ignorados"] = ignorados
        escolhido["duplicado_conflitante"] = conflito
        escolhido["quantidade_candidatos"] = len(candidatos)
        chave = escolhido["chave_nome_uf"]
        por_nome_uf[chave] = escolhido
        code = normalizar_codigo_ibge(escolhido.get("codigo_ibge"))
        if code:
            por_ibge[code] = escolhido

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
