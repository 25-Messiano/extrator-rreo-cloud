from __future__ import annotations

import asyncio
import json
import os
from typing import Callable

from core.maestro_ia.config import CONFIG
from core.maestro_ia.models import ExtractionCase, SpecialistResult, SupervisorDecision


SYSTEM_INSTRUCTIONS = """Você é o Supervisor do MAESTRO IA do Extrator RREO Cloud.
Você nunca altera código, nunca grava valores oficiais e nunca publica patches.
Analise falhas e divergências com conservadorismo. Se não houver evidência suficiente,
mande para PENDENTE_CONFERENCIA. Um patch é apenas uma proposta para homologação e
aprovação humana. Responda SOMENTE JSON com: decision, confidence, reason,
recommended_action, consensus, learn_strategy, patch_candidate, risk, tags.
"""


class OpenAISupervisor:
    def __init__(self, reviewer: Callable[[ExtractionCase, SpecialistResult | None, dict], SupervisorDecision] | None = None):
        self.reviewer = reviewer

    def review(self, case: ExtractionCase, specialist: SpecialistResult | None, validator: dict) -> SupervisorDecision:
        if self.reviewer is not None:
            return self.reviewer(case, specialist, validator)

        if not CONFIG.live_ai:
            return self._deterministic_shadow_review(case, specialist, validator)

        if not os.getenv("OPENAI_API_KEY"):
            return SupervisorDecision(
                decision="PENDENTE_CONFERENCIA",
                confidence=0.0,
                reason="OPENAI_API_KEY ausente no ambiente de execução.",
                recommended_action="CONFIGURAR_CHAVE_SEM_ALTERAR_PRODUCAO",
                risk="MEDIUM",
                tags=["CREDENTIAL_MISSING"],
            )
        try:
            from agents import Agent, Runner
        except ImportError:
            return SupervisorDecision(
                decision="PENDENTE_CONFERENCIA",
                confidence=0.0,
                reason="Pacote openai-agents não instalado.",
                recommended_action="INSTALAR_DEPENDENCIA_EM_HOMOLOGACAO",
                risk="MEDIUM",
                tags=["SDK_MISSING"],
            )

        payload = {
            "case": case.to_dict(),
            "specialist": specialist.to_dict() if specialist else None,
            "validator": validator,
        }
        agent = Agent(name="MAESTRO IA Supervisor", instructions=SYSTEM_INSTRUCTIONS, model=CONFIG.openai_model)

        async def _run() -> str:
            result = await Runner.run(agent, json.dumps(payload, ensure_ascii=False))
            return str(result.final_output)

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Streamlit pode já possuir loop. Executa em um loop separado em thread no runtime.
                raise RuntimeError("EVENT_LOOP_ACTIVE")
            raw = asyncio.run(_run())
            data = json.loads(raw)
            return SupervisorDecision(
                decision=str(data.get("decision") or "PENDENTE_CONFERENCIA"),
                confidence=float(data.get("confidence") or 0.0),
                reason=str(data.get("reason") or ""),
                recommended_action=str(data.get("recommended_action") or "CONFERIR"),
                consensus=bool(data.get("consensus")),
                learn_strategy=bool(data.get("learn_strategy")),
                patch_candidate=bool(data.get("patch_candidate")),
                risk=str(data.get("risk") or "MEDIUM"),
                tags=[str(v) for v in (data.get("tags") or [])],
            )
        except Exception as exc:
            return SupervisorDecision(
                decision="PENDENTE_CONFERENCIA",
                confidence=0.0,
                reason=f"Supervisor indisponível: {type(exc).__name__}",
                recommended_action="MANTER_RESULTADO_FORA_DA_BASE_OFICIAL",
                risk="MEDIUM",
                tags=["SUPERVISOR_FAILURE"],
            )

    @staticmethod
    def _deterministic_shadow_review(case: ExtractionCase, specialist: SpecialistResult | None, validator: dict) -> SupervisorDecision:
        if case.status == "OK" and case.verification_ok:
            return SupervisorDecision(
                decision="OBSERVADO_OK",
                confidence=1.0,
                reason="Motor determinístico e validação existentes indicam sucesso.",
                recommended_action="NENHUMA_ALTERACAO",
                consensus=True,
                risk="LOW",
                tags=["SHADOW", "BASELINE_OK"],
            )
        if specialist and validator.get("ok") and specialist.confidence >= CONFIG.confidence_auto_accept:
            return SupervisorDecision(
                decision="CANDIDATO_VALIDADO_EM_SOMBRA",
                confidence=specialist.confidence,
                reason="Especialista e validadores concordam; modo sombra impede gravação oficial.",
                recommended_action="REGISTRAR_ESTRATEGIA",
                consensus=True,
                learn_strategy=True,
                risk="LOW",
                tags=["SHADOW", "CONSENSUS"],
            )
        return SupervisorDecision(
            decision="PENDENTE_CONFERENCIA",
            confidence=max((specialist.confidence if specialist else 0.0), 0.0),
            reason="Falha/divergência sem consenso suficiente.",
            recommended_action="CENTRAL_DE_CORRECOES",
            consensus=False,
            patch_candidate=bool(case.error and "REPET" in case.error.upper()),
            risk="MEDIUM",
            tags=["SHADOW", "NO_CONSENSUS"],
        )
