from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from core.identificacao_arquivos import (
    UF_IBGE_PREFIX,
    codigo_ibge_no_texto,
    identificar_uf,
    uf_do_codigo_ibge,
)


BUCKET_NAME = os.getenv(
    "GOOGLE_STORAGE_BUCKET",
    "maestro-rreo-arquivos",
).strip()

BASE_ARQUIVOS_PREFIX = "01_Arquivo_dos_Estados_RREO_e_FNDE/"
RREO_ROOT_PREFIX = f"{BASE_ARQUIVOS_PREFIX}01_RREO/"
FNDE_ROOT_PREFIX = f"{BASE_ARQUIVOS_PREFIX}02_FNDE/"

# Compatibilidade temporária com a estrutura antiga.
LEGACY_RREO_PREFIX = "ARQUIVO_DE_ESTADOS_RREO/PDF - DOS MUNICIPIOS/"
LEGACY_FNDE_ROOT_PREFIX = "ARQUIVO_DE_ESTADOS_RREO/"

RESULTADOS_PREFIX = f"{BASE_ARQUIVOS_PREFIX}03_PLANILHAS_PROCESSADAS/"


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


def get_storage_client():
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError as exc:
        raise StorageConfigurationError("Bibliotecas google-cloud-storage/google-auth não instaladas.") from exc
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


def _list_subfolders(prefix: str) -> list[str]:
    client = get_storage_client()
    iterator = client.list_blobs(
        BUCKET_NAME,
        prefix=prefix,
        delimiter="/",
        timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")),
    )
    list(iterator)
    return sorted(
        item.rstrip("/").split("/")[-1]
        for item in iterator.prefixes
        if item.rstrip("/").split("/")[-1]
    )


def _uf_from_state_folder(folder: str) -> str:
    """Extrai a UF de nomes de pasta tolerando prefixos, sufixos e ano.

    Exemplos aceitos: MG, 31_Minas Gerais_MG, MG_2025,
    FNDE_Minas_Gerais_MG_2025.
    """
    return identificar_uf(str(folder or ""))


def _year_prefix(module: str, year: int | str) -> str:
    year_text = str(year)
    if module.upper() == "FNDE":
        return f"{FNDE_ROOT_PREFIX}FNDE_{year_text}/"
    return f"{RREO_ROOT_PREFIX}RREO_{year_text}/"


def list_rreo_state_folders(year: int | str = 2025) -> list[str]:
    folders = _list_subfolders(_year_prefix("RREO", year))
    if folders:
        return folders
    return _list_subfolders(LEGACY_RREO_PREFIX)


def list_fnde_state_folders(year: int | str = 2025) -> list[str]:
    folders = _list_subfolders(_year_prefix("FNDE", year))
    if folders:
        return folders

    # Compatibilidade com o padrão antigo '<Estado> FNDE - <UF>_<ANO>'.
    import re
    pattern = re.compile(r"^.+?\s+FNDE\s*-\s*[A-Z]{2}_\d{4}$", re.IGNORECASE)
    return [
        folder
        for folder in _list_subfolders(LEGACY_FNDE_ROOT_PREFIX)
        if pattern.match(folder)
    ]


def _find_state_folder(folders: list[str], uf: str) -> str | None:
    target = str(uf or "").upper().strip()
    for folder in folders:
        if _uf_from_state_folder(folder) == target:
            return folder
    return None


def find_rreo_folder(uf: str, year: int | str = 2025) -> str | None:
    return _find_state_folder(list_rreo_state_folders(year), uf)


def find_fnde_folder(uf: str, year: int | str | None = 2025) -> str | None:
    target_year = year or 2025
    folder = _find_state_folder(list_fnde_state_folders(target_year), uf)
    if folder:
        return folder

    # Compatibilidade com a estrutura antiga.
    import re
    target = str(uf or "").upper()
    year_text = str(target_year)
    for legacy_folder in list_fnde_state_folders(target_year):
        match = re.search(r"-\s*([A-Z]{2})_(\d{4})$", legacy_folder, re.IGNORECASE)
        if match and match.group(1).upper() == target and match.group(2) == year_text:
            return legacy_folder
    return None


def list_states(
    year: int | str = 2025,
    include_rreo: bool = True,
    include_fnde: bool = False,
) -> list[str]:
    """Lista uma pasta representativa por UF para a operação selecionada."""
    by_uf: dict[str, str] = {}

    if include_rreo:
        for folder in list_rreo_state_folders(year):
            uf = _uf_from_state_folder(folder)
            if uf:
                by_uf[uf] = folder

    if include_fnde:
        for folder in list_fnde_state_folders(year):
            uf = _uf_from_state_folder(folder)
            if not uf:
                # Estrutura antiga.
                import re
                match = re.search(r"-\s*([A-Z]{2})_\d{4}$", folder, re.IGNORECASE)
                uf = match.group(1).upper() if match else ""
            if uf and uf not in by_uf:
                by_uf[uf] = folder

    return [by_uf[uf] for uf in sorted(by_uf)]


def _list_pdfs_under_prefix(prefix: str) -> list[dict[str, Any]]:
    client = get_storage_client()
    files: list[dict[str, Any]] = []
    for blob in client.list_blobs(
        BUCKET_NAME, prefix=prefix,
        timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")),
    ):
        if blob.name.lower().endswith(".pdf"):
            files.append(
                {
                    "name": Path(blob.name).name,
                    "blob_name": blob.name,
                    "size": blob.size or 0,
                    "updated": blob.updated,
                }
            )
    return sorted(files, key=lambda item: item["name"])



_YEAR_LISTING_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
_YEAR_LISTING_CACHE_LOCK = threading.Lock()


def clear_storage_listing_cache() -> None:
    """Limpa o snapshot em memoria usado pelos fallbacks recursivos."""
    with _YEAR_LISTING_CACHE_LOCK:
        _YEAR_LISTING_CACHE.clear()


def _list_year_pdfs_cached(module: str, year: int | str) -> list[dict[str, Any]]:
    key = (str(module).upper(), str(year))
    ttl = max(5.0, float(os.getenv("GCS_YEAR_LIST_CACHE_SECONDS", "300")))
    now = time.monotonic()
    with _YEAR_LISTING_CACHE_LOCK:
        cached = _YEAR_LISTING_CACHE.get(key)
        if cached and (now - cached[0]) < ttl:
            return list(cached[1])
    files = _list_pdfs_under_prefix(_year_prefix(key[0], key[1]))
    with _YEAR_LISTING_CACHE_LOCK:
        _YEAR_LISTING_CACHE[key] = (now, list(files))
    return files

def _arquivo_pertence_uf(item: dict[str, Any], uf: str) -> bool:
    """Confere UF usando IBGE, filename e caminho completo do blob."""
    target = str(uf or "").upper().strip()
    if not target:
        return False
    nome = str(item.get("name") or "")
    blob_name = str(item.get("blob_name") or "")
    codigo = codigo_ibge_no_texto(nome) or codigo_ibge_no_texto(blob_name)
    if codigo and uf_do_codigo_ibge(codigo) == target:
        return True
    return identificar_uf(nome) == target or identificar_uf(blob_name) == target


def list_rreo_pdfs_by_uf(uf: str, year: int | str = 2025) -> list[dict[str, Any]]:
    """Lista RREO por UF sem depender rigidamente do nome da pasta.

    Primeiro usa a pasta estadual resolvida. Se a pasta nao existir ou estiver
    vazia, faz uma varredura recursiva somente em RREO_<ano> e filtra a UF pelo
    caminho/filename. A estrutura legada fica como ultimo recurso.
    """
    target = str(uf or "").upper().strip()
    folder = find_rreo_folder(target, year)
    if folder:
        prefix = f"{_year_prefix('RREO', year)}{folder}/"
        files = _list_pdfs_under_prefix(prefix)
        if files:
            return files

    all_files = _list_year_pdfs_cached("RREO", year)
    matched = [item for item in all_files if _arquivo_pertence_uf(item, target)]
    if matched:
        return matched

    legacy_files = _list_pdfs_under_prefix(LEGACY_RREO_PREFIX)
    return [item for item in legacy_files if _arquivo_pertence_uf(item, target)]


def list_pdfs(state: str, year: int | str = 2025) -> list[dict[str, Any]]:
    """Compatibilidade: lista RREO aceitando UF ou nome de pasta."""
    uf = _uf_from_state_folder(state) or identificar_uf(state)
    if uf:
        return list_rreo_pdfs_by_uf(uf, year)

    # Quando o chamador fornece uma pasta antiga que nao permite descobrir UF,
    # ainda tenta o prefixo legado diretamente.
    return _list_pdfs_under_prefix(f"{LEGACY_RREO_PREFIX}{state}/")


def list_fnde_pdfs(folder: str, year: int | str = 2025) -> list[dict[str, Any]]:
    uf = _uf_from_state_folder(folder)
    resolved = find_fnde_folder(uf, year) if uf else folder
    if resolved and _uf_from_state_folder(resolved):
        prefix = f"{_year_prefix('FNDE', year)}{resolved}/"
        files = _list_pdfs_under_prefix(prefix)
        if files:
            return files

    return _list_pdfs_under_prefix(f"{LEGACY_FNDE_ROOT_PREFIX}{folder}/")

def _arquivo_pertence_uf_fnde(item: dict[str, Any], uf: str) -> bool:
    return _arquivo_pertence_uf(item, uf)


def list_fnde_pdfs_by_uf(uf: str, year: int | str = 2025) -> list[dict[str, Any]]:
    """Lista FNDE de uma UF com fallback defensivo no ano inteiro.

    1. tenta a pasta estadual resolvida normalmente;
    2. se a pasta nao existir ou vier vazia, percorre FNDE_<ano>/ e
       seleciona somente arquivos cujo IBGE pertence a UF ou cujo nome
       declara explicitamente a UF.

    O fallback resolve arquivos novos que estejam em uma pasta com nome
    diferente do padrao sem associar municipios de outro estado.
    """
    target = str(uf or "").upper().strip()
    folder = find_fnde_folder(target, year)
    if folder:
        files = list_fnde_pdfs(folder, year)
        if files:
            return files

    # Busca recursiva sob o ano. O filtro por prefixo IBGE/UF evita mistura.
    all_files = _list_year_pdfs_cached("FNDE", year)
    matched = [item for item in all_files if _arquivo_pertence_uf_fnde(item, target)]
    if matched:
        return matched

    # Estrutura legada como ultimo recurso.
    legacy_files = _list_pdfs_under_prefix(LEGACY_FNDE_ROOT_PREFIX)
    return [item for item in legacy_files if _arquivo_pertence_uf_fnde(item, target)]


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
        str(target),
        timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")),
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
        timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")),
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



def describe_state_files(uf: str, year: int | str = 2025) -> dict[str, Any]:
    """Lista RREO e FNDE apenas uma vez para uma UF/ano."""
    target = str(uf or "").upper().strip()
    rreo_folder = find_rreo_folder(target, year)
    fnde_folder = find_fnde_folder(target, year)
    return {
        "uf": target,
        "year": int(year),
        "rreo_folder": rreo_folder,
        "fnde_folder": fnde_folder,
        "rreo": list_rreo_pdfs_by_uf(target, year),
        "fnde": list_fnde_pdfs_by_uf(target, year),
    }


MASTER_PREFIX = f"{RESULTADOS_PREFIX}MASTER/"
MASTER_BACKUP_PREFIX = f"{RESULTADOS_PREFIX}BACKUPS_MASTER/"
LOGS_PREFIX = f"{RESULTADOS_PREFIX}LOGS/"


def master_blob_name(year: int | str) -> str:
    return f"{MASTER_PREFIX}RREO_FNDE_BRASIL_MASTER_{int(year)}.xlsx"


def master_exists(year: int | str) -> bool:
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    return bool(bucket.blob(master_blob_name(year)).exists(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))))


def download_master(year: int | str, destination: str | Path) -> Path | None:
    blob_name = master_blob_name(year)
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    if not blob.exists(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))):
        return None
    return download_file(blob_name, destination)


def upload_master(local_path: str | Path, year: int | str) -> dict[str, Any]:
    return upload_file(
        local_path, master_blob_name(year),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def backup_master(local_path: str | Path, year: int | str, label: str) -> dict[str, Any]:
    source = Path(local_path)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label or "backup"))
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    blob_name = f"{MASTER_BACKUP_PREFIX}{int(year)}/RREO_FNDE_BRASIL_MASTER_{int(year)}_{stamp}_{safe}.xlsx"
    return upload_file(source, blob_name, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def upload_activity_log(local_path: str | Path, year: int | str) -> dict[str, Any]:
    source = Path(local_path)
    return upload_file(
        source, f"{LOGS_PREFIX}LOG_ATIVIDADE_{int(year)}.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
