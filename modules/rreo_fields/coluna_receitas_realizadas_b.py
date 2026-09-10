from __future__ import annotations

import re

from modules.rreo_fields.types import ColumnRole
from modules.rreo_fields.coluna_previsao_atualizada_a import register_only

ROLE = ColumnRole.RECEITAS_REALIZADAS_B
COLLECT = True
WRITE_TO_EXCEL = True
MONEY_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")


def br_to_float(value: str) -> float:
    return round(float(value.replace(".", "").replace(",", ".")), 2)


def extract_b_from_row_block(block: str) -> dict[str, object]:
    """Extrai SOMENTE a coluna (b) de um bloco ja isolado da linha.

    Regra fechada:
      1o valor monetario = PREVISAO (a), somente evidencia/proibido;
      2o valor monetario = RECEITAS REALIZADAS (b), unico valor gravavel;
      se nao houver exatamente informacao suficiente, retorna None.
    """
    tokens = MONEY_PATTERN.findall(block or "")
    if len(tokens) < 2:
        return {
            "role": ROLE.value,
            "value": None,
            "previsao_a_seen": register_only(br_to_float(tokens[0]) if tokens else None),
            "status": "COLUNA_B_NAO_CONFIRMADA",
        }
    previsao = br_to_float(tokens[0])
    realizada = br_to_float(tokens[1])
    return {
        "role": ROLE.value,
        "value": realizada,
        "previsao_a_seen": register_only(previsao),
        "status": "OK",
    }
