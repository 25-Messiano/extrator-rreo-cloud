from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.identificacao_arquivos import identificar_uf
from integrations.google_storage import (
    find_fnde_folder,
    find_rreo_folder,
    list_fnde_pdfs_by_uf,
    list_rreo_pdfs_by_uf,
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
    result = {identificar_uf(folder) for folder in folders}
    return sorted(uf for uf in result if uf)


def carregar_estado(uf: str, ano: int, usar_rreo: bool, usar_fnde: bool) -> ArquivosEstado:
    target = str(uf).upper().strip()
    rreo_folder = find_rreo_folder(target, ano) if usar_rreo else None
    fnde_folder = find_fnde_folder(target, ano) if usar_fnde else None
    rreo_files = list_rreo_pdfs_by_uf(target, ano) if usar_rreo else []
    fnde_files = list_fnde_pdfs_by_uf(target, ano) if usar_fnde else []
    return ArquivosEstado(target, int(ano), rreo_folder, fnde_folder, rreo_files, fnde_files)
