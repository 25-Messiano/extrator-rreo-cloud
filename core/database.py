from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "database.db"

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        raw = path or os.getenv("DATABASE_PATH") or DEFAULT_DB
        self.path = Path(raw)
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS arquivos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    cloud_path TEXT,
                    hash_sha256 TEXT UNIQUE,
                    tipo TEXT,
                    status TEXT NOT NULL DEFAULT 'novo',
                    criado_em TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arquivo_id INTEGER,
                    modulo TEXT NOT NULL,
                    iniciado_em TEXT NOT NULL,
                    finalizado_em TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY (arquivo_id) REFERENCES arquivos(id)
                );
                CREATE TABLE IF NOT EXISTS resultados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    processamento_id INTEGER NOT NULL,
                    codigo TEXT NOT NULL,
                    valor REAL,
                    fonte TEXT,
                    confianca REAL,
                    FOREIGN KEY (processamento_id) REFERENCES processamentos(id)
                );
                CREATE TABLE IF NOT EXISTS erros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    processamento_id INTEGER,
                    etapa TEXT NOT NULL,
                    mensagem TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    FOREIGN KEY (processamento_id) REFERENCES processamentos(id)
                );
            """)

    def set_config(self, chave: str, valor: Any) -> None:
        encoded = json.dumps(valor, ensure_ascii=False)
        with self.connect() as conn:
            conn.execute("""INSERT INTO configuracoes(chave, valor, atualizado_em)
                VALUES (?, ?, ?) ON CONFLICT(chave) DO UPDATE SET
                valor=excluded.valor, atualizado_em=excluded.atualizado_em""",
                (chave, encoded, _utc_now()))

    def get_config(self, chave: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (chave,)).fetchone()
        return json.loads(row["valor"]) if row else default

    def list_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT p.id, a.nome, a.cloud_path, p.modulo,
                p.iniciado_em, p.finalizado_em, p.status
                FROM processamentos p LEFT JOIN arquivos a ON a.id=p.arquivo_id
                ORDER BY p.id DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(row) for row in rows]
