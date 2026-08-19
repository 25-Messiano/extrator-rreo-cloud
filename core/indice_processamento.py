from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.indice_rreo import localizar_por_municipio
from core.politica_operacoes import PoliticaExecucao


@dataclass
class TarefaProcessamento:
    codigo_ibge: str
    municipio: str
    uf: str
    row: int
    rreo: dict[str, Any] | None
    fnde: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "codigo_ibge": self.codigo_ibge,
            "municipio": self.municipio,
            "uf": self.uf,
            "row": self.row,
            "arquivo_rreo": self.rreo,
            "arquivo_fnde": self.fnde,
        }


def montar_plano(
    municipios: Iterable[dict[str, Any]],
    indice_rreo: dict[str, Any] | None,
    indice_fnde: dict[str, Any] | None,
    politica: PoliticaExecucao | None = None,
    usar_rreo: bool | None = None,
    usar_fnde: bool | None = None,
) -> list[TarefaProcessamento]:
    if politica is not None:
        politica.exigir_isolamento()
        usar_rreo = politica.usar_rreo
        usar_fnde = politica.usar_fnde
    if usar_rreo is None or usar_fnde is None:
        raise ValueError("Informe a política de execução ou os dois sinalizadores de fonte.")

    fnde_by_code = (indice_fnde or {}).get("por_ibge", indice_fnde or {})
    tasks: list[TarefaProcessamento] = []
    for city in municipios:
        rreo = localizar_por_municipio(indice_rreo or {}, city["nome"], city["uf"]) if usar_rreo else None
        fnde = fnde_by_code.get(city["codigo_ibge"]) if usar_fnde else None
        tasks.append(TarefaProcessamento(
            codigo_ibge=city["codigo_ibge"],
            municipio=city["nome"],
            uf=city["uf"],
            row=int(city.get("row") or 0),
            rreo=rreo,
            fnde=fnde,
        ))
    return tasks
