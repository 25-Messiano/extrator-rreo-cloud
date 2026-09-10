from __future__ import annotations

import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from integrations.google_storage import BUCKET_NAME, get_storage_client
from modules.rreo_safe import validate_state_completeness

ENGINE_VERSION = "1.3.7.2"
REGISTRY_SCHEMA_VERSION = 1
REGISTRY_BLOB = os.getenv(
    "RREO_SAFE_REGISTRY_BLOB",
    "01_Arquivo_dos_Estados_RREO_e_FNDE/04_AUDITORIA_RREO_SAFE/REGISTRO_MESTRE_RREO_SAFE.json",
).strip().lstrip("/")
SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "rreo_safe_registry" / "REGISTRO_MESTRE_RREO_SAFE.json"
LOCAL_PATH = Path(os.getenv("RREO_SAFE_REGISTRY_LOCAL", "/tmp/REGISTRO_MESTRE_RREO_SAFE.json"))
SYNC_EVERY = max(1, int(os.getenv("RREO_SAFE_REGISTRY_SYNC_EVERY", "5")))

_LOCK = threading.RLock()
_CACHE: dict[str, Any] | None = None
_DIRTY = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _blank() -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_version": "1.0.0",
        "engine_integration_version": ENGINE_VERSION,
        "description": "Registro Mestre RREO SAFE — histórico + atualização automática.",
        "created_at": _now(),
        "updated_at": _now(),
        "cloud_blob": REGISTRY_BLOB,
        "sync_policy": {
            "local_atomic_each_municipality": True,
            "cloud_every_n_municipalities": SYNC_EVERY,
            "cloud_on_state_finish": True,
            "cloud_on_run_finish": True,
            "optimistic_generation_check": True,
        },
        "global_totals": {},
        "issue_catalog": [],
        "controlled_aliases": [],
        "alias_proposals": [],
        "runs": {},
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        return None
    return None


def _atomic_write(data: Mapping[str, Any]) -> None:
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL_PATH.with_suffix(LOCAL_PATH.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, LOCAL_PATH)


def _download_cloud() -> tuple[dict[str, Any] | None, int | None]:
    try:
        client = get_storage_client()
        blob = client.bucket(BUCKET_NAME).blob(REGISTRY_BLOB)
        if not blob.exists(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))):
            return None, None
        blob.reload(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")))
        raw = blob.download_as_bytes(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")))
        data = json.loads(raw.decode("utf-8"))
        return (data if isinstance(data, dict) else None), int(blob.generation or 0)
    except Exception:
        return None, None


def _merge(base: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Merge conservador. Nunca apaga histórico; run mais recente substitui a mesma chave."""
    out = copy.deepcopy(base or _blank())
    inc = dict(incoming or {})
    for key in ("issue_catalog", "controlled_aliases", "alias_proposals"):
        current = out.setdefault(key, [])
        seen = {json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) for x in current if isinstance(x, dict)}
        for item in inc.get(key, []) or []:
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if marker not in seen:
                current.append(copy.deepcopy(item)); seen.add(marker)
    out.setdefault("runs", {}).update(copy.deepcopy(inc.get("runs", {}) or {}))
    for key in ("schema_version", "registry_version", "description", "cloud_blob", "sync_policy"):
        if key in inc and inc[key] not in (None, ""):
            out[key] = copy.deepcopy(inc[key])
    out["engine_integration_version"] = ENGINE_VERSION
    out["updated_at"] = max(str(out.get("updated_at") or ""), str(inc.get("updated_at") or ""), _now())
    if not out.get("created_at"):
        out["created_at"] = inc.get("created_at") or _now()
    _recompute_totals(out)
    return out


def _recompute_totals(data: dict[str, Any]) -> None:
    runs = list((data.get("runs") or {}).values())
    data["global_totals"] = {
        "runs": len(runs),
        "states_distinct": len({str(r.get("uf") or "") for r in runs if r.get("uf")}),
        "processed_pdf_events": sum(int(r.get("processed_pdfs") or 0) for r in runs),
        "financial_comparisons": sum(int(r.get("financial_comparisons") or 0) for r in runs),
        "financial_divergences": sum(int(r.get("financial_divergences") or 0) for r in runs),
        "pending_review_events": sum(int(r.get("pending_review") or 0) for r in runs),
        "processing_errors": sum(int(r.get("processing_errors") or 0) for r in runs),
    }


def load_registry(*, prefer_cloud: bool = True) -> dict[str, Any]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        seed = _read_json(SEED_PATH) or _blank()
        local = _read_json(LOCAL_PATH)
        data = _merge(seed, local or {})
        if prefer_cloud:
            cloud, _ = _download_cloud()
            if cloud:
                data = _merge(data, cloud)
        _CACHE = data
        _atomic_write(_CACHE)
        return _CACHE


def _run_key(job_id: str, uf: str) -> str:
    return f"{str(job_id).strip()}:{str(uf).upper().strip()}"


def begin_state_run(
    *,
    job_id: str,
    uf: str,
    year: int | str,
    bimestre: int | str,
    operation: str,
    expected_names: Iterable[str],
    found_names: Iterable[str],
) -> str:
    global _DIRTY
    with _LOCK:
        data = load_registry()
        key = _run_key(job_id, uf)
        coverage = validate_state_completeness(expected_names, found_names)
        previous = (data.get("runs") or {}).get(key, {})
        run = {
            **previous,
            "run_id": key,
            "job_id": job_id,
            "source": "runtime_auto_registry",
            "engine_version": ENGINE_VERSION,
            "year": int(year),
            "bimestre": int(str(bimestre).upper().replace("B", "") or 6),
            "uf": str(uf).upper(),
            "operation": operation,
            "status": "EM_ANDAMENTO",
            "started_at": previous.get("started_at") or _now(),
            "updated_at": _now(),
            "expected_municipalities": int(coverage.get("expected") or 0),
            "pdfs_found": int(coverage.get("found") or 0),
            "missing_pdfs": list(coverage.get("missing") or []),
            "extra_pdfs": list(coverage.get("extra") or []),
            "state_coverage_ok": bool(coverage.get("ok")),
            "processed_pdfs": int(previous.get("processed_pdfs") or 0),
            "safe_validated": int(previous.get("safe_validated") or 0),
            "pending_review": int(previous.get("pending_review") or 0),
            "processing_errors": int(previous.get("processing_errors") or 0),
            "financial_scope": "runtime_full",
            "financial_comparisons": int(previous.get("financial_comparisons") or 0),
            "financial_divergences": int(previous.get("financial_divergences") or 0),
            "missing_fields_reader_a": int(previous.get("missing_fields_reader_a") or 0),
            "missing_fields_reader_b": int(previous.get("missing_fields_reader_b") or 0),
            "failure_cases": list(previous.get("failure_cases") or []),
            "municipalities": dict(previous.get("municipalities") or {}),
        }
        data.setdefault("runs", {})[key] = run
        data["updated_at"] = _now(); _recompute_totals(data); _atomic_write(data)
        _DIRTY += 1
        return key


def record_municipality(
    *,
    job_id: str,
    uf: str,
    codigo_ibge: str,
    municipio: str,
    arquivo_pdf: str,
    rreo_data: Mapping[str, Any] | None,
    values: Mapping[str, Any] | None,
    error: str = "",
    auto_sync: bool = True,
) -> None:
    global _DIRTY
    with _LOCK:
        data = load_registry()
        key = _run_key(job_id, uf)
        run = data.setdefault("runs", {}).setdefault(key, {
            "run_id": key, "job_id": job_id, "uf": str(uf).upper(), "engine_version": ENGINE_VERSION,
            "status": "EM_ANDAMENTO", "started_at": _now(), "municipalities": {}, "failure_cases": [],
        })
        d = dict(rreo_data or {})
        vals = dict(values or {})
        divergences = dict(d.get("verification_divergences") or {})
        structural_divergences = dict(d.get("structural_divergences") or {})
        semantic_divergences = dict(d.get("semantic_divergences") or {})
        secondary = dict(d.get("secondary_values") or {})
        missing_a = [c for c, v in vals.items() if v is None]
        missing_b = [c for c in vals if secondary and secondary.get(c) is None]
        identity_ok = bool(d.get("identity_ok"))
        verification_ok = bool(d.get("verification_ok"))
        post_write_ok = bool(d.get("post_write_ok")) if "post_write_ok" in d else None
        status = "VALIDADO_SAFE" if verification_ok and identity_ok and not error else "PENDENTE_CONFERENCIA"
        rec = {
            "codigo_ibge": str(codigo_ibge or ""),
            "municipio": municipio,
            "municipio_interno": (d.get("municipio_interno") or {}).get("nome") if isinstance(d.get("municipio_interno"), dict) else None,
            "arquivo_pdf": arquivo_pdf,
            "status": status,
            "identity_ok": identity_ok,
            "identity_status": d.get("identity_status"),
            "confianca_identidade": d.get("confianca_municipio"),
            "metodo_identidade": d.get("origem_municipio"),
            "verification_ok": verification_ok,
            "verification_method": d.get("verification_method"),
            "safe_confidence": d.get("safe_confidence"),
            "post_write_ok": post_write_ok,
            "pdf_sha256": d.get("pdf_sha256"),
            "result_fingerprint": d.get("result_fingerprint"),
            "values": vals,
            "secondary_values": secondary,
            "financial_divergences": divergences,
            "structural_divergences": structural_divergences,
            "semantic_divergences": semantic_divergences,
            "missing_reader_a": missing_a,
            "missing_reader_b": missing_b,
            "error": error or d.get("error") or "",
            "updated_at": _now(),
        }
        municipalities = run.setdefault("municipalities", {})
        municipalities[str(codigo_ibge or municipio)] = rec
        # Recalcula a UF a partir dos registros presentes para ser idempotente em retomadas.
        items = list(municipalities.values())
        run["processed_pdfs"] = sum(1 for x in items if x.get("arquivo_pdf"))
        run["safe_validated"] = sum(1 for x in items if x.get("status") == "VALIDADO_SAFE")
        run["pending_review"] = sum(1 for x in items if x.get("status") != "VALIDADO_SAFE")
        run["processing_errors"] = sum(1 for x in items if x.get("error"))
        run["financial_comparisons"] = sum(len(x.get("values") or {}) for x in items if x.get("arquivo_pdf"))
        run["financial_divergences"] = sum(
            len(x.get("financial_divergences") or {})
            + len(x.get("structural_divergences") or {})
            + len(x.get("semantic_divergences") or {})
            for x in items
        )
        run["missing_fields_reader_a"] = sum(len(x.get("missing_reader_a") or []) for x in items)
        run["missing_fields_reader_b"] = sum(len(x.get("missing_reader_b") or []) for x in items)
        run["failure_cases"] = [
            {
                "codigo_ibge": x.get("codigo_ibge"), "municipio": x.get("municipio"),
                "municipio_interno": x.get("municipio_interno"), "identity_status": x.get("identity_status"),
                "financial_divergences": x.get("financial_divergences"),
                "structural_divergences": x.get("structural_divergences"),
                "semantic_divergences": x.get("semantic_divergences"),
                "error": x.get("error"),
            }
            for x in items if x.get("status") != "VALIDADO_SAFE"
        ]
        run["updated_at"] = _now(); data["updated_at"] = _now(); _recompute_totals(data); _atomic_write(data)
        _DIRTY += 1
        do_sync = auto_sync and _DIRTY >= SYNC_EVERY
    if do_sync:
        sync_registry()


def propose_alias(*, uf: str, alias: str, official: str, reason: str, evidence: str = "") -> None:
    """Registra aprendizado como proposta. Nunca ativa alias automaticamente."""
    global _DIRTY
    proposal = {
        "uf": str(uf).upper(), "alias": alias, "official": official, "reason": reason,
        "evidence": evidence, "status": "PROPOSED_REVIEW_REQUIRED", "created_at": _now(),
    }
    with _LOCK:
        data = load_registry()
        existing = data.setdefault("alias_proposals", [])
        marker = (proposal["uf"], proposal["alias"].strip().upper(), proposal["official"].strip().upper())
        if not any((str(x.get("uf")).upper(), str(x.get("alias")).strip().upper(), str(x.get("official")).strip().upper()) == marker for x in existing):
            existing.append(proposal); data["updated_at"] = _now(); _atomic_write(data); _DIRTY += 1


def finish_state_run(*, job_id: str, uf: str, status: str = "CONCLUIDO", message: str = "") -> None:
    global _DIRTY
    with _LOCK:
        data = load_registry(); key = _run_key(job_id, uf); run = data.setdefault("runs", {}).setdefault(key, {})
        final_status = status
        if str(status).upper() == "CONCLUIDO" and run.get("state_coverage_ok") is False:
            final_status = "CONCLUIDO_INCOMPLETO"
        run["status"] = final_status; run["finished_at"] = _now(); run["updated_at"] = _now()
        if message: run["message"] = message
        data["updated_at"] = _now(); _recompute_totals(data); _atomic_write(data); _DIRTY += 1
    sync_registry(force=True)


def finish_job(*, job_id: str, status: str = "CONCLUIDO", message: str = "") -> None:
    with _LOCK:
        data = load_registry()
        for run in (data.get("runs") or {}).values():
            if str(run.get("job_id") or "") == str(job_id):
                run["job_status"] = status
                if message: run["job_message"] = message
                run["updated_at"] = _now()
        data["updated_at"] = _now(); _recompute_totals(data); _atomic_write(data)
    sync_registry(force=True)


def sync_registry(*, force: bool = False) -> dict[str, Any]:
    """Sincroniza com GCS usando geração otimista para evitar sobrescrita silenciosa."""
    global _CACHE, _DIRTY
    with _LOCK:
        if not force and _DIRTY <= 0:
            return {"ok": True, "skipped": True, "blob_name": REGISTRY_BLOB}
        local = copy.deepcopy(load_registry(prefer_cloud=False))
    last_error = None
    for _ in range(3):
        try:
            client = get_storage_client(); bucket = client.bucket(BUCKET_NAME); blob = bucket.blob(REGISTRY_BLOB)
            generation: int | None = None; cloud: dict[str, Any] | None = None
            if blob.exists(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))):
                blob.reload(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")))
                generation = int(blob.generation or 0)
                raw = blob.download_as_bytes(timeout=float(os.getenv("GCS_TIMEOUT_SECONDS", "120")))
                cloud = json.loads(raw.decode("utf-8"))
            merged = _merge(cloud or _blank(), local)
            payload = json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8")
            kwargs = {"content_type": "application/json; charset=utf-8", "timeout": float(os.getenv("GCS_TIMEOUT_SECONDS", "120"))}
            if generation is None:
                kwargs["if_generation_match"] = 0
            else:
                kwargs["if_generation_match"] = generation
            blob.upload_from_string(payload, **kwargs)
            with _LOCK:
                _CACHE = merged; _atomic_write(merged); _DIRTY = 0
            return {"ok": True, "blob_name": REGISTRY_BLOB, "size": len(payload)}
        except Exception as exc:
            last_error = exc
            # Em conflito de geração, o próximo ciclo recarrega e faz merge.
            continue
    return {"ok": False, "blob_name": REGISTRY_BLOB, "error": str(last_error or "sync failed")}


def registry_snapshot() -> dict[str, Any]:
    with _LOCK:
        return copy.deepcopy(load_registry())
