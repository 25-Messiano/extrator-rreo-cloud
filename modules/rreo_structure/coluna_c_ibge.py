from __future__ import annotations
import re

COLUNA = "C"
PAPEL = "IDENTIFICADOR_OFICIAL"


def normalizar(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\D", "", str(valor))


def validar(valor, eh_municipio: bool) -> dict:
    ibge = normalizar(valor)
    if eh_municipio:
        ok = len(ibge) == 7
    else:
        ok = len(ibge) in {1, 2, 7}
    return {"coluna": COLUNA, "papel": PAPEL, "valor_original": valor, "ibge": ibge, "ok": ok}
