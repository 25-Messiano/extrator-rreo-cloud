from __future__ import annotations

from typing import Any, Callable

from core.politica_operacoes import Fonte, PoliticaExecucao
from core.processamento_lotes import execute_dual_parallel
from core.processamento_lotes_rreo import executar_lote_rreo
from core.processamento_lotes_fnde import executar_lote_fnde


def executar_lote_politica(
    politica: PoliticaExecucao,
    itens: list[dict[str, Any]],
    rreo_worker: Callable[[dict[str, Any]], Any] | None,
    fnde_worker: Callable[[dict[str, Any]], Any] | None,
    rreo_workers: int,
    fnde_workers: int,
):
    politica.exigir_isolamento()
    if politica.fonte is Fonte.RREO:
        if rreo_worker is None:
            raise RuntimeError("Worker RREO não fornecido.")
        return executar_lote_rreo(politica, itens, rreo_worker, rreo_workers), {}
    if politica.fonte is Fonte.FNDE:
        if fnde_worker is None:
            raise RuntimeError("Worker FNDE não fornecido.")
        return {}, executar_lote_fnde(politica, itens, fnde_worker, fnde_workers)
    if rreo_worker is None or fnde_worker is None:
        raise RuntimeError("Execução combinada exige os dois workers.")
    return execute_dual_parallel(itens, rreo_worker, fnde_worker, rreo_workers, fnde_workers)
