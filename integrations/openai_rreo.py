from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def review_rreo_json(payload: dict[str, Any], *, model: str | None = None) -> dict[str, Any]:
    """Revisor opcional. Nunca escreve Excel e nunca substitui validacao deterministica."""
    if not enabled():
        return {"engine": "OPENAI", "enabled": False, "status": "SEM_CHAVE", "advisory_only": True}
    try:
        from openai import OpenAI
    except ImportError as exc:
        return {"engine": "OPENAI", "enabled": True, "status": "SDK_AUSENTE", "error": str(exc), "advisory_only": True}
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = (
        "Revise este JSON de extracao RREO. Verifique somente coerencia entre codigo, descricao/evidencia e valor da coluna "
        "RECEITAS REALIZADAS Ate o Bimestre (b). Nao proponha gravacao em Excel. Responda JSON com status OK ou REVISAR e observacoes.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    response = client.responses.create(model=model or DEFAULT_MODEL, input=prompt)
    text = getattr(response, "output_text", "") or ""
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {"status": "REVISAR", "observacoes": text}
    return {"engine": "OPENAI", "enabled": True, "model": model or DEFAULT_MODEL, "advisory_only": True, "result": parsed}
