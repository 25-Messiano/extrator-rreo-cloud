from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

CODIGOS_RREO_AUTORIZADOS = (
    "1.1", "1.2", "1.3", "1.4", "2.1", "2.1.1", "2.1.2",
    "2.2", "2.3", "2.4", "2.5", "2.6", "6.1.1", "6.2", "6.2.1",
)
PROGRAMAS_FNDE_AUTORIZADOS = ("PNAE", "PNATE", "PDDE", "QSE")


def normalizar_texto(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).upper()
    return re.sub(r"\s+", " ", text).strip()


def normalizar_codigo_ibge(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(7) if digits else ""


def validar_codigos_rreo(codigos: Iterable[str]) -> list[str]:
    requested = list(dict.fromkeys(str(code).strip() for code in codigos))
    invalid = [code for code in requested if code not in CODIGOS_RREO_AUTORIZADOS]
    if invalid:
        raise ValueError(f"Códigos RREO não autorizados: {', '.join(invalid)}")
    return requested


def validar_programas_fnde(programas: Iterable[str]) -> list[str]:
    requested = list(dict.fromkeys(str(item).upper().strip() for item in programas))
    invalid = [item for item in requested if item not in PROGRAMAS_FNDE_AUTORIZADOS]
    if invalid:
        raise ValueError(f"Programas FNDE não autorizados: {', '.join(invalid)}")
    return requested


def valores_seguros(values: dict[str, Any], allowed: Iterable[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in allowed:
        value = values.get(key)
        if value in (None, ""):
            result[key] = None
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            result[key] = None
            continue
        result[key] = round(number, 2)
    return result
