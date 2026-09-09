from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C1_4,
    description='Receita Resultante do Imposto de Renda Retido na Fonte - IRRF',
    semantic_terms=('IRRF', 'RENDA RETIDO'),
    excel_column=17,
    excel_letter='Q',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
