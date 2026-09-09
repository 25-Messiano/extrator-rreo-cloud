from __future__ import annotations
from pathlib import Path
from typing import Mapping
from openpyxl import load_workbook
from destinos import POR_CODIGO, CAMPOS, validar_destinos_unicos
from destinos.base_destino import ABA_OFICIAL


def gravar_resultados(caminho_entrada: str|Path, caminho_saida: str|Path, ibge: str, valores: Mapping[str,float|None]):
    """ÚNICA camada autorizada a escrever no Excel. Extratores de PDF não importam openpyxl."""
    wb = load_workbook(caminho_entrada, data_only=False)
    ws = wb[ABA_OFICIAL]
    validar_destinos_unicos(ws, CAMPOS)
    alteradas=[]
    for codigo, valor in valores.items():
        campo = POR_CODIGO.get(str(codigo))
        if campo is None or valor is None or not campo.gravar:
            continue
        alteradas.append((codigo, campo.escrever(ws, ibge, float(valor))))
    wb.save(caminho_saida)
    return alteradas
