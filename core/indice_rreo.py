from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from core.validacao import normalizar_texto


def municipio_do_nome_arquivo(nome_arquivo: str) -> str:
    nome = Path(str(nome_arquivo or "")).stem
    nome = re.sub(r"(?i)^RREO[_\s-]*MUNICIPAL[_\s-]*\d{4}A?", "", nome)
    nome = re.sub(r"(?i)^[_\s-]*RREO[_\s-]*", "", nome)
    nome = re.sub(r"\s*[-_]\s*[A-Za-z]{2}\s*$", "", nome)
    nome = re.sub(r"[_]+", " ", nome)
    return normalizar_texto(nome)


def build_rreo_index(files: Iterable[dict[str, Any]], uf: str = "") -> dict[str, Any]:
    por_nome_uf: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []
    invalidos: list[dict[str, Any]] = []
    uf_normalizada = str(uf or "").upper()
    for item in files:
        nome_municipio = municipio_do_nome_arquivo(str(item.get("name") or ""))
        if not nome_municipio:
            invalidos.append({"arquivo": item.get("name", ""), "motivo": "MUNICIPIO_AUSENTE_NO_NOME"})
            continue
        chave = f"{nome_municipio}|{uf_normalizada}"
        enriched = dict(item)
        enriched.update({
            "municipio_arquivo": nome_municipio,
            "uf": uf_normalizada,
            "chave_nome_uf": chave,
            "metodo_identificacao": "NOME_EXTERNO",
        })
        if chave in por_nome_uf:
            duplicados.append({
                "chave": chave,
                "primeiro": por_nome_uf[chave].get("name"),
                "duplicado": item.get("name"),
            })
            continue
        por_nome_uf[chave] = enriched
    return {
        "uf": uf_normalizada,
        "por_nome_uf": por_nome_uf,
        "duplicados": duplicados,
        "invalidos": invalidos,
        "total": len(por_nome_uf),
    }


def localizar_por_municipio(index: dict[str, Any], nome: str, uf: str) -> dict[str, Any] | None:
    chave = f"{normalizar_texto(nome)}|{str(uf or '').upper()}"
    return (index or {}).get("por_nome_uf", {}).get(chave)
