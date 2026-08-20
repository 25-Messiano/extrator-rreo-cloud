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
    """Lê a cota de CPU de containers Linux/cgroup v2 quando disponível."""
    path = Path("/sys/fs/cgroup/cpu.max")
    try:
        quota_raw, period_raw = path.read_text(encoding="utf-8").strip().split()[:2]
        if quota_raw == "max":
            return None
        quota = int(quota_raw)
        period = int(period_raw)
        if quota <= 0 or period <= 0:
            return None
        # Arredondamento para cima evita tratar 1.5 CPU como apenas 1.
        return max(1, (quota + period - 1) // period)
    except (OSError, ValueError, IndexError):
        return None


def detect_cpu_capacity() -> int:
    """Detecta a capacidade de CPU disponível no Render/container.

    APP_CPU_COUNT permite sobrescrever manualmente. No Render, WEB_CONCURRENCY
    é definido a partir da quantidade de CPUs da instância e por isso é uma
    referência melhor do que os.cpu_count() em alguns hosts compartilhados.
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
    cpus = max(1, int(cpu_count or detect_cpu_capacity()))

    if cpus <= 1:
        return RuntimeProfile(cpus, 6, 2, 1, 1, "Econômico 1 CPU")
    if cpus == 2:
        return RuntimeProfile(cpus, 10, 4, 2, 1, "Equilibrado 2 CPUs")
    if cpus <= 4:
        return RuntimeProfile(cpus, 12, 6, 3, 2, "Desempenho 4 CPUs")
    if cpus <= 8:
        return RuntimeProfile(cpus, 16, 8, 4, 2, "Alto desempenho 8 CPUs")
    return RuntimeProfile(cpus, 20, 8, 4, 2, "Alto desempenho 8+ CPUs")
