from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from core.json_pipeline import sha256_file
from modules.rreo import extract_text
from modules.rreo_fields.registry import extract_many

ALL_CODES = ["1.1","1.2","1.3","1.4","2.1","2.1.1","2.1.2","2.2","2.3","2.4","2.5","2.6","6.1.1","6.2","6.2.1"]


def extract_pdf_to_record(pdf_path: str | Path, *, ano: int, bimestre: int, codes: Iterable[str] = ALL_CODES) -> dict[str, Any]:
    path = Path(pdf_path)
    text = extract_text(path)
    selected = list(codes)
    values, evidence = extract_many(text, selected)
    return {
        "tipo": "EXTRACAO_RREO",
        "arquivo_pdf": path.name,
        "sha256_pdf": sha256_file(path),
        "ano": int(ano),
        "bimestre": int(bimestre),
        "coluna_autorizada": "RECEITAS_REALIZADAS_ATE_O_BIMESTRE_B",
        "coluna_previsao_a": "REGISTRADA_MAS_PROIBIDA_PARA_GRAVACAO",
        "valores": values,
        "evidencias": evidence,
    }
