from __future__ import annotations

COLUNA = "A"
PAPEL = "SEQUENCIAL_GERAL"


def validar(valor, esperado: int | None = None) -> dict:
    ok_tipo = isinstance(valor, int) or (isinstance(valor, float) and valor.is_integer())
    numero = int(valor) if ok_tipo else None
    ok = ok_tipo and (esperado is None or numero == esperado)
    return {"coluna": COLUNA, "papel": PAPEL, "valor": numero, "esperado": esperado, "ok": ok}
