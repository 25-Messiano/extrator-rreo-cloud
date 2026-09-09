from __future__ import annotations
from pathlib import Path
from typing import Any
from openpyxl import load_workbook
from .auditor_estrutura_abcd import auditar
from .mapeamento_integrado import load_config, validate_headers


def preflight_planilha(path: str | Path) -> dict[str, Any]:
    structural = auditar(path)
    if not structural["estrutura_abcd_valida"]:
        return {"status": "BLOQUEADO_ABCD", "estrutura": structural, "cabecalho": None}
    wb = load_workbook(path, read_only=True, data_only=False)
    try:
        ws = wb.active
        header_map = validate_headers(ws, load_config())
    finally:
        wb.close()
    return {"status": "PLANILHA_PRONTA", "estrutura": structural, "cabecalho": header_map}
