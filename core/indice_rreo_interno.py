from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from integrations.google_storage import download_pdf
from modules.rreo import extract_text, identify_internal_municipality


def _process_one(
    file_info: dict[str, Any],
    municipalities: list[dict[str, Any]],
    uf: str,
    temp_root: Path,
) -> dict[str, Any]:
    """Lê um PDF RREO e identifica o município somente pelo conteúdo interno."""
    name = str(file_info.get("name") or "")
    blob_name = str(file_info.get("blob_name") or "")
    if not blob_name:
        return {
            "status": "ERRO",
            "name": name,
            "blob_name": blob_name,
            "erro": "blob_name ausente",
        }

    local_path = temp_root / name
    try:
        download_pdf(blob_name, local_path)
        text = extract_text(local_path)
        municipality, confidence, method, model, attempts = identify_internal_municipality(
            texto_pdf=text,
            municipios=municipalities,
            uf_esperada=uf,
            usar_gemini=True,
        )

        if not municipality:
            return {
                "status": "NAO_IDENTIFICADO",
                "name": name,
                "blob_name": blob_name,
                "size": int(file_info.get("size") or 0),
                "updated": str(file_info.get("updated") or ""),
                "metodo_identificacao": method,
                "confianca": float(confidence or 0.0),
                "modelo": model,
                "tentativas": int(attempts or 0),
            }

        return {
            "status": "OK",
            "name": name,
            "blob_name": blob_name,
            "size": int(file_info.get("size") or 0),
            "updated": str(file_info.get("updated") or ""),
            "codigo_ibge": str(municipality.get("codigo_ibge") or ""),
            "municipio_interno": str(municipality.get("nome") or ""),
            "uf": str(municipality.get("uf") or uf).upper(),
            "row": int(municipality.get("row") or 0),
            "metodo_identificacao": method,
            "confianca": float(confidence or 0.0),
            "modelo": model,
            "tentativas": int(attempts or 0),
        }
    except Exception as error:
        return {
            "status": "ERRO",
            "name": name,
            "blob_name": blob_name,
            "size": int(file_info.get("size") or 0),
            "updated": str(file_info.get("updated") or ""),
            "erro": f"{type(error).__name__}: {error}",
        }
    finally:
        local_path.unlink(missing_ok=True)


def build_rreo_internal_index(
    uf: str,
    year: int,
    files: list[dict[str, Any]],
    municipalities: list[dict[str, Any]],
    max_workers: int = 2,
) -> dict[str, Any]:
    """Cria índice RREO por código IBGE derivado de Município interno + UF.

    O código IBGE nunca é lido do PDF RREO. Ele vem exclusivamente do cadastro
    oficial recebido em ``municipalities`` após a identificação do município no
    conteúdo interno do documento.
    """
    safe_workers = max(1, min(int(max_workers or 1), 4))
    by_ibge: dict[str, dict[str, Any]] = {}
    unidentified: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix=f"rreo_index_{uf}_{year}_") as tmp:
        temp_root = Path(tmp)
        with ThreadPoolExecutor(max_workers=safe_workers) as executor:
            futures = {
                executor.submit(_process_one, item, municipalities, uf, temp_root): item
                for item in files
            }
            for future in as_completed(futures):
                result = future.result()
                status = result.get("status")
                if status == "OK":
                    code = str(result.get("codigo_ibge") or "")
                    if not code:
                        result["status"] = "NAO_IDENTIFICADO"
                        result["erro"] = "Município identificado sem código IBGE no cadastro oficial"
                        unidentified.append(result)
                        continue
                    previous = by_ibge.get(code)
                    if previous:
                        # Conserva o resultado de maior confiança e registra a duplicidade.
                        if float(result.get("confianca") or 0.0) > float(previous.get("confianca") or 0.0):
                            duplicates.append(previous)
                            by_ibge[code] = result
                        else:
                            duplicates.append(result)
                    else:
                        by_ibge[code] = result
                elif status == "NAO_IDENTIFICADO":
                    unidentified.append(result)
                else:
                    errors.append(result)

    return {
        "uf": str(uf).upper(),
        "year": int(year),
        "total_arquivos": len(files),
        "total_identificados": len(by_ibge),
        "total_nao_identificados": len(unidentified),
        "total_erros": len(errors),
        "total_duplicidades": len(duplicates),
        "por_ibge": by_ibge,
        "nao_identificados": unidentified,
        "erros": errors,
        "duplicidades": duplicates,
    }
