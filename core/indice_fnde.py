from __future__ import annotations

import re
from typing import Any, Iterable

from core.validacao import normalizar_codigo_ibge

_PATTERN = re.compile(r"(?<!\d)(\d{7})(?!\d)")


def codigo_ibge_do_nome(name: str) -> str:
    match = _PATTERN.search(str(name or ""))
    return normalizar_codigo_ibge(match.group(1)) if match else ""


def build_fnde_index(files: Iterable[dict[str, Any]], uf: str = "") -> dict[str, Any]:
    por_ibge: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []
    invalidos: list[dict[str, Any]] = []
    for item in files:
        code = codigo_ibge_do_nome(str(item.get("name") or ""))
        if not code:
            invalidos.append({"arquivo": item.get("name", ""), "motivo": "IBGE_AUSENTE_NO_NOME"})
            continue
        enriched = dict(item)
        enriched.update({"codigo_ibge": code, "uf": str(uf).upper(), "metodo_identificacao": "IBGE_NO_NOME"})
        if code in por_ibge:
            duplicados.append({"codigo_ibge": code, "primeiro": por_ibge[code].get("name"), "duplicado": item.get("name")})
            continue
        por_ibge[code] = enriched
    return {"por_ibge": por_ibge, "duplicados": duplicados, "invalidos": invalidos, "total": len(por_ibge)}
