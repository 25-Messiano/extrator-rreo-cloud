"""Compatibilidade com versões anteriores.

A política atual usa o nome externo do arquivo para localizar o RREO. O conteúdo
interno é conferido apenas durante a extração e serve para auditoria.
"""
from __future__ import annotations

from typing import Any

from core.indice_rreo import build_rreo_index, localizar_por_municipio


def build_rreo_internal_index(*, uf: str, year: int, files: list[dict[str, Any]], municipalities=None, max_workers=1, use_gemini=False) -> dict[str, Any]:
    result = build_rreo_index(files, uf=uf, municipios=municipalities or [])
    result.update({"ano": int(year), "politica": "NOME_EXTERNO", "nao_identificados": result.pop("invalidos", [])})
    return result
