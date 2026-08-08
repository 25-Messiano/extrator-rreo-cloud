from __future__ import annotations

import ast
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app.py", "config/storage.py", "modules/calendar_parser.py",
    "modules/database/connection.py", "modules/database/consultas.py", "modules/reports.py",
    "integrations/google_storage.py", "templates/index.html",
    "static/css/app.css", "static/js/app.js", "requirements.txt", "render.yaml",
]


def main():
    missing = [x for x in REQUIRED if not (BASE / x).exists()]
    if missing:
        raise SystemExit("Arquivos obrigatórios ausentes: " + ", ".join(missing))
    for path in BASE.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("Validação estrutural e sintática: OK")


if __name__ == "__main__":
    main()
