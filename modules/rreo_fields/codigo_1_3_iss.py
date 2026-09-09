from __future__ import annotations

from modules.rreo_fields.types import FieldSpec, RowCode
from modules.rreo_fields.row_engine import extract_exclusive_field

SPEC = FieldSpec(
    row_code=RowCode.C1_3,
    description='Receita Resultante do Imposto sobre Serviços de Qualquer Natureza - ISS',
    semantic_terms=('ISS', 'SERVICOS DE QUALQUER NATUREZA'),
    excel_column=19,
    excel_letter='S',
    validation_only=False,
)

def extract(text: str) -> dict[str, object]:
    return extract_exclusive_field(text, SPEC)
