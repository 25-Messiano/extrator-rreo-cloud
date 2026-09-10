from __future__ import annotations

from modules.rreo_fields.types import ColumnRole

ROLE = ColumnRole.PREVISAO_ATUALIZADA_A
COLLECT = False
WRITE_TO_EXCEL = False


def register_only(value: float | None) -> dict[str, object]:
    """Reconhece a coluna (a), mas PROIBE seu uso como dado de saida.

    O valor pode ser mantido apenas como evidencia diagnostica para confirmar que
    a primeira coluna monetaria foi vista. Nunca retorna valor gravavel.
    """
    return {
        "role": ROLE.value,
        "seen": value is not None,
        "diagnostic_value": value,
        "collect": False,
        "write_to_excel": False,
        "status": "PROIBIDO_PARA_GRAVACAO",
    }
