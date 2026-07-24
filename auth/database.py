from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from core.database import Database
from .security import hash_password, hash_recovery_code, verify_password


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthDatabase:
    def __init__(self) -> None:
        self.db = Database()
        self.initialize()

    def initialize(self) -> None:
        with self.db.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL CHECK(perfil IN ('administrador','operador')),
                    ativo INTEGER NOT NULL DEFAULT 1,
                    trocar_senha INTEGER NOT NULL DEFAULT 0,
                    criado_em TEXT NOT NULL,
                    ultimo_login TEXT
                );
                CREATE TABLE IF NOT EXISTS recuperacao_senha (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER NOT NULL,
                    codigo_hash TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    expira_em TEXT NOT NULL,
                    usado_em TEXT,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                );
                CREATE INDEX IF NOT EXISTS idx_recuperacao_usuario
                    ON recuperacao_senha(usuario_id, id DESC);
                """
            )

    def has_admin(self) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM usuarios WHERE perfil='administrador' LIMIT 1"
            ).fetchone()
        return row is not None

    def create_user(
        self,
        nome: str,
        email: str,
        password: str,
        perfil: str = "operador",
        trocar_senha: bool = False,
    ) -> int:
        nome = nome.strip()
        email = email.strip().lower()
        if not nome:
            raise ValueError("Informe o nome do usuário.")
        if "@" not in email:
            raise ValueError("Informe um e-mail válido.")
        if perfil not in {"administrador", "operador"}:
            raise ValueError("Perfil inválido.")
        senha_hash = hash_password(password)
        try:
            with self.db.connect() as conn:
                cursor = conn.execute(
                    """INSERT INTO usuarios
                    (nome, email, senha_hash, perfil, ativo, trocar_senha, criado_em)
                    VALUES (?, ?, ?, ?, 1, ?, ?)""",
                    (nome, email, senha_hash, perfil, int(trocar_senha), _utc_now().isoformat()),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Já existe um usuário cadastrado com esse e-mail.") from exc

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE email=? COLLATE NOCASE AND ativo=1",
                (email.strip(),),
            ).fetchone()
            if row is None or not verify_password(password, row["senha_hash"]):
                return None
            now = _utc_now().isoformat()
            conn.execute("UPDATE usuarios SET ultimo_login=? WHERE id=?", (now, row["id"]))
            data = dict(row)
            data["ultimo_login"] = now
            return data

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE email=? COLLATE NOCASE", (email.strip(),)
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT id, nome, email, perfil, ativo, trocar_senha, criado_em, ultimo_login
                FROM usuarios ORDER BY nome COLLATE NOCASE"""
            ).fetchall()
        return [dict(row) for row in rows]

    def set_active(self, user_id: int, active: bool) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE usuarios SET ativo=? WHERE id=?", (int(active), user_id))

    def update_password(self, user_id: int, password: str, force_change: bool = False) -> None:
        senha_hash = hash_password(password)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE usuarios SET senha_hash=?, trocar_senha=? WHERE id=?",
                (senha_hash, int(force_change), user_id),
            )

    def create_recovery(self, user_id: int, code: str, minutes: int = 15) -> None:
        now = _utc_now()
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO recuperacao_senha
                (usuario_id, codigo_hash, criado_em, expira_em)
                VALUES (?, ?, ?, ?)""",
                (
                    user_id,
                    hash_recovery_code(code),
                    now.isoformat(),
                    (now + timedelta(minutes=minutes)).isoformat(),
                ),
            )

    def verify_recovery(self, email: str, code: str) -> dict[str, Any] | None:
        user = self.get_user_by_email(email)
        if not user:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT * FROM recuperacao_senha
                WHERE usuario_id=? AND usado_em IS NULL
                ORDER BY id DESC LIMIT 1""",
                (user["id"],),
            ).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row["expira_em"]) < _utc_now():
                return None
            if row["codigo_hash"] != hash_recovery_code(code.strip()):
                return None
            conn.execute(
                "UPDATE recuperacao_senha SET usado_em=? WHERE id=?",
                (_utc_now().isoformat(), row["id"]),
            )
        return user
