from __future__ import annotations

from pathlib import Path

from core.maestro_ia.gemini_specialist import GeminiSpecialist
from core.maestro_ia.memory import OperationalMemory
from core.maestro_ia.models import ExtractionCase, SpecialistResult, SupervisorDecision
from core.maestro_ia.openai_supervisor import OpenAISupervisor
from core.maestro_ia.orchestrator import MaestroOrchestrator
from core.maestro_ia.validators import compare_values


def _case(status="ERRO", verification_ok=False):
    return ExtractionCase(
        case_id="RREO-2025-BA-2900001-test",
        source="RREO", year=2025, uf="BA", ibge="2900001", municipality="Teste",
        operation="RREO", status=status, error="falha repetida" if status != "OK" else "",
        values={"1.1": 100.0, "1.2": 200.0}, verification_ok=verification_ok,
    )


def test_consenso_exato():
    result = compare_values({"1.1": 10.0}, {"1.1": 10.0})
    assert result["ok"] is True
    assert result["agreement"] == 1.0


def test_divergencia_nao_pode_validar():
    result = compare_values({"1.1": 10.0}, {"1.1": 11.0})
    assert result["ok"] is False
    assert "1.1" in result["divergent"]


def test_maestro_sombra_aprende_sem_alterar_producao(tmp_path: Path):
    memory = OperationalMemory(str(tmp_path / "memory.sqlite3"))
    specialist = GeminiSpecialist(lambda case: SpecialistResult(
        provider="GEMINI", status="OK", values={"1.1": 100.0, "1.2": 200.0},
        confidence=0.999, strategy="ESTRATEGIA_TESTE",
    ))
    supervisor = OpenAISupervisor(lambda case, spec, val: SupervisorDecision(
        decision="CANDIDATO_VALIDADO_EM_SOMBRA", confidence=0.999,
        reason="consenso", recommended_action="REGISTRAR_ESTRATEGIA",
        consensus=True, learn_strategy=True, patch_candidate=False,
    ))
    maestro = MaestroOrchestrator(memory=memory, specialist=specialist, supervisor=supervisor)
    case = _case()
    original = dict(case.values)
    outcome = maestro.handle(case)
    assert outcome.shadow_only is True
    assert case.values == original
    assert memory.summary()["strategies"] == 1


def test_patch_candidate_nunca_e_aplicado(tmp_path: Path, monkeypatch):
    import core.maestro_ia.orchestrator as orch
    created = []
    monkeypatch.setattr(orch, "create_patch_candidate", lambda *a, **k: created.append((a, k)) or tmp_path / "x.json")
    memory = OperationalMemory(str(tmp_path / "memory.sqlite3"))
    specialist = GeminiSpecialist(lambda case: SpecialistResult(provider="GEMINI", status="FAIL"))
    supervisor = OpenAISupervisor(lambda case, spec, val: SupervisorDecision(
        decision="PENDENTE_CONFERENCIA", confidence=0.2, reason="repetição",
        recommended_action="PROPOR_PATCH", patch_candidate=True, risk="HIGH",
    ))
    maestro = MaestroOrchestrator(memory=memory, specialist=specialist, supervisor=supervisor)
    out = maestro.handle(_case())
    assert created
    assert out.shadow_only is True
    assert out.supervisor.patch_candidate is True
