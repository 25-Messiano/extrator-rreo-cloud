from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / "app.py",
    ROOT / "pages" / "1_Painel.py",
    ROOT / "integrations" / "google_storage.py",
    ROOT / "integrations" / "gemini.py",
    ROOT / "modules" / "rreo.py",
    ROOT / "data" / "RREO-TCM+FNDE PLANILHA BASE.xlsx",
]

missing = [str(path) for path in REQUIRED if not path.exists()]
if missing:
    raise SystemExit("Arquivos ausentes:\n" + "\n".join(missing))

for name in ["sistema.json", "codigos_ativos.json", "planilha_base.json"]:
    json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))

workbook = load_workbook(
    ROOT / "data" / "RREO-TCM+FNDE PLANILHA BASE.xlsx",
    read_only=True,
)
print(f"OK: planilha com {len(workbook.sheetnames)} aba(s).")
workbook.close()
print("OK: estrutura do projeto validada.")
