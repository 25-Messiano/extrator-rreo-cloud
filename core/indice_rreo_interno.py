from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from core.validacao import normalizar_texto


def _fingerprint(files: Iterable[dict[str, Any]]) -> str:
    import hashlib
    data = "|".join(
        sorted(
            f"{item.get('blob_name')}:{item.get('size')}:{item.get('updated')}"
            for item in files
        )
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _municipio_do_nome(nome_arquivo: str) -> str:
    nome = Path(nome_arquivo).stem
    nome = re.sub(
        r"(?i)^RREO[_\s-]*MUNICIPAL[_\s-]*\d{4}A?",
        "",
        nome,
    )
    nome = re.sub(r"(?i)^[_\s-]*RREO[_\s-]*", "", nome)
    nome = re.sub(r"\s*-\s*[A-Za-z]{2}\s*$", "", nome)
    return normalizar_texto(nome)


def build_rreo_internal_index(
    *,
    uf: str,
    year: int,
    files: list[dict[str, Any]],
    municipalities: list[dict[str, Any]],
    max_workers: int = 4,
    use_gemini: bool = False,
) -> dict[str, Any]:
    """Compatibilidade: cria índice leve somente pelo nome externo.

    Não baixa PDFs, não lê conteúdo, não chama Gemini e não troca município.
    O nome interno é conferido apenas durante o processamento e serve para log.
    """
    del municipalities, max_workers, use_gemini
    por_nome_uf: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []

    for item in files:
        nome = _municipio_do_nome(str(item.get("name") or ""))
        if not nome:
            continue
        chave = f"{nome}|{str(uf).upper()}"
        registro = {
            **item,
            "municipio_externo_normalizado": nome,
            "uf": str(uf).upper(),
            "metodo_identificacao": "NOME_EXTERNO",
            "confianca": 1.0,
        }
        if chave in por_nome_uf:
            duplicados.append({
                "chave": chave,
                "primeiro": por_nome_uf[chave].get("name"),
                "duplicado": item.get("name"),
            })
            continue
        por_nome_uf[chave] = registro

    return {
        "uf": str(uf).upper(),
        "ano": int(year),
        "fingerprint": _fingerprint(files),
        "por_nome_uf": por_nome_uf,
        "por_ibge": {},
        "nao_identificados": [],
        "duplicados": duplicados,
        "erros": [],
        "total": len(por_nome_uf),
        "metodo": "NOME_EXTERNO_SEM_LEITURA_INTERNA",
    }


def localizar_por_municipio(
    index: dict[str, Any],
    nome: str,
    uf: str,
) -> dict[str, Any] | None:
    chave = f"{normalizar_texto(nome)}|{str(uf).upper()}"
    return index.get("por_nome_uf", {}).get(chave)
