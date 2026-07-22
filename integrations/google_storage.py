from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.cloud import storage
from google.oauth2 import service_account


BUCKET_NAME = os.getenv(
    "GOOGLE_STORAGE_BUCKET",
    "maestro-rreo-arquivos",
).strip()

RREO_PREFIX = (
    "ARQUIVO_DE_ESTADOS_RREO/"
    "PDF - DOS MUNICIPIOS/"
)

RESULTADOS_PREFIX = (
    "ARQUIVO_DE_ESTADOS_RREO/"
    "PLANILHAS_PROCESSADAS/"
)


class StorageConfigurationError(RuntimeError):
    pass


def _credentials_info() -> dict[str, Any]:
    raw = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GCP_KEY") or "").strip()

    if not raw:
        raise StorageConfigurationError(
            "Credenciais não configuradas. Defina GOOGLE_SERVICE_ACCOUNT_JSON ou GCP_KEY."
        )

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        path = Path(raw)

        if path.exists():
            return json.loads(
                path.read_text(encoding="utf-8")
            )

        raise StorageConfigurationError(
            "GOOGLE_SERVICE_ACCOUNT_JSON inválida."
        )


def get_storage_client() -> storage.Client:
    info = _credentials_info()

    credentials = (
        service_account.Credentials
        .from_service_account_info(info)
    )

    project_id = (
        os.getenv(
            "GOOGLE_CLOUD_PROJECT",
            "",
        ).strip()
        or info.get("project_id")
        or "maestro-rreo"
    )

    return storage.Client(
        project=project_id,
        credentials=credentials,
    )


def list_states() -> list[str]:
    client = get_storage_client()

    iterator = client.list_blobs(
        BUCKET_NAME,
        prefix=RREO_PREFIX,
        delimiter="/",
    )

    list(iterator)

    states: list[str] = []

    for prefix in iterator.prefixes:
        state = prefix.rstrip("/").split("/")[-1]

        if state:
            states.append(state)

    return sorted(states)


def list_pdfs(
    state: str,
) -> list[dict[str, Any]]:
    client = get_storage_client()

    prefix = f"{RREO_PREFIX}{state}/"

    blobs = client.list_blobs(
        BUCKET_NAME,
        prefix=prefix,
    )

    files: list[dict[str, Any]] = []

    for blob in blobs:
        if blob.name.lower().endswith(".pdf"):
            files.append(
                {
                    "name": Path(blob.name).name,
                    "blob_name": blob.name,
                    "size": blob.size or 0,
                    "updated": blob.updated,
                }
            )

    return sorted(
        files,
        key=lambda item: item["name"],
    )


def download_file(
    blob_name: str,
    destination: str | Path,
) -> Path:
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)

    target = Path(destination)

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    blob.download_to_filename(
        str(target)
    )

    return target


def download_pdf(
    blob_name: str,
    destination: str | Path,
) -> Path:
    return download_file(
        blob_name=blob_name,
        destination=destination,
    )


def upload_file(
    local_path: str | Path,
    blob_name: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    source = Path(local_path)

    if not source.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {source}"
        )

    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)

    blob.upload_from_filename(
        str(source),
        content_type=content_type,
    )

    return {
        "name": source.name,
        "blob_name": blob.name,
        "size": source.stat().st_size,
    }


def upload_result(
    local_path: str | Path,
    state: str,
) -> dict[str, Any]:
    source = Path(local_path)

    blob_name = (
        f"{RESULTADOS_PREFIX}"
        f"{state}/"
        f"{source.name}"
    )

    return upload_file(
        local_path=source,
        blob_name=blob_name,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


def list_results(
    state: str | None = None,
) -> list[dict[str, Any]]:
    client = get_storage_client()

    prefix = RESULTADOS_PREFIX

    if state:
        prefix = f"{RESULTADOS_PREFIX}{state}/"

    blobs = client.list_blobs(
        BUCKET_NAME,
        prefix=prefix,
    )

    files: list[dict[str, Any]] = []

    for blob in blobs:
        if not blob.name.lower().endswith(".xlsx"):
            continue

        files.append(
            {
                "name": Path(blob.name).name,
                "blob_name": blob.name,
                "size": blob.size or 0,
                "updated": blob.updated,
            }
        )

    return sorted(
        files,
        key=lambda item: (
            item["updated"] is not None,
            item["updated"],
        ),
        reverse=True,
    )


def download_bytes(
    blob_name: str,
) -> bytes:
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)

    return blob.download_as_bytes()


def delete_file(
    blob_name: str,
) -> None:
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)

    blob.delete()


def health_check() -> dict[str, Any]:
    try:
        client = get_storage_client()
        bucket = client.get_bucket(BUCKET_NAME)

        return {
            "ok": True,
            "bucket": bucket.name,
        }

    except Exception as error:
        return {
            "ok": False,
            "message": str(error),
        }
