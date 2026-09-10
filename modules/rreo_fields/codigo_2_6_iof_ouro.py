from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C2_6,
    description='Cota-Parte IOF-Ouro',
    semantic_terms=('IOF', 'OURO'),
    excel_column=20,
    excel_letter='T',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
