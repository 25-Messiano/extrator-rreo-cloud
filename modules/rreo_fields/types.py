from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RowCode(str, Enum):
    C1_1 = "1.1"
    C1_2 = "1.2"
    C1_3 = "1.3"
    C1_4 = "1.4"
    C2_1 = "2.1"
    C2_1_1 = "2.1.1"
    C2_1_2 = "2.1.2"
    C2_2 = "2.2"
    C2_3 = "2.3"
    C2_4 = "2.4"
    C2_5 = "2.5"
    C2_6 = "2.6"
    C6_1_1 = "6.1.1"
    C6_2 = "6.2"
    C6_2_1 = "6.2.1"


class ColumnRole(str, Enum):
    PREVISAO_ATUALIZADA_A = "PREVISAO_ATUALIZADA_A"
    RECEITAS_REALIZADAS_B = "RECEITAS_REALIZADAS_B"


@dataclass(frozen=True)
class FieldSpec:
    row_code: RowCode
    description: str
    semantic_terms: tuple[str, ...]
    excel_column: int | None
    excel_letter: str | None
    validation_only: bool = False

    @property
    def code(self) -> str:
        return self.row_code.value
