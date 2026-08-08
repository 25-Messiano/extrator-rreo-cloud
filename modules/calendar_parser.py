from __future__ import annotations

import re
from dataclasses import dataclass

DATE_RE = re.compile(r"^(?P<dia>\d{2})/(?P<mes>\d{2})/(?P<ano>-?\d+)(?P<era>aC|dC)")


@dataclass(frozen=True)
class ParsedDate:
    dia: int
    mes: int
    ano_literal: str
    ano_num: int
    era: str


def parse_data_literal(valor: str) -> ParsedDate:
    m = DATE_RE.match(valor.strip())
    if not m:
        raise ValueError(f"Data inválida: {valor}")
    ano_raw = int(m.group("ano"))
    era = m.group("era")
    # A base oficial já usa sinal negativo nos anos aC. Para tolerar entradas
    # sem sinal, normalizamos aC para negativo, preservando 0 como 0.
    ano_num = -abs(ano_raw) if era == "aC" and ano_raw != 0 else abs(ano_raw)
    if era == "dC":
        ano_num = abs(ano_raw)
    return ParsedDate(
        dia=int(m.group("dia")),
        mes=int(m.group("mes")),
        ano_literal=f"{m.group('ano')}{era}",
        ano_num=ano_num,
        era=era,
    )


def parse_linha_calendario(linha: str):
    original = linha.rstrip("\r\n")
    if not original.startswith("G.") or ">M." not in original:
        return None
    parte_g, direita = original.split(">", 1)
    if "|" in direita:
        parte_m, marcacoes = direita.split("|", 1)
    else:
        parte_m, marcacoes = direita, ""
    conteudo_g = parte_g[2:]
    if "." not in conteudo_g:
        return None
    data_g, dia_semana = conteudo_g.rsplit(".", 1)
    data_m = parte_m[2:]
    pg = parse_data_literal(data_g)
    pm = parse_data_literal(data_m)
    data_g_limpa = f"{pg.dia:02d}/{pg.mes:02d}/{pg.ano_literal}"
    data_m_limpa = f"{pm.dia:02d}/{pm.mes:02d}/{pm.ano_literal}"
    return {
        "chave_g": parte_g,
        "data_g": data_g_limpa,
        "g_dia": pg.dia,
        "g_mes": pg.mes,
        "g_ano_literal": pg.ano_literal,
        "g_ano_num": pg.ano_num,
        "dia_semana": dia_semana,
        "chave_m": parte_m,
        "data_m": data_m_limpa,
        "m_dia": pm.dia,
        "m_mes": pm.mes,
        "m_ano_literal": pm.ano_literal,
        "m_ano_num": pm.ano_num,
        "marcacoes": marcacoes,
        "linha_original": original,
    }


def data_g_de_linha_evento(linha: str) -> str | None:
    linha = linha.strip()
    if not linha.startswith("G."):
        return None
    corpo = linha[2:].split(">", 1)[0]
    if "." not in corpo:
        return None
    return corpo.rsplit(".", 1)[0]
