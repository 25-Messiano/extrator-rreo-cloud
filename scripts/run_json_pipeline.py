from __future__ import annotations

import argparse
from pathlib import Path

from modules.rreo_json.pipeline import prepare_json_pipeline


def main() -> None:
    p = argparse.ArgumentParser(description="Gera JSONs de identidade, extracao, validacao e destino RREO.")
    p.add_argument("pdf")
    p.add_argument("planilha")
    p.add_argument("--aba", required=True)
    p.add_argument("--uf", required=True)
    p.add_argument("--ano", type=int, default=2025)
    p.add_argument("--bimestre", type=int, default=6)
    p.add_argument("--saida", default="saida_json")
    p.add_argument("--similaridade", type=float, default=0.82)
    p.add_argument("--margem-ambiguidade", type=float, default=0.03)
    args = p.parse_args()
    paths = prepare_json_pipeline(
        args.pdf, args.planilha, sheet_name=args.aba, uf=args.uf,
        ano=args.ano, bimestre=args.bimestre, output_dir=args.saida,
        similarity_min=args.similaridade, ambiguity_margin=args.margem_ambiguidade,
    )
    for name, path in paths.items():
        print(f"{name}: {Path(path).resolve()}")


if __name__ == "__main__":
    main()
