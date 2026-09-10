from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from openpyxl import load_workbook

from core.json_pipeline import load_json
from modules.rreo_json.destination import apply_destination_record


def main() -> None:
    p = argparse.ArgumentParser(description="Aplica JSON de destino ja validado em uma copia da planilha.")
    p.add_argument("planilha")
    p.add_argument("validacao_json")
    p.add_argument("destino_json")
    p.add_argument("saida")
    args = p.parse_args()
    src, dst = Path(args.planilha), Path(args.saida)
    shutil.copy2(src, dst)
    validation = load_json(args.validacao_json)
    destination = load_json(args.destino_json)
    wb = load_workbook(dst, data_only=False)
    try:
        ws = wb[destination["aba"]]
        written = apply_destination_record(ws, destination, validation)
        wb.save(dst)
    finally:
        wb.close()
    print(f"Células gravadas: {len(written)}")
    for cell in written:
        print(cell)


if __name__ == "__main__":
    main()
