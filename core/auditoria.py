from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

LOG_SHEET = "LOG_PROCESSAMENTO"
MISSING_SHEET = "MUNICIPIOS_NAO_ENCONTRADOS"
AUDIT_SHEET = "AUDITORIA"

LOG_HEADERS = [
    "Data/Hora", "PDF processado", "Município", "Código IBGE", "UF", "Ano",
    "Estado/Lote", "Linha da planilha", "Campos preenchidos", "Códigos encontrados",
    "Códigos ausentes", "FNDE processado", "Programas FNDE encontrados", "Status",
    "Status do upload", "Tentativas de upload", "Pasta de destino", "Erro resumido",
    "Observações",
]

MISSING_HEADERS = [
    "Estado/UF", "Código IBGE", "Município da planilha-base", "Situação",
    "PDF correspondente", "Observação",
]


def _sheet(workbook: Workbook, name: str, headers: list[str]) -> Worksheet:
    if name in workbook.sheetnames:
        ws = workbook[name]
        if ws.max_row == 1 and all(ws.cell(1, c).value is None for c in range(1, len(headers)+1)):
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
    return ws


def append_log(workbook: Workbook, item: dict[str, Any]) -> None:
    ws = _sheet(workbook, LOG_SHEET, LOG_HEADERS)
    ws.append([item.get(h, "") for h in LOG_HEADERS])


def write_missing(workbook: Workbook, rows: Iterable[dict[str, Any]]) -> None:
    if MISSING_SHEET in workbook.sheetnames:
        del workbook[MISSING_SHEET]
    ws = _sheet(workbook, MISSING_SHEET, MISSING_HEADERS)
    for item in rows:
        ws.append([item.get(h, "") for h in MISSING_HEADERS])


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
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 60
    ws.freeze_panes = "A2"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
