from __future__ import annotations

from importlib import import_module
from typing import Any

MODULE_BY_CODE = {
    "1.1": "modules.rreo_fields.codigo_1_1_iptu",
    "1.2": "modules.rreo_fields.codigo_1_2_itbi",
    "1.3": "modules.rreo_fields.codigo_1_3_iss",
    "1.4": "modules.rreo_fields.codigo_1_4_irrf",
    "2.1": "modules.rreo_fields.codigo_2_1_fpm",
    "2.1.1": "modules.rreo_fields.codigo_2_1_1_fpm_cf_b",
    "2.1.2": "modules.rreo_fields.codigo_2_1_2_fpm_cf_de",
    "2.2": "modules.rreo_fields.codigo_2_2_icms",
    "2.3": "modules.rreo_fields.codigo_2_3_ipi_exportacao",
    "2.4": "modules.rreo_fields.codigo_2_4_itr",
    "2.5": "modules.rreo_fields.codigo_2_5_ipva",
    "2.6": "modules.rreo_fields.codigo_2_6_iof_ouro",
    "6.1.1": "modules.rreo_fields.codigo_6_1_1_principal",
    "6.2": "modules.rreo_fields.codigo_6_2_vaaf",
    "6.2.1": "modules.rreo_fields.codigo_6_2_1_principal",
}


def extract_one(text: str, code: str) -> dict[str, Any]:
    module_name = MODULE_BY_CODE.get(str(code))
    if not module_name:
        raise ValueError(f"Codigo RREO sem modulo exclusivo: {code}")
    module = import_module(module_name)
    return module.extract(text)


def extract_many(text: str, codes: list[str]) -> tuple[dict[str, float | None], dict[str, dict[str, Any]]]:
    values: dict[str, float | None] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for code in codes:
        item = extract_one(text, code)
        values[code] = item.get("value")
        evidence[code] = item
    return values, evidence
