from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integrations.google_storage import (
    find_fnde_folder,
    find_rreo_folder,
    list_fnde_pdfs,
    list_pdfs,
    list_states,
)


@dataclass
class ArquivosEstado:
    uf: str
    ano: int
    pasta_rreo: str | None
    pasta_fnde: str | None
    rreo: list[dict[str, Any]]
    fnde: list[dict[str, Any]]


def listar_ufs(ano: int, usar_rreo: bool, usar_fnde: bool) -> list[str]:
    folders = list_states(year=ano, include_rreo=usar_rreo, include_fnde=usar_fnde)
    result: set[str] = set()
    for folder in folders:
        suffix = str(folder).rstrip("/").split("_")[-1].upper()
        if len(suffix) == 2:
            result.add(suffix)
    return sorted(result)


def carregar_estado(uf: str, ano: int, usar_rreo: bool, usar_fnde: bool) -> ArquivosEstado:
    target = str(uf).upper()
    rreo_folder = find_rreo_folder(target, ano) if usar_rreo else None
    fnde_folder = find_fnde_folder(target, ano) if usar_fnde else None
    rreo_files = list_pdfs(rreo_folder or target, ano) if rreo_folder else []
    fnde_files = list_fnde_pdfs(fnde_folder, ano) if fnde_folder else []
    return ArquivosEstado(target, int(ano), rreo_folder, fnde_folder, rreo_files, fnde_files)
