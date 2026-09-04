from __future__ import annotations

from math import isclose
from typing import Any


def compare_values(primary: dict[str, float | None], secondary: dict[str, float | None], *, abs_tol: float = 0.02) -> dict[str, Any]:
    keys = sorted(set(primary) | set(secondary))
    equal: list[str] = []
    divergent: dict[str, dict[str, float | None]] = {}
    missing: list[str] = []
    for key in keys:
        a = primary.get(key)
        b = secondary.get(key)
        if a is None or b is None:
            missing.append(key)
            continue
        if isclose(float(a), float(b), rel_tol=0.0, abs_tol=abs_tol):
            equal.append(key)
        else:
            divergent[key] = {"primary": a, "secondary": b}
    comparable = len(equal) + len(divergent)
    agreement = len(equal) / comparable if comparable else 0.0
    return {
        "ok": comparable > 0 and not divergent,
        "agreement": agreement,
        "equal": equal,
        "divergent": divergent,
        "missing": missing,
        "comparable": comparable,
    }


def validate_case(case_values: dict[str, float | None], specialist_values: dict[str, float | None] | None, verification_ok: bool) -> dict[str, Any]:
    if specialist_values is None:
        return {
            "ok": bool(verification_ok),
            "agreement": 1.0 if verification_ok else 0.0,
            "mode": "DETERMINISTIC_ONLY",
            "divergent": {},
        }
    result = compare_values(case_values, specialist_values)
    result["mode"] = "DUAL_AI_PLUS_DETERMINISTIC"
    result["deterministic_verification_ok"] = bool(verification_ok)
    result["ok"] = bool(result["ok"] and verification_ok)
    return result
