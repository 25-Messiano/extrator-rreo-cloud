from __future__ import annotations

from typing import Callable

from core.maestro_ia.models import ExtractionCase, SpecialistResult


class GeminiSpecialist:
    """Especialista de extração. Em sombra, pode operar com callable injetado em testes."""

    def __init__(self, extractor: Callable[[ExtractionCase], SpecialistResult] | None = None):
        self.extractor = extractor

    def analyze(self, case: ExtractionCase) -> SpecialistResult:
        if self.extractor is not None:
            return self.extractor(case)
        text = str(case.metadata.get("document_text") or "").strip()
        if case.source == "RREO" and text:
            try:
                from integrations.gemini import extract_rreo_values
                codes = list(case.divergences) or [k for k, v in case.values.items() if v is None]
                if not codes:
                    codes = list(case.values)
                values = extract_rreo_values(text[:45000], codes)
                filled = sum(v is not None for v in values.values())
                confidence = min(0.99, 0.70 + (0.29 * filled / max(len(codes), 1)))
                return SpecialistResult(
                    provider="GEMINI", status="OK" if filled else "SEM_RESULTADO",
                    values=values, confidence=confidence,
                    rationale="Releitura dirigida pelo Especialista Gemini em caso falho/divergente.",
                    strategy="GEMINI_RELEITURA_DIRECIONADA",
                )
            except Exception as exc:
                return SpecialistResult(
                    provider="GEMINI", status="ERROR", confidence=0.0,
                    rationale=f"Gemini indisponível: {type(exc).__name__}",
                    strategy="GEMINI_RELEITURA_DIRECIONADA",
                )
        return SpecialistResult(
            provider="GEMINI", status="NO_EVIDENCE", confidence=0.0,
            rationale="Modo sombra sem evidência textual/visual disponível para o especialista.",
            strategy="SEM_ACAO",
        )
