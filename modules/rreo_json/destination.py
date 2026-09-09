from __future__ import annotations

from typing import Any, Mapping
from openpyxl.worksheet.worksheet import Worksheet

from modules.rreo_structure.mapeamento_integrado import build_destination_json, load_config, validate_headers


def build_destination_record(ws: Worksheet, identity: Mapping[str, Any], validation: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    if validation.get("status") != "VALIDADO_SAFE_JSON":
        raise RuntimeError("Destino bloqueado: JSON de validacao nao esta VALIDADO_SAFE_JSON")
    cfg = load_config()
    validate_headers(ws, cfg)
    record = build_destination_json(ws, identity, values, cfg)
    # Compatibilidade com o pipeline anterior.
    record["aba"] = ws.title
    record["linha"] = (identity.get("melhor_candidato") or {}).get("row")
    record["ibge_registrado"] = (identity.get("melhor_candidato") or {}).get("ibge")
    record["ente_planilha"] = (identity.get("melhor_candidato") or {}).get("ente_planilha")
    return record


def apply_destination_record(ws: Worksheet, destination: Mapping[str, Any], validation: Mapping[str, Any]) -> list[str]:
    if validation.get("status") != "VALIDADO_SAFE_JSON":
        raise RuntimeError("Gravacao bloqueada: validacao insuficiente")
    cfg = load_config()
    validate_headers(ws, cfg)
    written: list[str] = []
    for code, item in (destination.get("destinos") or {}).items():
        if not item.get("autorizado_gravar"):
            continue
        cell = str(item["celula"])
        expected_col = str(cfg["codigos"][code]["destino"])
        if not cell.startswith(expected_col):
            raise RuntimeError(f"Celula divergente para {code}: {cell}")
        target = ws[cell]
        if isinstance(target.value, str) and target.value.startswith("="):
            raise RuntimeError(f"Formula protegida em {cell}")
        target.value = float(item["valor"])
        target.number_format = '#,##0.00;[Red](#,##0.00);-'
        written.append(cell)
    return written
