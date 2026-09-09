from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from core.json_pipeline import atomic_write_json, stable_hash
from modules.rreo import extract_text
from modules.rreo_json.identity import identify_municipality
from modules.rreo_json.extraction import extract_pdf_to_record
from modules.rreo_json.validation import validate_extraction
from modules.rreo_json.destination import build_destination_record


def prepare_json_pipeline(
    pdf_path: str | Path,
    workbook_path: str | Path,
    *,
    sheet_name: str,
    uf: str,
    ano: int,
    bimestre: int,
    output_dir: str | Path,
    similarity_min: float = 0.82,
    ambiguity_margin: float = 0.03,
) -> dict[str, Path]:
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    text = extract_text(pdf_path)

    wb = load_workbook(workbook_path, data_only=False, read_only=False)
    try:
        ws = wb[sheet_name]
        identity = identify_municipality(
            filename=pdf_path.name,
            internal_text=text,
            ws=ws,
            uf=uf,
            similarity_min=similarity_min,
            ambiguity_margin=ambiguity_margin,
        )
        extraction = extract_pdf_to_record(pdf_path, ano=ano, bimestre=bimestre)
        validation = validate_extraction(extraction, identity)
        destination = build_destination_record(ws, identity, validation, extraction["valores"]) if validation["status"] == "VALIDADO_SAFE_JSON" else {
            "tipo": "DESTINO_RREO", "status": "BLOQUEADO", "motivo": validation["status"], "destinos": {}
        }
    finally:
        wb.close()

    base = pdf_path.stem
    identity["fingerprint"] = stable_hash(identity)
    extraction["fingerprint"] = stable_hash({k: v for k, v in extraction.items() if k != "evidencias"})
    validation["fingerprint"] = stable_hash(validation)
    destination["fingerprint"] = stable_hash(destination)
    paths = {
        "identity": atomic_write_json(output_dir / f"{base}.identidade.json", identity),
        "extraction": atomic_write_json(output_dir / f"{base}.extracao.json", extraction),
        "validation": atomic_write_json(output_dir / f"{base}.validacao.json", validation),
        "destination": atomic_write_json(output_dir / f"{base}.destino.json", destination),
    }
    return paths
