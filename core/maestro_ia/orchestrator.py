from __future__ import annotations

from core.maestro_ia.config import CONFIG
from core.maestro_ia.gemini_specialist import GeminiSpecialist
from core.maestro_ia.memory import OperationalMemory
from core.maestro_ia.models import ExtractionCase, MaestroOutcome
from core.maestro_ia.openai_supervisor import OpenAISupervisor
from core.maestro_ia.patches import create_patch_candidate
from core.maestro_ia.validators import validate_case


class MaestroOrchestrator:
    """Orquestrador em modo sombra: observa, aprende e propõe; nunca grava resultado oficial."""

    def __init__(self, *, memory: OperationalMemory | None = None,
                 specialist: GeminiSpecialist | None = None,
                 supervisor: OpenAISupervisor | None = None):
        self.memory = memory or OperationalMemory(CONFIG.memory_path)
        self.specialist = specialist or GeminiSpecialist()
        self.supervisor = supervisor or OpenAISupervisor()

    def handle(self, case: ExtractionCase) -> MaestroOutcome:
        self.memory.remember_case(case)
        prior = self.memory.recommend_strategy(case)

        needs_specialist = case.status != "OK" or not case.verification_ok
        specialist_result = self.specialist.analyze(case) if needs_specialist else None
        validator = validate_case(
            case.values,
            specialist_result.values if specialist_result and specialist_result.values else None,
            case.verification_ok,
        )
        if prior:
            validator["memory_prior"] = {
                "strategy": prior.get("strategy"),
                "successes": prior.get("successes"),
                "failures": prior.get("failures"),
                "avg_confidence": prior.get("avg_confidence"),
            }
        decision = self.supervisor.review(case, specialist_result, validator)

        memory_action = "CASE_RECORDED"
        if specialist_result and decision.learn_strategy:
            success = bool(validator.get("ok"))
            self.memory.learn_strategy(
                case, specialist_result.strategy, specialist_result.confidence, success,
                {"validator": validator, "decision": decision.to_dict()},
            )
            memory_action = "STRATEGY_LEARNED"

        if decision.patch_candidate:
            create_patch_candidate(CONFIG.patch_dir, case, decision, diagnosis=decision.reason)
            memory_action += "+PATCH_PROPOSED"

        outcome = MaestroOutcome(
            case=case,
            specialist=specialist_result,
            supervisor=decision,
            validator=validator,
            memory_action=memory_action,
            shadow_only=True,
        )
        self.memory.remember_outcome(outcome)
        return outcome
