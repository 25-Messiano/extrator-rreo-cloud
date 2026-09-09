from __future__ import annotations

from typing import Any

from integrations.gemini_rreo_review import review_rreo_json as gemini_review
from integrations.openai_rreo import review_rreo_json as openai_review


def review_with_available_engines(extraction_json: dict[str, Any]) -> dict[str, Any]:
    """Revisao consultiva multi-IA. Nenhuma IA recebe permissao de gravar Excel."""
    reviews = [gemini_review(extraction_json), openai_review(extraction_json)]
    active = [r for r in reviews if r.get("enabled")]
    requires_review = any(r.get("status") == "REVISAR" for r in active)
    return {
        "tipo": "REVISAO_IA",
        "advisory_only": True,
        "status": "REVISAR" if requires_review else "OK_CONSULTIVO",
        "engines": reviews,
        "regra": "IA NUNCA ESCREVE EXCEL NEM SOBRESCREVE VALIDACAO DETERMINISTICA",
    }
