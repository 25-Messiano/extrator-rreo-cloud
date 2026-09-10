from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C2_1_1,
    description='Parcela referente à CF, art. 159, I, alínea b',
    semantic_terms=('159', 'ALINEA B'),
    excel_column=5,
    excel_letter='E',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
