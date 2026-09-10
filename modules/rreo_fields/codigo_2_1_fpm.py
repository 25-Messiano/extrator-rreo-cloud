from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C2_1,
    description='Cota-Parte FPM',
    semantic_terms=('FPM',),
    excel_column=None,
    excel_letter=None,
    validation_only=True,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
