from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C1_2,
    description='Receita Resultante do Imposto sobre Transmissão Inter Vivos - ITBI',
    semantic_terms=('ITBI', 'TRANSMISSAO INTER VIVOS'),
    excel_column=18,
    excel_letter='R',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
