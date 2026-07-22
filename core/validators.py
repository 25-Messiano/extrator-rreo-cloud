from __future__ import annotations

import hashlib
from pathlib import Path

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO"
}


def validar_codigo_ibge(codigo: str) -> bool:
    texto = "".join(ch for ch in str(codigo) if ch.isdigit())
    return len(texto) == 7


def validar_uf(uf: str) -> bool:
    return str(uf).strip().upper() in UFS


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
