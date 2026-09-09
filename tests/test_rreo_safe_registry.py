from __future__ import annotations

import json
from pathlib import Path


def test_seed_registry_exists_and_has_history():
    p = Path(__file__).resolve().parents[1] / "data" / "rreo_safe_registry" / "REGISTRO_MESTRE_RREO_SAFE.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["global_totals"]["states_distinct"] >= 13
    assert data["global_totals"]["financial_divergences"] == 0
    assert "HIST_2025_SC_V137" in data["runs"]


def test_registry_records_locally_without_relaxing_alias(monkeypatch, tmp_path):
    import core.rreo_safe_registry as reg
    monkeypatch.setattr(reg, "LOCAL_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(reg, "_CACHE", None)
    monkeypatch.setattr(reg, "_DIRTY", 0)
    monkeypatch.setattr(reg, "_download_cloud", lambda: (None, None))
    monkeypatch.setattr(reg, "sync_registry", lambda **kwargs: {"ok": True, "skipped": True})

    reg.begin_state_run(
        job_id="TESTJOB", uf="SC", year=2025, bimestre=6, operation="TESTE",
        expected_names=["Itá", "Itajaí"], found_names=["Itá", "Itajaí"],
    )
    reg.record_municipality(
        job_id="TESTJOB", uf="SC", codigo_ibge="4208005", municipio="Itá",
        arquivo_pdf="ita.pdf",
        rreo_data={
            "identity_ok": True, "verification_ok": True, "identity_status": "OK",
            "municipio_interno": {"nome": "Itá"}, "verification_divergences": {},
            "secondary_values": {"1.1": 10.0}, "pdf_sha256": "abc",
        },
        values={"1.1": 10.0}, auto_sync=False,
    )
    snap = reg.registry_snapshot()
    run = snap["runs"]["TESTJOB:SC"]
    assert run["safe_validated"] == 1
    assert run["financial_comparisons"] == 1
    assert run["state_coverage_ok"] is True
