from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


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

PROGRAMAS_FNDE_AUTORIZADOS = (
    "PNAE",
    "PNATE",
    "PDDE",
    "QSE",
)


def normalizar_texto(valor: Any) -> str:
    texto = unicodedata.normalize(
        "NFKD",
        str(valor or ""),
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = re.sub(
        r"[^A-Za-z0-9]+",
        " ",
        texto,
    ).upper()

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def normalizar_codigo_ibge(valor: Any) -> str:
    digitos = re.sub(
        r"\D",
        "",
        str(valor or ""),
    )

    if not digitos:
        return ""

    # Um código IBGE municipal válido possui sete dígitos.
    # Não inventa código quando a entrada possui mais de sete.
    if len(digitos) > 7:
        return ""

    return digitos.zfill(7)


def validar_codigos_rreo(
    codigos: Iterable[str] | None,
) -> list[str]:
    solicitados = list(
        dict.fromkeys(
            str(codigo).strip()
            for codigo in (codigos or CODIGOS_RREO_AUTORIZADOS)
            if str(codigo).strip()
        )
    )

    invalidos = [
        codigo
        for codigo in solicitados
        if codigo not in CODIGOS_RREO_AUTORIZADOS
    ]

    if invalidos:
        raise ValueError(
            "Códigos RREO não autorizados: "
            + ", ".join(invalidos)
        )

    return solicitados


def validar_programas_fnde(
    programas: Iterable[str] | None,
) -> list[str]:
    solicitados = list(
        dict.fromkeys(
            str(programa).upper().strip()
            for programa in (programas or PROGRAMAS_FNDE_AUTORIZADOS)
            if str(programa).strip()
        )
    )

    invalidos = [
        programa
        for programa in solicitados
        if programa not in PROGRAMAS_FNDE_AUTORIZADOS
    ]

    if invalidos:
        raise ValueError(
            "Programas FNDE não autorizados: "
            + ", ".join(invalidos)
        )

    return solicitados


def valores_seguros(
    valores: dict[str, Any] | None,
    permitidos: Iterable[str],
) -> dict[str, float | None]:
    origem = valores or {}
    resultado: dict[str, float | None] = {}

    for chave in permitidos:
        valor = origem.get(chave)

        if valor in (None, ""):
            resultado[chave] = None
            continue

        try:
            resultado[chave] = round(
                float(valor),
                2,
            )
        except (TypeError, ValueError):
            resultado[chave] = None

    return resultado
