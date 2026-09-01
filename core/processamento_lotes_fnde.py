from __future__ import annotations

from typing import Any, Callable, TypeVar

from core.processamento_lotes import execute_parallel
from core.politica_operacoes import Fonte, PoliticaExecucao

R = TypeVar("R")


def executar_lote_fnde(politica: PoliticaExecucao, itens: list[dict[str, Any]], worker: Callable[[dict[str, Any]], R], max_workers: int, timeout_seconds: int = 420):
    if politica.fonte is not Fonte.FNDE:
        raise RuntimeError("Executor FNDE recebeu política de outra fonte.")
    return execute_parallel(itens, worker, max_workers, timeout_seconds)
