from __future__ import annotations

from typing import Any, Callable

from core.politica_operacoes import Fonte, PoliticaExecucao
from core.processamento_lotes import execute_dual_parallel
from core.processamento_lotes_rreo import executar_lote_rreo
from core.processamento_lotes_fnde import executar_lote_fnde
from core.recursos_execucao import low_memory_mode


def executar_lote_politica(
    politica: PoliticaExecucao,
    itens: list[dict[str, Any]],
    rreo_worker: Callable[[dict[str, Any]], Any] | None,
    fnde_worker: Callable[[dict[str, Any]], Any] | None,
    rreo_workers: int,
    fnde_workers: int,
    timeout_seconds: int = 420,
):
    politica.exigir_isolamento()
    if politica.fonte is Fonte.RREO:
        if rreo_worker is None:
            raise RuntimeError("Worker RREO não fornecido.")
        return executar_lote_rreo(politica, itens, rreo_worker, rreo_workers, timeout_seconds), {}
    if politica.fonte is Fonte.FNDE:
        if fnde_worker is None:
            raise RuntimeError("Worker FNDE não fornecido.")
        return {}, executar_lote_fnde(politica, itens, fnde_worker, fnde_workers, timeout_seconds)
    if rreo_worker is None or fnde_worker is None:
        raise RuntimeError("Execução combinada exige os dois workers.")

    # Em instâncias com pouca RAM (Free/Starter), não executamos RREO e FNDE
    # simultaneamente. Mesmo com 1 worker de cada fonte, dois PDFs abertos ao
    # mesmo tempo podem ultrapassar o limite de memória do Render.
    if low_memory_mode():
        from core.processamento_lotes import execute_parallel
        rreo_result = execute_parallel(itens, rreo_worker, 1, timeout_seconds)
        fnde_result = execute_parallel(itens, fnde_worker, 1, timeout_seconds)
        return rreo_result, fnde_result

    return execute_dual_parallel(
        itens, rreo_worker, fnde_worker, rreo_workers, fnde_workers, timeout_seconds
    )
