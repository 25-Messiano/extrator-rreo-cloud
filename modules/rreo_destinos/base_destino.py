from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from openpyxl.worksheet.worksheet import Worksheet

ABA_OFICIAL = "Estado de Goiás-GO"
COLUNA_IBGE = 3  # C
COLUNA_ENTE = 4  # D
LINHA_CABECALHO = 1
PRIMEIRA_LINHA_DADOS = 3


def normalizar(texto: object) -> str:
    s = "" if texto is None else str(texto)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper().replace("–", "-").replace("—", "-")
    s = re.sub(r"[^A-Z0-9.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def codigo_exato_no_cabecalho(cabecalho: object, codigo: str) -> bool:
    """Localiza o código inteiro em qualquer posição; 2.1 nunca casa 2.1.1."""
    bruto = "" if cabecalho is None else str(cabecalho)
    padrao = r"(?<![0-9.])" + re.escape(codigo) + r"(?![0-9.])"
    return bool(re.search(padrao, bruto))


@dataclass(frozen=True)
class DestinoCampo:
    codigo: str
    aliases: tuple[str, ...]
    gravar: bool = True

    def localizar_coluna(self, ws: Worksheet) -> int | None:
        if not self.gravar:
            return None
        # 1) prioridade absoluta: código inteiro no início do cabeçalho
        for col in range(1, ws.max_column + 1):
            if codigo_exato_no_cabecalho(ws.cell(LINHA_CABECALHO, col).value, self.codigo):
                return col
        # 2) fallback semântico tolerante aos erros tipográficos do modelo
        aliases_n = tuple(normalizar(a) for a in self.aliases)
        for col in range(1, ws.max_column + 1):
            h = normalizar(ws.cell(LINHA_CABECALHO, col).value)
            if h and any(a and a in h for a in aliases_n):
                return col
        return None

    def localizar_linha_municipio(self, ws: Worksheet, ibge: str | int) -> int:
        alvo = re.sub(r"\D", "", str(ibge))
        if len(alvo) != 7:
            raise ValueError(f"IBGE inválido: {ibge!r}")
        for row in range(PRIMEIRA_LINHA_DADOS, ws.max_row + 1):
            atual = re.sub(r"\D", "", str(ws.cell(row, COLUNA_IBGE).value or ""))
            if atual == alvo:
                return row
        raise KeyError(f"IBGE {alvo} não encontrado na coluna C")

    def escrever(self, ws: Worksheet, ibge: str | int, valor: float) -> str:
        if ws.title != ABA_OFICIAL:
            raise ValueError(f"Aba inválida: {ws.title!r}; esperada {ABA_OFICIAL!r}")
        if not self.gravar:
            raise RuntimeError(f"{self.codigo} é campo de validação e NÃO possui destino no Excel")
        coluna = self.localizar_coluna(ws)
        if coluna is None:
            raise KeyError(f"Cabeçalho de destino não encontrado para {self.codigo}")
        linha = self.localizar_linha_municipio(ws, ibge)
        celula = ws.cell(linha, coluna)
        celula.value = float(valor)
        celula.number_format = '#,##0.00;[Red](#,##0.00);-'
        return celula.coordinate


def validar_destinos_unicos(ws: Worksheet, campos: Iterable[DestinoCampo]) -> dict[str, int | None]:
    mapa: dict[str, int | None] = {}
    usadas: dict[int, str] = {}
    for campo in campos:
        col = campo.localizar_coluna(ws)
        mapa[campo.codigo] = col
        if campo.gravar:
            if col is None:
                raise KeyError(f"Destino ausente para {campo.codigo}")
            if col in usadas:
                raise RuntimeError(f"Colisão: {campo.codigo} e {usadas[col]} apontam para a coluna {col}")
            usadas[col] = campo.codigo
    return mapa
