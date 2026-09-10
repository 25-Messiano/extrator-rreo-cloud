from __future__ import annotations

import re
from typing import Any

from core.validacao import normalizar_texto
from modules.rreo_fields.types import ColumnRole, FieldSpec
from modules.rreo_fields.coluna_receitas_realizadas_b import extract_b_from_row_block

# O bloco SEMPRE termina no proximo codigo numerico, inclusive totais como "2-".
# Isso impede que 1.4 invada 2-, que 2.1 invada 2.1.1 etc.
_NEXT_CODE = re.compile(r"(?m)^\s*\d+(?:\.\d+)*\s*[-–—]")


def exact_row_pattern(code: str) -> re.Pattern[str]:
    # O codigo precisa estar no inicio logico e terminar antes do hifen.
    # re.escape evita qualquer interpretacao dos pontos como curingas.
    return re.compile(rf"(?m)^\s*{re.escape(code)}\s*[-–—]")


def isolate_exact_row_block(text: str, code: str, *, max_chars: int = 1400) -> str:
    match = exact_row_pattern(code).search(text or "")
    if not match:
        return ""
    after = text[match.end(): min(len(text), match.start() + max_chars)]
    next_match = _NEXT_CODE.search(after)
    end = match.end() + next_match.start() if next_match else min(len(text), match.start() + max_chars)
    return text[match.start():end].strip()


def validate_semantic_identity(block: str, spec: FieldSpec) -> tuple[bool, str]:
    normalized = normalizar_texto(block)
    if not normalized:
        return False, "LINHA_NAO_ENCONTRADA"
    terms = tuple(normalizar_texto(x) for x in spec.semantic_terms if x)
    if terms and not any(term in normalized for term in terms):
        return False, f"ROTULO_NAO_CONFIRMADO:{spec.code}"
    return True, "OK"


def extract_exclusive_field(text: str, spec: FieldSpec) -> dict[str, Any]:
    block = isolate_exact_row_block(text, spec.code)
    semantic_ok, semantic_status = validate_semantic_identity(block, spec)
    if not semantic_ok:
        return {
            "code": spec.code,
            "value": None,
            "row_block": block,
            "semantic_ok": False,
            "status": semantic_status,
            "column_role": ColumnRole.RECEITAS_REALIZADAS_B.value,
        }
    result = extract_b_from_row_block(block)
    return {
        "code": spec.code,
        "value": result["value"],
        "previsao_a_seen": result["previsao_a_seen"],
        "row_block": block,
        "semantic_ok": True,
        "status": result["status"],
        "column_role": ColumnRole.RECEITAS_REALIZADAS_B.value,
        "excel_column": spec.excel_column,
        "excel_letter": spec.excel_letter,
        "validation_only": spec.validation_only,
    }
