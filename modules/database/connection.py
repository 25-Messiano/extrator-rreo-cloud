import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "database" / "calendario.db"


def conectar():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco de calendário não encontrado em {DB_PATH}. "
            "Execute o importador durante o build."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
