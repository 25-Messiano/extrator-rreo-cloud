from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    cpu_count: int
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


def recommended_profile(cpu_count: int | None = None) -> RuntimeProfile:
    """Perfil proporcional com prioridade para confiabilidade.

    RREO possui mais campos e recebe mais workers leves. FNDE possui apenas
    quatro campos, mas leitura de imagem/OCR e mais cara. Uma parcela da
    capacidade fica reservada para a segunda leitura/validacao. Os numeros sao
    limites de concorrencia, nao CPUs exclusivas; as filas podem compartilhar o
    tempo de CPU quando a outra fonte estiver ociosa.
    """
    cpus = max(1, int(cpu_count or detect_cpu_capacity()))

    if cpus <= 1:
        return RuntimeProfile(cpus, 4, 1, 1, 1, 1, "Seguro 1 CPU")
    if cpus == 2:
        return RuntimeProfile(cpus, 6, 2, 1, 1, 1, "Seguro 2 CPUs")
    if cpus <= 4:
        # Pro Plus 4 CPUs: volume maior no RREO, FNDE mais pesado e um canal
        # dedicado a rechecagem. Threads sao limitadas para nao saturar OCR.
        return RuntimeProfile(cpus, 8, 3, 2, 1, 1, "Confiavel 4 CPUs")
    if cpus <= 8:
        return RuntimeProfile(cpus, 12, 5, 3, 2, 2, "Confiavel 8 CPUs")

    # Escala proporcional sem explosao de threads em instancias grandes.
    rreo = min(10, max(6, round(cpus * 0.55)))
    fnde = min(6, max(3, round(cpus * 0.30)))
    verification = min(4, max(2, round(cpus * 0.20)))
    gemini = min(3, max(1, round(cpus * 0.15)))
    return RuntimeProfile(cpus, min(20, max(12, cpus * 2)), rreo, fnde, verification, gemini, "Confiavel 8+ CPUs")
