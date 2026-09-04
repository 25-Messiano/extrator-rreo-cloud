from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True, slots=True)
class MaestroConfig:
    enabled: bool = _bool("MAESTRO_IA_ENABLED", True)
    shadow_mode: bool = _bool("MAESTRO_IA_SHADOW_MODE", True)
    live_ai: bool = _bool("MAESTRO_IA_LIVE_AI", False)
    openai_model: str = os.getenv("MAESTRO_OPENAI_MODEL", "gpt-5.6-mini").strip()
    confidence_auto_accept: float = float(os.getenv("MAESTRO_CONFIDENCE_AUTO_ACCEPT", "0.985"))
    confidence_review: float = float(os.getenv("MAESTRO_CONFIDENCE_REVIEW", "0.90"))
    memory_path: str = os.getenv("MAESTRO_MEMORY_DB", "data/maestro_ia_memory.sqlite3")
    patch_dir: str = os.getenv("MAESTRO_PATCH_DIR", "data/maestro_ia_patch_candidates")
    max_background_workers: int = max(1, min(int(os.getenv("MAESTRO_BG_WORKERS", "1")), 2))


CONFIG = MaestroConfig()
