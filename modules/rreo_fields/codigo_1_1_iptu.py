from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C1_1,
    description='Receita Resultante do Imposto sobre a Propriedade Predial e Territorial Urbana - IPTU',
    semantic_terms=('IPTU', 'PROPRIEDADE PREDIAL'),
    excel_column=16,
    excel_letter='P',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
