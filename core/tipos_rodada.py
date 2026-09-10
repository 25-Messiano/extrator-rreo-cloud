"""Política central dos tipos de rodada do Extrator RREO/FNDE.

A interface pode mudar, mas a regra de dados deve permanecer concentrada aqui.
"""
from __future__ import annotations

from enum import Enum


class TipoRodada(str, Enum):
    NOVA = "Rodada Nova"
    CORRECAO = "Rodada de Correção"
    INCREMENTACAO = "Rodada de Incrementação"


DESCRICOES: dict[TipoRodada, str] = {
    TipoRodada.NOVA: (
        "Cria uma planilha limpa a partir da base oficial. Não herda valores "
        "de rodadas anteriores e não substitui automaticamente a planilha mestre."
    ),
    TipoRodada.CORRECAO: (
        "Usa a planilha mestre atual e força nova leitura da seleção. Quando a "
        "fonte é lida com sucesso, limpa os campos antigos dessa fonte e grava "
        "os novos valores."
    ),
    TipoRodada.INCREMENTACAO: (
        "Usa a planilha mestre atual e processa somente municípios ainda não "
        "concluídos para a operação selecionada."
    ),
}


def usa_master_existente(tipo: TipoRodada | str) -> bool:
    return TipoRodada(tipo) is not TipoRodada.NOVA


def forca_processamento(tipo: TipoRodada | str) -> bool:
    return TipoRodada(tipo) in {TipoRodada.NOVA, TipoRodada.CORRECAO}


def limpa_fonte_antes_de_gravar(tipo: TipoRodada | str) -> bool:
    return TipoRodada(tipo) is TipoRodada.CORRECAO


def atualiza_atividade_global(tipo: TipoRodada | str) -> bool:
    # Rodada Nova é independente do master. Marcar atividade global faria uma
    # futura incrementação pular municípios que ainda não foram incorporados ao master.
    return TipoRodada(tipo) is not TipoRodada.NOVA


def incremental_ja_concluido(
    row: dict | None,
    usar_rreo: bool,
    usar_fnde: bool,
    tem_arquivo_rreo: bool,
    tem_arquivo_fnde: bool,
) -> bool:
    """Decide se a Rodada de Incrementação pode pular o município.

    Se uma fonte estava marcada como SEM_PDF, mas um arquivo novo passou a
    existir no Cloud, o município volta a ser elegível para processamento.
    """
    if not row:
        return False

    def fonte_ok(enabled: bool, status: str, tem_arquivo: bool) -> bool:
        if not enabled:
            return True
        status = str(status or "").upper()
        if status == "OK":
            return True
        if status == "SEM_PDF":
            return not tem_arquivo
        return False

    return fonte_ok(usar_rreo, row.get("status_rreo", ""), tem_arquivo_rreo) and fonte_ok(
        usar_fnde, row.get("status_fnde", ""), tem_arquivo_fnde
    )


__all__ = [
    "TipoRodada",
    "DESCRICOES",
    "usa_master_existente",
    "forca_processamento",
    "limpa_fonte_antes_de_gravar",
    "atualiza_atividade_global",
    "incremental_ja_concluido",
]
