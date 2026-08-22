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
    """Banco compartilhado pelo sistema.

    No Render, usa PostgreSQL quando DATABASE_URL estiver definida.
    Em desenvolvimento local, mantém compatibilidade com SQLite.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.database_url = (os.getenv("DATABASE_URL") or "").strip()
        self.is_postgres = bool(self.database_url)

        raw = path or os.getenv("DATABASE_PATH") or DEFAULT_DB
        self.path = Path(raw)
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path
        if not self.is_postgres:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError(
                    "O driver PostgreSQL não está instalado. "
                    "Adicione psycopg[binary] ao requirements.txt."
                ) from exc

            connection = psycopg.connect(
                self.database_url,
                row_factory=dict_row,
                connect_timeout=15,
            )
        else:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        if self.is_postgres:
            statements = (
                """
                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS arquivos (
                    id BIGSERIAL PRIMARY KEY,
                    nome TEXT NOT NULL,
                    cloud_path TEXT,
                    hash_sha256 TEXT UNIQUE,
                    tipo TEXT,
                    status TEXT NOT NULL DEFAULT 'novo',
                    criado_em TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS processamentos (
                    id BIGSERIAL PRIMARY KEY,
                    arquivo_id BIGINT REFERENCES arquivos(id),
                    modulo TEXT NOT NULL,
                    iniciado_em TEXT NOT NULL,
                    finalizado_em TEXT,
                    status TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS resultados (
                    id BIGSERIAL PRIMARY KEY,
                    processamento_id BIGINT NOT NULL REFERENCES processamentos(id),
                    codigo TEXT NOT NULL,
                    valor DOUBLE PRECISION,
                    fonte TEXT,
                    confianca DOUBLE PRECISION
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS erros (
                    id BIGSERIAL PRIMARY KEY,
                    processamento_id BIGINT REFERENCES processamentos(id),
                    etapa TEXT NOT NULL,
                    mensagem TEXT NOT NULL,
                    criado_em TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS municipio_atividade (
                    ano INTEGER NOT NULL,
                    codigo_ibge TEXT NOT NULL,
                    uf TEXT NOT NULL,
                    municipio TEXT NOT NULL,
                    status_rreo TEXT NOT NULL DEFAULT 'PENDENTE',
                    status_fnde TEXT NOT NULL DEFAULT 'PENDENTE',
                    status_geral TEXT NOT NULL DEFAULT 'PENDENTE',
                    ultimo_erro TEXT,
                    tentativas INTEGER NOT NULL DEFAULT 0,
                    atualizado_em TEXT NOT NULL,
                    PRIMARY KEY (ano, codigo_ibge)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS execucoes_persistentes (
                    job_id TEXT PRIMARY KEY,
                    ano INTEGER NOT NULL,
                    escopo TEXT NOT NULL,
                    operacao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total INTEGER NOT NULL DEFAULT 0,
                    concluidos INTEGER NOT NULL DEFAULT 0,
                    erros INTEGER NOT NULL DEFAULT 0,
                    lote_atual INTEGER NOT NULL DEFAULT 0,
                    uf_atual TEXT,
                    municipio_atual TEXT,
                    master_blob TEXT,
                    mensagem TEXT,
                    iniciado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """,
            )
            with self.connect() as conn:
                for statement in statements:
                    conn.execute(statement)
            return

        with self.connect() as conn:
            conn.executescript(
                """
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
                CREATE TABLE IF NOT EXISTS municipio_atividade (
                    ano INTEGER NOT NULL,
                    codigo_ibge TEXT NOT NULL,
                    uf TEXT NOT NULL,
                    municipio TEXT NOT NULL,
                    status_rreo TEXT NOT NULL DEFAULT 'PENDENTE',
                    status_fnde TEXT NOT NULL DEFAULT 'PENDENTE',
                    status_geral TEXT NOT NULL DEFAULT 'PENDENTE',
                    ultimo_erro TEXT,
                    tentativas INTEGER NOT NULL DEFAULT 0,
                    atualizado_em TEXT NOT NULL,
                    PRIMARY KEY (ano, codigo_ibge)
                );
                CREATE TABLE IF NOT EXISTS execucoes_persistentes (
                    job_id TEXT PRIMARY KEY,
                    ano INTEGER NOT NULL,
                    escopo TEXT NOT NULL,
                    operacao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total INTEGER NOT NULL DEFAULT 0,
                    concluidos INTEGER NOT NULL DEFAULT 0,
                    erros INTEGER NOT NULL DEFAULT 0,
                    lote_atual INTEGER NOT NULL DEFAULT 0,
                    uf_atual TEXT,
                    municipio_atual TEXT,
                    master_blob TEXT,
                    mensagem TEXT,
                    iniciado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                );
                """
            )

    def set_config(self, chave: str, valor: Any) -> None:
        encoded = json.dumps(valor, ensure_ascii=False)
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"""INSERT INTO configuracoes(chave, valor, atualizado_em)
            VALUES ({placeholder}, {placeholder}, {placeholder})
            ON CONFLICT(chave) DO UPDATE SET
            valor=excluded.valor, atualizado_em=excluded.atualizado_em"""
        with self.connect() as conn:
            conn.execute(sql, (chave, encoded, _utc_now()))

    def get_config(self, chave: str, default: Any = None) -> Any:
        placeholder = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT valor FROM configuracoes WHERE chave={placeholder}",
                (chave,),
            ).fetchone()
        return json.loads(row["valor"]) if row else default

    def list_history(self, limit: int = 200) -> list[dict[str, Any]]:
        placeholder = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            rows = conn.execute(
                f"""SELECT p.id, a.nome, a.cloud_path, p.modulo,
                p.iniciado_em, p.finalizado_em, p.status
                FROM processamentos p LEFT JOIN arquivos a ON a.id=p.arquivo_id
                ORDER BY p.id DESC LIMIT {placeholder}""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_activity_map(self, ano: int, codigos: list[str] | None = None) -> dict[str, dict[str, Any]]:
        placeholder = "%s" if self.is_postgres else "?"
        params: list[Any] = [int(ano)]
        sql = f"SELECT * FROM municipio_atividade WHERE ano={placeholder}"
        if codigos:
            marks = ",".join([placeholder] * len(codigos))
            sql += f" AND codigo_ibge IN ({marks})"
            params.extend(str(c) for c in codigos)
        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return {str(row["codigo_ibge"]): dict(row) for row in rows}

    def upsert_municipio_activity(
        self, *, ano: int, codigo_ibge: str, uf: str, municipio: str,
        status_rreo: str, status_fnde: str, status_geral: str,
        ultimo_erro: str = "", incrementar_tentativa: bool = True,
    ) -> None:
        p = "%s" if self.is_postgres else "?"
        agora = _utc_now()
        sql = f"""INSERT INTO municipio_atividade(
            ano,codigo_ibge,uf,municipio,status_rreo,status_fnde,status_geral,
            ultimo_erro,tentativas,atualizado_em
        ) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
        ON CONFLICT(ano,codigo_ibge) DO UPDATE SET
            uf=excluded.uf, municipio=excluded.municipio,
            status_rreo=excluded.status_rreo, status_fnde=excluded.status_fnde,
            status_geral=excluded.status_geral, ultimo_erro=excluded.ultimo_erro,
            tentativas=municipio_atividade.tentativas + {1 if incrementar_tentativa else 0},
            atualizado_em=excluded.atualizado_em"""
        with self.connect() as conn:
            conn.execute(sql, (int(ano), str(codigo_ibge), uf, municipio, status_rreo,
                               status_fnde, status_geral, ultimo_erro,
                               1 if incrementar_tentativa else 0, agora))

    def state_activity_summary(self, ano: int, uf: str) -> dict[str, int]:
        p = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT status_geral, COUNT(*) AS qtd FROM municipio_atividade WHERE ano={p} AND uf={p} GROUP BY status_geral",
                (int(ano), uf.upper()),
            ).fetchall()
        out = {"PROCESSADO": 0, "ERRO": 0, "PARCIAL": 0, "PENDENTE": 0}
        for row in rows:
            out[str(row["status_geral"])] = int(row["qtd"] or 0)
        return out

    def upsert_job(self, *, job_id: str, ano: int, escopo: str, operacao: str, status: str,
                   total: int = 0, concluidos: int = 0, erros: int = 0, lote_atual: int = 0,
                   uf_atual: str = "", municipio_atual: str = "", master_blob: str = "", mensagem: str = "") -> None:
        p = "%s" if self.is_postgres else "?"
        agora = _utc_now()
        sql = f"""INSERT INTO execucoes_persistentes(
            job_id,ano,escopo,operacao,status,total,concluidos,erros,lote_atual,uf_atual,municipio_atual,master_blob,mensagem,iniciado_em,atualizado_em
        ) VALUES ({','.join([p]*15)})
        ON CONFLICT(job_id) DO UPDATE SET
            status=excluded.status,total=excluded.total,concluidos=excluded.concluidos,erros=excluded.erros,
            lote_atual=excluded.lote_atual,uf_atual=excluded.uf_atual,municipio_atual=excluded.municipio_atual,
            master_blob=excluded.master_blob,mensagem=excluded.mensagem,atualizado_em=excluded.atualizado_em"""
        vals=(job_id,int(ano),escopo,operacao,status,int(total),int(concluidos),int(erros),int(lote_atual),
              uf_atual,municipio_atual,master_blob,mensagem,agora,agora)
        with self.connect() as conn:
            conn.execute(sql, vals)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        p = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            row = conn.execute(f"SELECT * FROM execucoes_persistentes WHERE job_id={p}", (job_id,)).fetchone()
        return dict(row) if row else None

    def latest_job(self, ano: int | None = None) -> dict[str, Any] | None:
        p = "%s" if self.is_postgres else "?"
        sql = "SELECT * FROM execucoes_persistentes"
        params: tuple[Any, ...] = ()
        if ano is not None:
            sql += f" WHERE ano={p}"
            params = (int(ano),)
        sql += " ORDER BY atualizado_em DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def list_activity(self, ano: int, limit: int = 10000) -> list[dict[str, Any]]:
        p = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM municipio_atividade WHERE ano={p} ORDER BY uf, municipio LIMIT {p}",
                (int(ano), int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_jobs(self, limit: int = 200) -> list[dict[str, Any]]:
        p = "%s" if self.is_postgres else "?"
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM execucoes_persistentes ORDER BY atualizado_em DESC LIMIT {p}",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]
