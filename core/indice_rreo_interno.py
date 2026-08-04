from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from core.indice_municipios import IndiceMunicipios, de_dicionarios
from core.validacao import normalizar_texto
from integrations.google_storage import download_pdf
from modules.rreo import extract_text, identify_internal_municipality


def _fingerprint(files: Iterable[dict[str, Any]]) -> str:
    import hashlib
    data = "|".join(sorted(f"{f.get('blob_name')}:{f.get('size')}:{f.get('updated')}" for f in files))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_rreo_internal_index(
    *,
    uf: str,
    year: int,
    files: list[dict[str, Any]],
    municipalities: list[dict[str, Any]],
    max_workers: int = 4,
    use_gemini: bool = True,
) -> dict[str, Any]:
    """Cria índice RREO pela chave primária (município interno normalizado, UF).

    `por_ibge` é fornecido apenas como visão derivada para compatibilidade; o
    código IBGE vem do cadastro oficial depois da identificação nome+UF.
    """
    municipal_index: IndiceMunicipios = de_dicionarios(municipalities)
    official = [item.as_dict() for item in municipal_index.do_estado(uf)]
    por_nome_uf: dict[str, dict[str, Any]] = {}
    por_ibge: dict[str, dict[str, Any]] = {}
    unidentified: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def worker(file_item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
        try:
            with tempfile.TemporaryDirectory(prefix="rreo_idx_") as tmp:
                local = Path(tmp) / str(file_item.get("name") or "arquivo.pdf")
                download_pdf(str(file_item.get("blob_name") or ""), local)
                text = extract_text(local)
            city, confidence, method, model, attempts = identify_internal_municipality(
                text, official, uf, usar_gemini=use_gemini
            )
            if not city:
                return file_item, None, "MUNICIPIO_INTERNO_NAO_IDENTIFICADO"
            return file_item, {
                **file_item,
                "municipio_interno": city["nome"],
                "uf": city["uf"],
                "codigo_ibge_derivado": city["codigo_ibge"],
                "chave_nome_uf": f"{normalizar_texto(city['nome'])}|{city['uf']}",
                "metodo_identificacao": method,
                "confianca": float(confidence),
                "modelo_gemini": model,
                "tentativas": attempts,
            }, None
        except Exception as exc:
            return file_item, None, f"{type(exc).__name__}: {exc}"

    workers = max(1, min(int(max_workers or 1), 4))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, item) for item in files]
        for future in as_completed(futures):
            original, identified, error = future.result()
            if not identified:
                row = {"arquivo": original.get("name", ""), "erro": error or "NÃO IDENTIFICADO"}
                (errors if error and ":" in error else unidentified).append(row)
                continue
            key = identified["chave_nome_uf"]
            if key in por_nome_uf:
                duplicates.append({"chave": key, "primeiro": por_nome_uf[key].get("name"), "duplicado": identified.get("name")})
                continue
            por_nome_uf[key] = identified
            por_ibge[identified["codigo_ibge_derivado"]] = identified

    return {
        "uf": str(uf).upper(), "ano": int(year), "fingerprint": _fingerprint(files),
        "por_nome_uf": por_nome_uf, "por_ibge": por_ibge,
        "nao_identificados": unidentified, "duplicados": duplicates,
        "erros": errors, "total": len(por_nome_uf),
    }


def localizar_por_municipio(index: dict[str, Any], nome: str, uf: str) -> dict[str, Any] | None:
    return index.get("por_nome_uf", {}).get(f"{normalizar_texto(nome)}|{str(uf).upper()}")
