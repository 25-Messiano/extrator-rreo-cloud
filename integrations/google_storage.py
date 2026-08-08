from __future__ import annotations

import json
import os
from pathlib import Path


def criar_cliente_storage():
    """Cria cliente GCS sem expor credenciais na interface ou nos logs."""
    from google.cloud import storage
    from google.oauth2 import service_account

    raw = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GCP_KEY") or "").strip()
    if raw:
        info = json.loads(raw)
        cred = service_account.Credentials.from_service_account_info(info)
        return storage.Client(project=info.get("project_id"), credentials=cred)
    return storage.Client()


def baixar_objeto(bucket_nome: str, objeto: str, destino: Path, *, obrigatorio: bool = True) -> bool:
    destino.parent.mkdir(parents=True, exist_ok=True)
    cliente = criar_cliente_storage()
    bucket = cliente.bucket(bucket_nome)
    blob = bucket.blob(objeto)
    if not blob.exists(cliente):
        if obrigatorio:
            raise FileNotFoundError("Fonte oficial obrigatória não encontrada no armazenamento.")
        return False
    blob.download_to_filename(str(destino))
    return True
