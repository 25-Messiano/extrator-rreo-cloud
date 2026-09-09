from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C2_1_2,
    description='Parcela referente à CF, art. 159, I, alíneas d e e',
    semantic_terms=('159', 'ALINEAS D E E'),
    excel_column=6,
    excel_letter='F',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
