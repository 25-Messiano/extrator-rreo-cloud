from __future__ import annotations

import sqlite3
from pathlib import Path

from config.storage import GCS_BUCKET, GCS_OBJECTS
from integrations.google_storage import baixar_objeto
from modules.calendar_parser import data_g_de_linha_evento, parse_data_literal, parse_linha_calendario

BASE_DIR = Path(__file__).resolve().parents[1]
TEMP_DIR = BASE_DIR / "data" / "temp"
DATABASE_DIR = BASE_DIR / "data" / "database"
DB_PATH = DATABASE_DIR / "calendario.db"

ARQUIVOS = {
    "calendario": TEMP_DIR / "calendario_mestre.txt",
    "lua": TEMP_DIR / "fases_lua.txt",
    "estacoes": TEMP_DIR / "estacoes.txt",
    "pascoa": TEMP_DIR / "pascoa.txt",
    "festas": TEMP_DIR / "festas.txt",
}


def baixar_fontes():
    print("Baixando fontes oficiais do calendário...")
    for chave, caminho in ARQUIVOS.items():
        obrigatorio = chave == "calendario"
        ok = baixar_objeto(GCS_BUCKET, GCS_OBJECTS[chave], caminho, obrigatorio=obrigatorio)
        print(f"- {chave}: {'OK' if ok else 'não disponível (opcional)'}")


def criar_banco():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=NORMAL;
        PRAGMA temp_store=MEMORY;

        CREATE TABLE calendario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_g TEXT NOT NULL,
            g_mes INTEGER NOT NULL,
            g_ano_num INTEGER NOT NULL,
            dia_semana TEXT NOT NULL,
            data_m TEXT NOT NULL,
            m_mes INTEGER NOT NULL,
            m_ano_num INTEGER NOT NULL
        );

        CREATE TABLE eventos_g (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_g TEXT NOT NULL,
            tipo TEXT NOT NULL,
            codigo TEXT NOT NULL,
            nome TEXT NOT NULL,
            prioridade INTEGER NOT NULL DEFAULT 50,
            UNIQUE(data_g, tipo, codigo)
        );
        CREATE INDEX idx_eventos_g_data ON eventos_g(data_g);

        CREATE TABLE festas_m (
            id TEXT PRIMARY KEY,
            tipo TEXT NOT NULL,
            mes INTEGER,
            dia_inicio INTEGER,
            dia_fim INTEGER,
            nome TEXT NOT NULL,
            status TEXT NOT NULL,
            referencia TEXT,
            observacao TEXT
        );
        CREATE INDEX idx_festas_mes ON festas_m(mes, status);

        CREATE TABLE meta (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        """
    )
    return conn


def importar_calendario(conn):
    sql = """
        INSERT INTO calendario (
            data_g, g_mes, g_ano_num, dia_semana, data_m, m_mes, m_ano_num
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    lote, total = [], 0
    with ARQUIVOS["calendario"].open("r", encoding="utf-8-sig", errors="strict") as arq:
        for numero_linha, linha in enumerate(arq, start=1):
            r = parse_linha_calendario(linha)
            if not r:
                continue
            lote.append((
                r["data_g"], r["g_mes"], r["g_ano_num"], r["dia_semana"],
                r["data_m"], r["m_mes"], r["m_ano_num"],
            ))
            if len(lote) >= 100000:
                conn.executemany(sql, lote); conn.commit(); total += len(lote); lote.clear()
                print(f"  calendário: {total:,} registros")
    if lote:
        conn.executemany(sql, lote); conn.commit(); total += len(lote)
    return total


def _inserir_evento(conn, data_g, tipo, codigo, nome, prioridade):
    conn.execute(
        "INSERT OR IGNORE INTO eventos_g(data_g,tipo,codigo,nome,prioridade) VALUES(?,?,?,?,?)",
        (data_g, tipo, codigo, nome, prioridade),
    )


def importar_eventos_simples(conn, caminho: Path, tipo: str):
    if not caminho.exists():
        return 0
    total = 0
    with caminho.open("r", encoding="utf-8-sig", errors="replace") as arq:
        for raw in arq:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//") or ">" not in line:
                continue
            data_g = data_g_de_linha_evento(line)
            if not data_g:
                continue
            nome = line.split(">", 1)[1].split("|", 1)[0].strip()
            if not nome:
                continue
            codigo = nome.upper().replace(" ", "_")[:80]
            prio = 10 if tipo == "lua" else 20
            _inserir_evento(conn, data_g, tipo, codigo, nome, prio)
            total += 1
    conn.commit()
    return total


def importar_pascoa(conn):
    caminho = ARQUIVOS["pascoa"]
    if not caminho.exists():
        return 0
    total = 0
    with caminho.open("r", encoding="utf-8-sig", errors="replace") as arq:
        for raw in arq:
            line = raw.strip()
            if not line or line.startswith("#") or ">M." not in line:
                continue
            data_g = data_g_de_linha_evento(line)
            if not data_g:
                continue
            _inserir_evento(conn, data_g, "pascoa", "PASCOA_15_RUBEN", "Páscoa — 15 de Rúben", 30)
            total += 1
    conn.commit()
    return total


def importar_festas(conn):
    caminho = ARQUIVOS["festas"]
    if not caminho.exists():
        return 0
    total = 0
    sql = """
        INSERT OR REPLACE INTO festas_m(
            id,tipo,mes,dia_inicio,dia_fim,nome,status,referencia,observacao
        ) VALUES(?,?,?,?,?,?,?,?,?)
    """
    with caminho.open("r", encoding="utf-8-sig", errors="replace") as arq:
        for raw in arq:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 9 or parts[0] not in {"FIXA", "INTERVALO", "REGRA"}:
                continue
            tipo, ident, mes, ini, fim, nome, status, ref, obs = parts[:9]
            to_i = lambda v: int(v) if v.strip().isdigit() else None
            conn.execute(sql, (ident, tipo, to_i(mes), to_i(ini), to_i(fim), nome, status, ref, obs))
            total += 1
    conn.commit()
    return total


def criar_indices_calendario(conn):
    print("Criando índices de consulta...")
    conn.executescript(
        """
        CREATE INDEX idx_data_g ON calendario(data_g);
        CREATE INDEX idx_data_m ON calendario(data_m);
        CREATE INDEX idx_g_ym ON calendario(g_ano_num, g_mes, id);
        CREATE INDEX idx_m_ym ON calendario(m_ano_num, m_mes, id);
        """
    )
    conn.commit()


def gravar_meta(conn, total):
    row = conn.execute(
        "SELECT MIN(g_ano_num), MAX(g_ano_num), MIN(m_ano_num), MAX(m_ano_num) FROM calendario"
    ).fetchone()
    dados = {
        "total": str(total),
        "g_min": str(row[0]), "g_max": str(row[1]),
        "m_min": str(row[2]), "m_max": str(row[3]),
    }
    conn.executemany("INSERT OR REPLACE INTO meta(chave,valor) VALUES(?,?)", dados.items())
    conn.commit()


def importar():
    baixar_fontes()
    conn = criar_banco()
    total = importar_calendario(conn)
    criar_indices_calendario(conn)
    lua = importar_eventos_simples(conn, ARQUIVOS["lua"], "lua")
    est = importar_eventos_simples(conn, ARQUIVOS["estacoes"], "estacao")
    pas = importar_pascoa(conn)
    fes = importar_festas(conn)
    gravar_meta(conn, total)
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    print("IMPORTAÇÃO CONCLUÍDA")
    print(f"Calendário: {total:,} | Lua: {lua:,} | Estações: {est:,} | Páscoa: {pas:,} | Festas: {fes:,}")
    print(f"Banco: {DB_PATH}")


if __name__ == "__main__":
    importar()
