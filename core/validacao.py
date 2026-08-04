from __future__ import annotations

import re
import unicodedata
from typing import Any


CODIGOS_RREO_AUTORIZADOS = (
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "2.1",
    "2.1.1",
    "2.1.2",
    "2.2",
    "2.3",
    "2.4",
    "2.5",
    "2.6",
    "6.1.1",
    "6.2",
    "6.2.1",
)


def normalizar_texto(valor: Any) -> str:
    texto = "" if valor is None else str(valor)

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = texto.upper()

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto,
    )

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def validar_codigos_rreo(
    valores: dict[str, Any] | None,
) -> dict[str, float]:
    origem = valores or {}
    resultado: dict[str, float] = {}

    for codigo in CODIGOS_RREO_AUTORIZADOS:
        valor = origem.get(codigo, 0)

        try:
            resultado[codigo] = round(
                float(valor or 0),
                2,
            )
        except (TypeError, ValueError):
            resultado[codigo] = 0.0

    return resultado
