from __future__ import annotations

import base64
import hashlib
import io
import os
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from integrations.google_storage import BUCKET_NAME, get_storage_client

RECOVERY_PREFIX = os.getenv("APP_RECOVERY_PREFIX", "99_BACKUP_RECUPERACAO_APP/").strip().strip("/") + "/"
WATCH_SECONDS = max(0, int(os.getenv("APP_RECOVERY_WATCH_SECONDS", "120")))

_ROOT = Path(__file__).resolve().parents[1]
_LOCK = threading.Lock()
_WATCHER_STARTED = False

# Arquivos efêmeros, credenciais e dados sensíveis de runtime NÃO entram no snapshot.
_EXCLUDED_DIR_NAMES = {
    ".git", ".pytest_cache", "__pycache__", ".venv", "venv", "node_modules",
    ".streamlit", ".idea", ".vscode",
}
_EXCLUDED_FILE_NAMES = {
    ".env", ".env.local", ".env.production", "secrets.toml",
    "auth.db", "users.db", "rreo_cloud.db", "rreo_cloud.sqlite", "database.sqlite",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".bak"}
_EXCLUDED_PREFIXES = ("RECUPERACAO_APP_",)


def _is_included(path: Path) -> bool:
    rel = path.relative_to(_ROOT)
    if any(part in _EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
        return False
    if path.name in _EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() in _EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith(_EXCLUDED_PREFIXES):
        return False
    return path.is_file()


def iter_project_files() -> list[Path]:
    return sorted((p for p in _ROOT.rglob("*") if _is_included(p)), key=lambda p: p.as_posix())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project_fingerprint(files: Iterable[Path] | None = None) -> tuple[str, list[tuple[str, int, str]]]:
    selected = list(files or iter_project_files())
    digest = hashlib.sha256()
    manifest: list[tuple[str, int, str]] = []
    for path in selected:
        rel = path.relative_to(_ROOT).as_posix()
        data = path.read_bytes()
        file_hash = _sha256_bytes(data)
        manifest.append((rel, len(data), file_hash))
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest(), manifest


def _snapshot_zip(files: Iterable[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, path.relative_to(_ROOT).as_posix())
    return buffer.getvalue()


def _recovery_script(zip_bytes: bytes, fingerprint: str, created_at: str) -> str:
    payload = base64.b64encode(zip_bytes).decode("ascii")
    return f'''#!/usr/bin/env python3
"""Recuperação autossuficiente do Extrator RREO Cloud.

Snapshot: {created_at}
Fingerprint SHA256 do projeto: {fingerprint}

Uso:
    python RECUPERACAO_APP.py
ou:
    python RECUPERACAO_APP.py /caminho/de/destino
"""
from __future__ import annotations
import base64
import io
import sys
import zipfile
from pathlib import Path

FINGERPRINT = {fingerprint!r}
CREATED_AT = {created_at!r}
SNAPSHOT_B64 = """{payload}"""


def restaurar(destino: str | Path = "extrator-rreo-cloud-recuperado") -> Path:
    destino = Path(destino).expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=True)
    dados = base64.b64decode(SNAPSHOT_B64.encode("ascii"))
    with zipfile.ZipFile(io.BytesIO(dados), "r") as zf:
        zf.extractall(destino)
    print(f"Projeto restaurado em: {{destino}}")
    print(f"Snapshot: {{CREATED_AT}}")
    print(f"Fingerprint: {{FINGERPRINT}}")
    return destino


if __name__ == "__main__":
    restaurar(sys.argv[1] if len(sys.argv) > 1 else "extrator-rreo-cloud-recuperado")
'''


def _text_report(fingerprint: str, manifest: list[tuple[str, int, str]], created_at: str) -> str:
    total_bytes = sum(size for _, size, _ in manifest)
    commit = os.getenv("RENDER_GIT_COMMIT", "não informado")
    service = os.getenv("RENDER_SERVICE_NAME", "não informado")
    lines = [
        "EXTRATOR RREO CLOUD - RELATÓRIO AUTOMÁTICO DE RECUPERAÇÃO",
        "=" * 72,
        f"Gerado em (UTC): {created_at}",
        f"Fingerprint SHA256 do projeto: {fingerprint}",
        f"Commit Render/Git: {commit}",
        f"Serviço Render: {service}",
        f"Bucket de destino: {BUCKET_NAME}",
        f"Prefixo de backup: {RECOVERY_PREFIX}",
        f"Quantidade de arquivos no snapshot: {len(manifest)}",
        f"Tamanho total original: {total_bytes} bytes",
        "",
        "FINALIDADE",
        "- Este arquivo registra exatamente quais arquivos compunham o app quando o backup foi criado.",
        "- O arquivo RECUPERACAO_APP.py armazenado junto deste TXT contém um snapshot compactado e autossuficiente do projeto.",
        "- Para restaurar, baixe RECUPERACAO_APP.py e execute: python RECUPERACAO_APP.py",
        "",
        "EXCLUSÕES DE SEGURANÇA/RUNTIME",
        "- Credenciais (.env, secrets.toml), caches, logs temporários e bancos locais de usuários/runtime não são incorporados.",
        "- Variáveis de ambiente e segredos devem ser restaurados separadamente no Render/Cloud.",
        "",
        "MANIFESTO DE ARQUIVOS",
        "Formato: caminho | tamanho_bytes | sha256",
        "-" * 72,
    ]
    lines.extend(f"{rel} | {size} | {sha}" for rel, size, sha in manifest)
    lines.append("")
    lines.append("FIM DO RELATÓRIO")
    return "\n".join(lines) + "\n"


def _blob_text(blob_name: str) -> str:
    client = get_storage_client()
    blob = client.bucket(BUCKET_NAME).blob(blob_name)
    if not blob.exists(timeout=30):
        return ""
    return blob.download_as_text(encoding="utf-8", timeout=30).strip()


def _upload_bytes(blob_name: str, data: bytes, content_type: str) -> None:
    client = get_storage_client()
    blob = client.bucket(BUCKET_NAME).blob(blob_name)
    blob.upload_from_string(data, content_type=content_type, timeout=120)


def create_and_upload_backup(force: bool = False) -> dict[str, str | bool | int]:
    with _LOCK:
        files = iter_project_files()
        fingerprint, manifest = project_fingerprint(files)
        marker_name = f"{RECOVERY_PREFIX}ULTIMO_HASH.txt"
        previous = ""
        if not force:
            try:
                previous = _blob_text(marker_name)
            except Exception:
                previous = ""
        if previous == fingerprint:
            return {"ok": True, "changed": False, "fingerprint": fingerprint, "files": len(manifest)}

        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        short = fingerprint[:12]
        zip_bytes = _snapshot_zip(files)
        txt = _text_report(fingerprint, manifest, created_at).encode("utf-8")
        py = _recovery_script(zip_bytes, fingerprint, created_at).encode("utf-8")

        history_prefix = f"{RECOVERY_PREFIX}HISTORICO/{stamp}_{short}/"
        targets = [
            (f"{history_prefix}RECUPERACAO_APP.txt", txt, "text/plain; charset=utf-8"),
            (f"{history_prefix}RECUPERACAO_APP.py", py, "text/x-python; charset=utf-8"),
            (f"{RECOVERY_PREFIX}ULTIMO/RECUPERACAO_APP.txt", txt, "text/plain; charset=utf-8"),
            (f"{RECOVERY_PREFIX}ULTIMO/RECUPERACAO_APP.py", py, "text/x-python; charset=utf-8"),
            (marker_name, (fingerprint + "\n").encode("ascii"), "text/plain"),
        ]
        for blob_name, data, content_type in targets:
            _upload_bytes(blob_name, data, content_type)
        return {
            "ok": True,
            "changed": True,
            "fingerprint": fingerprint,
            "files": len(manifest),
            "history_prefix": history_prefix,
        }


def _watch_loop() -> None:
    while True:
        try:
            create_and_upload_backup(force=False)
        except Exception:
            # Backup nunca pode derrubar o aplicativo.
            pass
        if WATCH_SECONDS <= 0:
            return
        time.sleep(WATCH_SECONDS)


def ensure_recovery_watcher_started() -> None:
    """Dispara backup imediato e passa a observar alterações locais do app.

    O Cloud mantém o último fingerprint. Reinícios sem mudança não geram cópias
    duplicadas; um novo deploy/alteração cria automaticamente um novo par TXT/PY.
    """
    global _WATCHER_STARTED
    with _LOCK:
        if _WATCHER_STARTED:
            return
        _WATCHER_STARTED = True
    thread = threading.Thread(target=_watch_loop, name="app-recovery-watcher", daemon=True)
    thread.start()
