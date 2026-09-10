from __future__ import annotations

from typing import Any, Mapping

TOL = 0.02


def _close(a: float | None, b: float | None, tol: float = TOL) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def validate_extraction(extraction: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(extraction.get("valores") or {})
    evidence = dict(extraction.get("evidencias") or {})
    checks: dict[str, Any] = {}

    # Cada campo precisa ter identidade semantica e coluna B confirmadas.
    bad_fields: list[str] = []
    for code, item in evidence.items():
        ok = bool(item.get("semantic_ok")) and item.get("status") == "OK" and item.get("column_role") == "RECEITAS_REALIZADAS_B"
        checks[f"campo_{code}"] = "OK" if ok else "FALHA"
        if not ok:
            bad_fields.append(code)

    # Travas matematicas disponiveis nos 15 campos.
    if all(values.get(k) is not None for k in ("2.1", "2.1.1", "2.1.2")):
        fpm_sum = round(float(values["2.1.1"]) + float(values["2.1.2"]), 2)
        checks["2.1.1+2.1.2=2.1"] = {
            "ok": _close(fpm_sum, float(values["2.1"])),
            "soma": fpm_sum,
            "total": float(values["2.1"]),
        }
    else:
        checks["2.1.1+2.1.2=2.1"] = {"ok": False, "motivo": "CAMPO_AUSENTE"}

    # 6.2.1 deve ser <= 6.2; igualdade e comum, mas nao obrigatoria em todos os entes.
    if values.get("6.2") is not None and values.get("6.2.1") is not None:
        checks["6.2.1<=6.2"] = {
            "ok": float(values["6.2.1"]) <= float(values["6.2"]) + TOL,
            "principal": float(values["6.2.1"]),
            "total": float(values["6.2"]),
        }
    else:
        checks["6.2.1<=6.2"] = {"ok": False, "motivo": "CAMPO_AUSENTE"}

    identity_ok = bool(identity.get("identificado"))
    structural_ok = all(
        v == "OK" if isinstance(v, str) else bool(v.get("ok"))
        for v in checks.values()
    )
    status = "VALIDADO_SAFE_JSON" if identity_ok and structural_ok and not bad_fields else "PENDENTE_CONFERENCIA"
    return {
        "tipo": "VALIDACAO_RREO",
        "status": status,
        "identity_ok": identity_ok,
        "structural_ok": structural_ok,
        "campos_com_falha": bad_fields,
        "checks": checks,
        "ibge_confirmado_planilha": (identity.get("melhor_candidato") or {}).get("ibge"),
        "linha_confirmada_planilha": (identity.get("melhor_candidato") or {}).get("row"),
        "ente_confirmado_planilha": (identity.get("melhor_candidato") or {}).get("ente_planilha"),
    }
