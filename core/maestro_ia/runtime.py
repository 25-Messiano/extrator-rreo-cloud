from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from core.maestro_ia.config import CONFIG
from core.maestro_ia.models import ExtractionCase
from core.maestro_ia.orchestrator import MaestroOrchestrator

_EXECUTOR = ThreadPoolExecutor(max_workers=CONFIG.max_background_workers, thread_name_prefix="maestro-shadow")
_LOCK = threading.Lock()
_ORCHESTRATOR: MaestroOrchestrator | None = None


def get_orchestrator() -> MaestroOrchestrator:
    global _ORCHESTRATOR
    with _LOCK:
        if _ORCHESTRATOR is None:
            _ORCHESTRATOR = MaestroOrchestrator()
    return _ORCHESTRATOR


def make_case_id(source: str, year: int, uf: str, ibge: str) -> str:
    return f"{source}-{year}-{uf}-{ibge}-{uuid4().hex[:8]}"


def observe_case(case: ExtractionCase) -> None:
    """Fire-and-forget. Nunca bloqueia nem muda o resultado oficial."""
    if not CONFIG.enabled:
        return

    def _job() -> None:
        try:
            get_orchestrator().handle(case)
        except Exception:
            # Modo sombra é estritamente não bloqueante.
            return

    _EXECUTOR.submit(_job)


def status_snapshot() -> dict[str, object]:
    try:
        memory = get_orchestrator().memory.summary()
    except Exception:
        memory = {"cases": 0, "outcomes": 0, "strategies": 0}
    return {
        "enabled": CONFIG.enabled,
        "shadow_mode": CONFIG.shadow_mode,
        "live_ai": CONFIG.live_ai,
        "memory": memory,
    }
