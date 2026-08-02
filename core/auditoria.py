from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

RREO_LOG_SHEET = "LOG_RREO"
FNDE_LOG_SHEET = "LOG_FNDE"
MISSING_SHEET = "MUNICIPIOS_NAO_ENCONTRADOS"
AUDIT_SHEET = "AUDITORIA"

RREO_LOG_HEADERS = [
    "Data/Hora", "PDF RREO", "Município", "Código IBGE", "UF", "Ano",
    "Estado/Lote", "Linha da planilha", "Campos RREO preenchidos",
    "Códigos encontrados", "Códigos ausentes", "Status", "Método de extração",
    "Status do upload", "Tentativas de upload", "Pasta de destino",
    "Erro resumido", "Observações",
]

FNDE_LOG_HEADERS = [
    "Data/Hora", "PDF FNDE", "Município", "Código IBGE", "UF", "Ano",
    "Estado/Lote", "Linha da planilha", "Campos FNDE preenchidos",
    "Programas encontrados", "Programas ausentes", "Valores extraídos",
    "Método de extração", "Modelo Gemini", "Tentativas Gemini", "Status",
    "Status do upload", "Tentativas de upload", "Pasta de destino",
    "Erro resumido", "Avisos",
]

MISSING_HEADERS = [
    "Estado/UF", "Código IBGE", "Município da planilha-base", "Situação",
    "PDF RREO correspondente", "PDF FNDE correspondente", "Observação",
]


def _sheet(workbook: Workbook, name: str, headers: list[str]) -> Worksheet:
    if name in workbook.sheetnames:
        ws = workbook[name]
        if ws.max_row == 1 and all(ws.cell(1, c).value is None for c in range(1, len(headers) + 1)):
            for c, value in enumerate(headers, 1):
                ws.cell(1, c, value)
    else:
        ws = workbook.create_sheet(name)
        ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def append_rreo_log(workbook: Workbook, item: dict[str, Any]) -> None:
    ws = _sheet(workbook, RREO_LOG_SHEET, RREO_LOG_HEADERS)
    ws.append([item.get(header, "") for header in RREO_LOG_HEADERS])


def append_fnde_log(workbook: Workbook, item: dict[str, Any]) -> None:
    ws = _sheet(workbook, FNDE_LOG_SHEET, FNDE_LOG_HEADERS)
    ws.append([item.get(header, "") for header in FNDE_LOG_HEADERS])


def append_log(workbook: Workbook, item: dict[str, Any]) -> None:
    """Compatibilidade: encaminha ao log RREO."""
    append_rreo_log(workbook, item)


def write_missing(workbook: Workbook, rows: Iterable[dict[str, Any]]) -> None:
    if MISSING_SHEET in workbook.sheetnames:
        del workbook[MISSING_SHEET]
    ws = _sheet(workbook, MISSING_SHEET, MISSING_HEADERS)
    for item in rows:
        ws.append([item.get(header, "") for header in MISSING_HEADERS])
    for column, width in {"A": 15, "B": 16, "C": 34, "D": 36, "E": 44, "F": 44, "G": 60}.items():
        ws.column_dimensions[column].width = width


def write_audit(workbook: Workbook, metrics: dict[str, Any]) -> None:
    if AUDIT_SHEET in workbook.sheetnames:
        del workbook[AUDIT_SHEET]
    ws = workbook.create_sheet(AUDIT_SHEET)
    ws.append(["Item", "Valor"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for key, value in metrics.items():
        ws.append([key, value])
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 72
    ws.freeze_panes = "A2"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
