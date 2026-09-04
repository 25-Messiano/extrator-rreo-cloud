from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ExtractionCase:
    case_id: str
    source: str
    year: int
    uf: str
    ibge: str
    municipality: str
    operation: str
    status: str
    error: str = ""
    pdf_name: str = ""
    values: dict[str, float | None] = field(default_factory=dict)
    verification_ok: bool = False
    verification_method: str = ""
    divergences: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpecialistResult:
    provider: str
    status: str
    values: dict[str, float | None] = field(default_factory=dict)
    confidence: float = 0.0
    rationale: str = ""
    strategy: str = ""
    evidence: list[str] = field(default_factory=list)
    model: str = ""
    attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupervisorDecision:
    decision: str
    confidence: float
    reason: str
    recommended_action: str
    consensus: bool = False
    learn_strategy: bool = False
    patch_candidate: bool = False
    risk: str = "LOW"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MaestroOutcome:
    case: ExtractionCase
    specialist: SpecialistResult | None
    supervisor: SupervisorDecision
    validator: dict[str, Any]
    memory_action: str
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case.to_dict(),
            "specialist": self.specialist.to_dict() if self.specialist else None,
            "supervisor": self.supervisor.to_dict(),
            "validator": self.validator,
            "memory_action": self.memory_action,
            "shadow_only": self.shadow_only,
        }
