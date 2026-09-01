from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from integrations.google_storage import download_bytes, upload_text

JSON_NACIONAL_PREFIX = "01_Arquivo_dos_Estados_RREO_e_FNDE/03_PLANILHAS_PROCESSADAS/JSON_PROCESSAMENTO/"


def _safe_job_id(job_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(job_id or "job"))


def state_blob_name(year: int | str, job_id: str, uf: str) -> str:
    return f"{JSON_NACIONAL_PREFIX}{int(year)}/{_safe_job_id(job_id)}/estados/{str(uf).upper()}.json"


def status_blob_name(year: int | str, job_id: str) -> str:
    return f"{JSON_NACIONAL_PREFIX}{int(year)}/{_safe_job_id(job_id)}/status.json"


def save_state_checkpoint(year: int | str, job_id: str, uf: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.setdefault("schema", "RREO_FNDE_ESTADO_V1")
    body.setdefault("uf", str(uf).upper())
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    return upload_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True),
        state_blob_name(year, job_id, uf),
        content_type="application/json; charset=utf-8",
    )


def load_state_checkpoint(year: int | str, job_id: str, uf: str) -> dict[str, Any] | None:
    try:
        raw = download_bytes(state_blob_name(year, job_id, uf))
    except Exception:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def save_national_status(year: int | str, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.setdefault("schema", "RREO_FNDE_STATUS_NACIONAL_V1")
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    return upload_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True),
        status_blob_name(year, job_id),
        content_type="application/json; charset=utf-8",
    )


def apply_state_checkpoint(worksheet, checkpoint: dict[str, Any], *, preencher_rreo, preencher_fnde) -> set[str]:
    """Reaplica um estado já concluído ao Excel limpo e devolve os IBGEs restaurados."""
    restored: set[str] = set()
    for item in checkpoint.get("municipios", []) or []:
        try:
            row = int(item.get("row") or 0)
        except (TypeError, ValueError):
            row = 0
        codigo = str(item.get("codigo_ibge") or "").strip()
        if row <= 0 or not codigo:
            continue
        rreo_values = item.get("rreo_values") or {}
        fnde_values = item.get("fnde_values") or {}
        if rreo_values:
            preencher_rreo(worksheet, row, rreo_values)
        if fnde_values:
            preencher_fnde(worksheet, row, fnde_values)
        restored.add(codigo)
    return restored
