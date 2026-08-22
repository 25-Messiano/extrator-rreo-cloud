from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Fonte(str, Enum):
    RREO = "RREO"
    FNDE = "FNDE"
    COMBINADO = "RREO + FNDE"


class Abrangencia(str, Enum):
    ESTADO_INTEIRO = "Estado inteiro"
    MUNICIPIO_UNICO = "Município único"
    MUNICIPIOS_SELECIONADOS = "Municípios selecionados"
    TODOS_OS_ESTADOS = "Todos os Estados"
    AMOSTRA = "Amostra"


@dataclass(frozen=True)
class PoliticaExecucao:
    fonte: Fonte
    abrangencia: Abrangencia
    usar_rreo: bool
    usar_fnde: bool
    usar_indice_rreo: bool
    usar_indice_fnde: bool
    gerar_log_rreo: bool
    gerar_log_fnde: bool

    @property
    def combinada(self) -> bool:
        return self.usar_rreo and self.usar_fnde

    def exigir_isolamento(self) -> None:
        if self.fonte is Fonte.RREO and self.usar_fnde:
            raise RuntimeError("Política inválida: execução RREO não pode ativar FNDE.")
        if self.fonte is Fonte.FNDE and self.usar_rreo:
            raise RuntimeError("Política inválida: execução FNDE não pode ativar RREO.")


def criar_politica(fonte: Fonte, abrangencia: Abrangencia) -> PoliticaExecucao:
    usar_rreo = fonte in {Fonte.RREO, Fonte.COMBINADO}
    usar_fnde = fonte in {Fonte.FNDE, Fonte.COMBINADO}
    politica = PoliticaExecucao(
        fonte=fonte,
        abrangencia=abrangencia,
        usar_rreo=usar_rreo,
        usar_fnde=usar_fnde,
        usar_indice_rreo=usar_rreo,
        usar_indice_fnde=usar_fnde,
        gerar_log_rreo=usar_rreo,
        gerar_log_fnde=usar_fnde,
    )
    politica.exigir_isolamento()
    return politica


def politica_da_execucao(rotulo: str) -> PoliticaExecucao:
    partes = [parte.strip() for parte in str(rotulo).split("—", maxsplit=1)]
    if len(partes) != 2:
        raise ValueError(f"Execução inválida: {rotulo!r}")
    fonte_texto, abrangencia_texto = partes
    fonte = Fonte(fonte_texto)
    abrangencia = Abrangencia(abrangencia_texto)
    return criar_politica(fonte, abrangencia)


def matriz_operacoes() -> dict[str, dict[str, bool]]:
    return {
        "RREO": {"cloud": True, "indice_rreo": True, "indice_fnde": False, "rreo": True, "fnde": False},
        "FNDE": {"cloud": True, "indice_rreo": False, "indice_fnde": True, "rreo": False, "fnde": True},
        "RREO + FNDE": {"cloud": True, "indice_rreo": True, "indice_fnde": True, "rreo": True, "fnde": True},
    }
