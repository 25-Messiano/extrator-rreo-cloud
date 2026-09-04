from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass, asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from core.identificacao_arquivos import identificar_uf
from integrations.google_storage import (
    BUCKET_NAME,
    RREO_SOURCE_BUCKET,
    get_storage_client,
    list_appdowelever_rreo_state_folders,
    list_rreo_pdfs_by_uf,
)


DOWNLOAD_LOTE_PREFIX = (
    "01_Arquivo_dos_Estados_RREO_e_FNDE/04_DOWNLOADS_LOTE/RREO/"
)

ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class DownloadPackage:
    scope: str
    year: int
    bimestre: str
    uf: str | None
    filename: str
    bucket: str
    blob_name: str
    pdf_count: int
    source_bytes: int
    zip_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_bimestre(value: int | str | None) -> str:
    raw = str(value or 6).strip().upper()
    if raw.startswith("B"):
        raw = raw[1:]
    try:
        number = int(raw)
    except ValueError:
        number = 6
    return f"B{max(1, min(6, number))}"


def available_rreo_ufs(year: int | str = 2025) -> list[str]:
    ufs: set[str] = set()
    for folder in list_appdowelever_rreo_state_folders(year):
        uf = identificar_uf(folder)
        if uf:
            ufs.add(uf)
    return sorted(ufs)


def _collect_state_files(uf: str, year: int, bimestre: str) -> list[dict[str, Any]]:
    return list_rreo_pdfs_by_uf(uf, year, bimestre)


def inventory_state(uf: str, year: int | str = 2025, bimestre: int | str = 6) -> dict[str, Any]:
    year_i = int(year)
    bim = normalize_bimestre(bimestre)
    files = _collect_state_files(str(uf).upper(), year_i, bim)
    return {
        "scope": "ESTADO",
        "uf": str(uf).upper(),
        "year": year_i,
        "bimestre": bim,
        "pdf_count": len(files),
        "source_bytes": sum(int(item.get("size") or 0) for item in files),
    }


def inventory_brazil(year: int | str = 2025, bimestre: int | str = 6) -> dict[str, Any]:
    year_i = int(year)
    bim = normalize_bimestre(bimestre)
    states: dict[str, dict[str, int]] = {}
    total_files = 0
    total_bytes = 0
    for uf in available_rreo_ufs(year_i):
        files = _collect_state_files(uf, year_i, bim)
        if not files:
            continue
        count = len(files)
        size = sum(int(item.get("size") or 0) for item in files)
        states[uf] = {"pdf_count": count, "source_bytes": size}
        total_files += count
        total_bytes += size
    return {
        "scope": "BRASIL",
        "year": year_i,
        "bimestre": bim,
        "states": states,
        "state_count": len(states),
        "pdf_count": total_files,
        "source_bytes": total_bytes,
    }


def _zip_filename(scope: str, year: int, bimestre: str, uf: str | None) -> str:
    if scope == "ESTADO":
        return f"RREO_{uf}_{year}_{bimestre}.zip"
    return f"RREO_BRASIL_{year}_{bimestre}.zip"


def _output_blob_name(filename: str, year: int, bimestre: str) -> str:
    return f"{DOWNLOAD_LOTE_PREFIX}{year}/{bimestre}/{filename}"


def _iter_scope_files(
    scope: str,
    year: int,
    bimestre: str,
    uf: str | None,
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    if scope == "ESTADO":
        target = str(uf or "").upper().strip()
        if not target:
            raise ValueError("UF obrigatória para download por Estado.")
        files = _collect_state_files(target, year, bimestre)
        return [(target, item) for item in files], [target]

    states = available_rreo_ufs(year)
    collected: list[tuple[str, dict[str, Any]]] = []
    used_states: list[str] = []
    for state in states:
        files = _collect_state_files(state, year, bimestre)
        if not files:
            continue
        used_states.append(state)
        collected.extend((state, item) for item in files)
    return collected, used_states


def prepare_rreo_zip(
    scope: str,
    year: int | str = 2025,
    bimestre: int | str = 6,
    uf: str | None = None,
    progress: ProgressCallback | None = None,
) -> DownloadPackage:
    """Monta um ZIP RREO sem acumular PDFs em memória.

    Os PDFs são lidos um a um do bucket oficial APPDOWELEVER e escritos
    diretamente no ZIP temporário. O ZIP final é salvo no bucket de resultados.
    """
    scope_n = str(scope or "").upper().strip()
    if scope_n not in {"ESTADO", "BRASIL"}:
        raise ValueError("Escopo inválido. Use ESTADO ou BRASIL.")

    year_i = int(year)
    bim = normalize_bimestre(bimestre)
    target_uf = str(uf or "").upper().strip() or None
    files, states = _iter_scope_files(scope_n, year_i, bim, target_uf)
    if not files:
        where = f" para {target_uf}" if target_uf else ""
        raise FileNotFoundError(f"Nenhum PDF RREO encontrado{where} em {year_i}/{bim}.")

    filename = _zip_filename(scope_n, year_i, bim, target_uf)
    blob_name = _output_blob_name(filename, year_i, bim)
    total = len(files)
    source_bytes = sum(int(item.get("size") or 0) for _, item in files)

    client = get_storage_client()
    source_bucket = client.bucket(RREO_SOURCE_BUCKET)
    output_bucket = client.bucket(BUCKET_NAME)
    timeout = float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))

    with tempfile.TemporaryDirectory(prefix="rreo_download_lote_") as tmp:
        zip_path = Path(tmp) / filename
        # PDF já é comprimido; ZIP_STORED reduz CPU e deixa a geração muito mais rápida.
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for index, (state, item) in enumerate(files, start=1):
                blob_name_source = str(item["blob_name"])
                file_name = str(item.get("name") or Path(blob_name_source).name)
                arcname = file_name if scope_n == "ESTADO" else f"{state}/{file_name}"
                blob = source_bucket.blob(blob_name_source)
                with archive.open(arcname, mode="w", force_zip64=True) as entry:
                    blob.download_to_file(entry, timeout=timeout)
                if progress:
                    progress(index, total, f"{state} · {file_name}")

        output_blob = output_bucket.blob(blob_name)
        output_blob.upload_from_filename(
            str(zip_path),
            content_type="application/zip",
            timeout=timeout,
        )
        zip_bytes = zip_path.stat().st_size

    return DownloadPackage(
        scope=scope_n,
        year=year_i,
        bimestre=bim,
        uf=target_uf,
        filename=filename,
        bucket=BUCKET_NAME,
        blob_name=blob_name,
        pdf_count=total,
        source_bytes=source_bytes,
        zip_bytes=zip_bytes,
    )


def signed_download_url(blob_name: str, hours: int = 2) -> str:
    """Gera URL temporária do ZIP sem carregar o arquivo na RAM do Streamlit."""
    client = get_storage_client()
    blob = client.bucket(BUCKET_NAME).blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=max(1, min(int(hours), 24))),
        method="GET",
        response_disposition=f'attachment; filename="{Path(blob_name).name}"',
    )
