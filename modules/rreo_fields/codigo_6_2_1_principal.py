from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C6_2_1,
    description='FUNDEB - Complementação da União - VAAF - Principal',
    semantic_terms=('PRINCIPAL', 'VAAF'),
    excel_column=15,
    excel_letter='O',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
