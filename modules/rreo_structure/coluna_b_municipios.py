from __future__ import annotations

COLUNA = "B"
PAPEL = "SEQUENCIAL_MUNICIPIO_UF"


def validar(valor, esperado: int | None, eh_cabecalho_estado: bool = False) -> dict:
    if eh_cabecalho_estado:
        ok = valor in (None, "")
        return {"coluna": COLUNA, "papel": PAPEL, "valor": valor, "esperado": None, "ok": ok}
    ok_tipo = isinstance(valor, int) or (isinstance(valor, float) and valor.is_integer())
    numero = int(valor) if ok_tipo else None
    ok = ok_tipo and esperado is not None and numero == esperado
    return {"coluna": COLUNA, "papel": PAPEL, "valor": numero, "esperado": esperado, "ok": ok}
