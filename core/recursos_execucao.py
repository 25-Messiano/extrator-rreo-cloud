from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    cpu_count: int
    memory_limit_mb: int | None
    batch_size: int
    rreo_workers: int
    fnde_workers: int
    verification_workers: int
    gemini_concurrency: int
    name: str


def _positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _cgroup_cpu_count() -> int | None:
    """Le a cota de CPU de containers Linux/cgroup v2 quando disponivel."""
    path = Path("/sys/fs/cgroup/cpu.max")
    try:
        quota_raw, period_raw = path.read_text(encoding="utf-8").strip().split()[:2]
        if quota_raw == "max":
            return None
        quota = int(quota_raw)
        period = int(period_raw)
        if quota <= 0 or period <= 0:
            return None
        return max(1, (quota + period - 1) // period)
    except (OSError, ValueError, IndexError):
        return None




def _cgroup_memory_limit_mb() -> int | None:
    """Lê o limite de RAM do container (cgroup v2/v1) quando disponível."""
    candidates = [
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ]
    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw or raw == "max":
                continue
            value = int(raw)
            # Alguns hosts expõem um número gigantesco para significar "sem limite".
            if value <= 0 or value >= (1 << 60):
                continue
            return max(64, value // (1024 * 1024))
        except (OSError, ValueError):
            continue
    return None


def detect_memory_limit_mb() -> int | None:
    """Detecta o teto de RAM disponível para o processo.

    APP_MEMORY_LIMIT_MB permite sobrescrever manualmente no Render. Quando não
    informado, usa o limite do cgroup do container.
    """
    override = _positive_int(os.getenv("APP_MEMORY_LIMIT_MB"))
    if override:
        return override
    return _cgroup_memory_limit_mb()

def detect_cpu_capacity() -> int:
    """Detecta a capacidade de CPU disponivel no Render/container.

    APP_CPU_COUNT permite sobrescrever manualmente. WEB_CONCURRENCY e usado
    apenas como indicio de capacidade quando o Render o fornece. A distribuicao
    real dos workers e recalculada pelo perfil abaixo, portanto mudar de plano
    nao exige editar codigo.
    """
    for candidate in (
        _positive_int(os.getenv("APP_CPU_COUNT")),
        _positive_int(os.getenv("WEB_CONCURRENCY")),
        _cgroup_cpu_count(),
        os.cpu_count(),
    ):
        if candidate:
            return max(1, min(int(candidate), 64))
    return 1


def recommended_profile(
    cpu_count: int | None = None,
    memory_limit_mb: int | None = None,
) -> RuntimeProfile:
    """Perfil proporcional com limite explícito de memória.

    Em instâncias pequenas, RAM é o gargalo antes da CPU. Por isso o tamanho
    do lote cai para 1–2 municípios e o processamento pesado fica serial.
    Em máquinas maiores, a concorrência cresce de forma conservadora.
    """
    cpus = max(1, int(cpu_count or detect_cpu_capacity()))
    memory_mb = memory_limit_mb if memory_limit_mb is not None else detect_memory_limit_mb()

    # Render Free/Starter ou containers equivalentes. Um PDF/OCR por vez evita
    # picos que fazem o Render matar a instância por exceder RAM.
    if memory_mb is not None and memory_mb <= 768:
        return RuntimeProfile(cpus, memory_mb, 1, 1, 1, 1, 1, "Memória mínima <=768 MB")
    if memory_mb is not None and memory_mb <= 1536:
        return RuntimeProfile(cpus, memory_mb, 2, 1, 1, 1, 1, "Memória baixa <=1.5 GB")

    if cpus <= 1:
        # Standard 1 CPU/2 GB continua conservador para PDF + openpyxl.
        return RuntimeProfile(cpus, memory_mb, 2, 1, 1, 1, 1, "Seguro 1 CPU")
    if cpus == 2:
        return RuntimeProfile(cpus, memory_mb, 4, 2, 1, 1, 1, "Seguro 2 CPUs")
    if cpus <= 4:
        return RuntimeProfile(cpus, memory_mb, 8, 3, 2, 1, 1, "Confiavel 4 CPUs")
    if cpus <= 8:
        return RuntimeProfile(cpus, memory_mb, 12, 5, 3, 2, 2, "Confiavel 8 CPUs")

    rreo = min(10, max(6, round(cpus * 0.55)))
    fnde = min(6, max(3, round(cpus * 0.30)))
    verification = min(4, max(2, round(cpus * 0.20)))
    gemini = min(3, max(1, round(cpus * 0.15)))
    return RuntimeProfile(
        cpus, memory_mb, min(20, max(12, cpus * 2)),
        rreo, fnde, verification, gemini, "Confiavel 8+ CPUs"
    )


def low_memory_mode(memory_limit_mb: int | None = None) -> bool:
    limit = memory_limit_mb if memory_limit_mb is not None else detect_memory_limit_mb()
    return limit is not None and limit <= 1536
