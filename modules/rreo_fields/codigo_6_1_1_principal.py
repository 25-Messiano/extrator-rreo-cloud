from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C6_1_1,
    description='FUNDEB - Impostos e Transferências de Impostos - Principal',
    semantic_terms=('PRINCIPAL', 'FUNDEB'),
    excel_column=14,
    excel_letter='N',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
