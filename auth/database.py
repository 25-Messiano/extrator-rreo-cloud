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

    @property
    def _p(self) -> str:
        return "%s" if self.db.is_postgres else "?"

    def initialize(self) -> None:
        if self.db.is_postgres:
            statements = (
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id BIGSERIAL PRIMARY KEY,
                    nome TEXT NOT NULL,
                    email TEXT NOT NULL,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL CHECK(perfil IN ('administrador','operador')),
                    ativo INTEGER NOT NULL DEFAULT 1,
                    trocar_senha INTEGER NOT NULL DEFAULT 0,
                    criado_em TEXT NOT NULL,
                    ultimo_login TEXT
                )
                """,
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email_lower
                    ON usuarios (LOWER(email))
                """,
                """
                CREATE TABLE IF NOT EXISTS recuperacao_senha (
                    id BIGSERIAL PRIMARY KEY,
                    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
                    codigo_hash TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    expira_em TEXT NOT NULL,
                    usado_em TEXT
                )
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_recuperacao_usuario
                    ON recuperacao_senha(usuario_id, id DESC)
                """,
            )
            with self.db.connect() as conn:
                for statement in statements:
                    conn.execute(statement)
            return

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
                if self.db.is_postgres:
                    row = conn.execute(
                        """INSERT INTO usuarios
                        (nome, email, senha_hash, perfil, ativo, trocar_senha, criado_em)
                        VALUES (%s, %s, %s, %s, 1, %s, %s)
                        RETURNING id""",
                        (
                            nome,
                            email,
                            senha_hash,
                            perfil,
                            int(trocar_senha),
                            _utc_now().isoformat(),
                        ),
                    ).fetchone()
                    return int(row["id"])

                cursor = conn.execute(
                    """INSERT INTO usuarios
                    (nome, email, senha_hash, perfil, ativo, trocar_senha, criado_em)
                    VALUES (?, ?, ?, ?, 1, ?, ?)""",
                    (
                        nome,
                        email,
                        senha_hash,
                        perfil,
                        int(trocar_senha),
                        _utc_now().isoformat(),
                    ),
                )
                return int(cursor.lastrowid)
        except Exception as exc:
            if self._is_unique_violation(exc):
                raise ValueError("Já existe um usuário cadastrado com esse e-mail.") from exc
            raise

    @staticmethod
    def _is_unique_violation(exc: Exception) -> bool:
        if isinstance(exc, sqlite3.IntegrityError):
            return True
        try:
            from psycopg.errors import UniqueViolation

            return isinstance(exc, UniqueViolation)
        except ImportError:
            return False

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            if self.db.is_postgres:
                row = conn.execute(
                    "SELECT * FROM usuarios WHERE LOWER(email)=LOWER(%s) AND ativo=1",
                    (email.strip(),),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM usuarios WHERE email=? COLLATE NOCASE AND ativo=1",
                    (email.strip(),),
                ).fetchone()

            if row is None or not verify_password(password, row["senha_hash"]):
                return None

            now = _utc_now().isoformat()
            conn.execute(
                f"UPDATE usuarios SET ultimo_login={self._p} WHERE id={self._p}",
                (now, row["id"]),
            )
            data = dict(row)
            data["ultimo_login"] = now
            return data

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            if self.db.is_postgres:
                row = conn.execute(
                    "SELECT * FROM usuarios WHERE LOWER(email)=LOWER(%s)",
                    (email.strip(),),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM usuarios WHERE email=? COLLATE NOCASE",
                    (email.strip(),),
                ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        order_expression = "LOWER(nome)" if self.db.is_postgres else "nome COLLATE NOCASE"
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""SELECT id, nome, email, perfil, ativo, trocar_senha, criado_em, ultimo_login
                FROM usuarios ORDER BY {order_expression}"""
            ).fetchall()
        return [dict(row) for row in rows]

    def set_active(self, user_id: int, active: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE usuarios SET ativo={self._p} WHERE id={self._p}",
                (int(active), user_id),
            )

    def update_password(self, user_id: int, password: str, force_change: bool = False) -> None:
        senha_hash = hash_password(password)
        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE usuarios SET senha_hash={self._p}, trocar_senha={self._p} "
                f"WHERE id={self._p}",
                (senha_hash, int(force_change), user_id),
            )

    def create_recovery(self, user_id: int, code: str, minutes: int = 15) -> None:
        now = _utc_now()
        with self.db.connect() as conn:
            conn.execute(
                f"""INSERT INTO recuperacao_senha
                (usuario_id, codigo_hash, criado_em, expira_em)
                VALUES ({self._p}, {self._p}, {self._p}, {self._p})""",
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
                f"""SELECT * FROM recuperacao_senha
                WHERE usuario_id={self._p} AND usado_em IS NULL
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
                f"UPDATE recuperacao_senha SET usado_em={self._p} WHERE id={self._p}",
                (_utc_now().isoformat(), row["id"]),
            )
        return user
