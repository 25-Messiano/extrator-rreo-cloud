from __future__ import annotations

import os
from typing import Any

from integrations.gemini import extract_rreo_values


def enabled() -> bool:
    return bool((os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip())


def review_rreo_json(payload: dict[str, Any]) -> dict[str, Any]:
    """Revisor Gemini opcional. Nao escreve Excel e nao substitui o SAFE deterministico."""
    if not enabled():
        return {"engine": "GEMINI", "enabled": False, "status": "SEM_CHAVE", "advisory_only": True}
    evidence = payload.get("evidencias") or {}
    codes = list((payload.get("valores") or {}).keys())
    text_parts: list[str] = []
    for code in codes:
        block = (evidence.get(code) or {}).get("row_block")
        if block:
            text_parts.append(str(block))
    if not text_parts:
        return {"engine": "GEMINI", "enabled": True, "status": "SEM_EVIDENCIA", "advisory_only": True}
    result = extract_rreo_values("\n".join(text_parts), codes)
    primary = payload.get("valores") or {}
    divergences = {}
    for code in codes:
        a, b = primary.get(code), result.get(code)
        if a is None and b is None:
            continue
        if a is None or b is None or abs(float(a) - float(b)) > 0.01:
            divergences[code] = {"deterministico": a, "gemini": b}
    return {
        "engine": "GEMINI",
        "enabled": True,
        "status": "OK" if not divergences else "REVISAR",
        "advisory_only": True,
        "divergencias": divergences,
        "valores": result,
    }
