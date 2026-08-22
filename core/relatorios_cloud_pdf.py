from __future__ import annotations

"""Relatorios PDF de inventario dos arquivos RREO/FNDE existentes no Cloud.

O relatorio nao abre nem extrai conteudo dos PDFs. Ele reutiliza os mesmos
indices seguros do painel para responder, por municipio oficial, se existe
arquivo RREO e/ou FNDE no Google Cloud Storage.
"""

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Iterable

from openpyxl import load_workbook
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.identificacao_arquivos import ESTADO_PARA_UF, UF_IBGE_PREFIX
from core.indice_fnde import build_fnde_index
from core.indice_rreo import build_rreo_index, localizar_por_municipio
from integrations.google_storage import list_fnde_pdfs_by_uf, list_rreo_pdfs_by_uf
from modules.mapeamento_nova_planilha import (
    carregar_municipios_da_planilha,
    obter_aba_destino,
    validar_estrutura_planilha,
)


ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class LinhaInventarioCloud:
    cidade: str
    estado: str
    rreo: bool
    fnde: bool
    codigo_ibge: str = ""

    def as_pdf_row(self) -> list[str]:
        return [
            self.cidade,
            self.estado,
            "SIM" if self.rreo else "NÃO",
            "SIM" if self.fnde else "NÃO",
        ]


@dataclass(frozen=True)
class ResumoInventarioCloud:
    municipios: int
    com_rreo: int
    com_fnde: int
    com_ambos: int
    somente_rreo: int
    somente_fnde: int
    sem_arquivos: int


UF_PARA_ESTADO = {uf: estado.title() for estado, uf in ESTADO_PARA_UF.items()}


def _municipios_por_uf(planilha_base: str | Path, ufs: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    """Carrega a matriz oficial uma unica vez e separa municipios por UF."""
    workbook = load_workbook(Path(planilha_base), read_only=False, data_only=False)
    try:
        worksheet = obter_aba_destino(workbook)
        validar_estrutura_planilha(worksheet)
        result: dict[str, list[dict[str, Any]]] = {}
        for uf in ufs:
            target = str(uf).upper().strip()
            prefixo = UF_IBGE_PREFIX.get(target, "")
            if not prefixo:
                result[target] = []
                continue
            result[target] = carregar_municipios_da_planilha(worksheet, target, prefixo)
        return result
    finally:
        workbook.close()


def inventariar_cloud(
    planilha_base: str | Path,
    ano: int,
    ufs: Iterable[str],
    progress_callback: ProgressCallback | None = None,
) -> list[LinhaInventarioCloud]:
    """Monta a matriz Cidade/Estado/RREO/FNDE usando as mesmas regras do painel."""
    lista_ufs = [str(uf).upper().strip() for uf in ufs if str(uf).strip()]
    municipios_por_uf = _municipios_por_uf(planilha_base, lista_ufs)
    linhas: list[LinhaInventarioCloud] = []
    total_ufs = len(lista_ufs)

    for posicao, uf in enumerate(lista_ufs, start=1):
        municipios = municipios_por_uf.get(uf, [])
        arquivos_rreo = list_rreo_pdfs_by_uf(uf, ano)
        arquivos_fnde = list_fnde_pdfs_by_uf(uf, ano)
        indice_rreo = build_rreo_index(arquivos_rreo, uf, municipios)
        indice_fnde = build_fnde_index(arquivos_fnde, uf, municipios).get("por_ibge", {})

        for municipio in municipios:
            codigo = str(municipio.get("codigo_ibge") or "")
            arquivo_rreo = localizar_por_municipio(
                indice_rreo,
                str(municipio.get("nome") or ""),
                uf,
                codigo,
            )
            linhas.append(
                LinhaInventarioCloud(
                    cidade=str(municipio.get("nome") or "").strip(),
                    estado=uf,
                    rreo=bool(arquivo_rreo),
                    fnde=bool(indice_fnde.get(codigo)),
                    codigo_ibge=codigo,
                )
            )

        if progress_callback is not None:
            progress_callback(posicao, total_ufs, uf)

    return linhas


def resumir_inventario(linhas: Iterable[LinhaInventarioCloud]) -> ResumoInventarioCloud:
    itens = list(linhas)
    com_rreo = sum(1 for item in itens if item.rreo)
    com_fnde = sum(1 for item in itens if item.fnde)
    com_ambos = sum(1 for item in itens if item.rreo and item.fnde)
    somente_rreo = sum(1 for item in itens if item.rreo and not item.fnde)
    somente_fnde = sum(1 for item in itens if item.fnde and not item.rreo)
    sem_arquivos = sum(1 for item in itens if not item.rreo and not item.fnde)
    return ResumoInventarioCloud(
        municipios=len(itens),
        com_rreo=com_rreo,
        com_fnde=com_fnde,
        com_ambos=com_ambos,
        somente_rreo=somente_rreo,
        somente_fnde=somente_fnde,
        sem_arquivos=sem_arquivos,
    )


def _sim_nao_paragraph(valor: bool, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph("SIM" if valor else "NÃO", styles["StatusSim"] if valor else styles["StatusNao"])


def gerar_pdf_inventario(
    linhas: Iterable[LinhaInventarioCloud],
    ano: int,
    titulo_escopo: str,
) -> bytes:
    """Gera PDF multipagina com cabecalho repetido e tabela exata solicitada."""
    itens = list(linhas)
    resumo = resumir_inventario(itens)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Inventario Cloud RREO/FNDE - {titulo_escopo} - {ano}",
        author="Extrator RREO Cloud",
    )

    sample = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            "CloudTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=colors.HexColor("#17233D"),
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "Sub": ParagraphStyle(
            "CloudSub",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=4 * mm,
        ),
        "SummaryLabel": ParagraphStyle(
            "SummaryLabel",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_CENTER,
        ),
        "SummaryValue": ParagraphStyle(
            "SummaryValue",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=11,
            textColor=colors.HexColor("#17233D"),
            alignment=TA_CENTER,
        ),
        "Cell": ParagraphStyle(
            "Cell",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.2,
            textColor=colors.HexColor("#1F2937"),
        ),
        "CellCenter": ParagraphStyle(
            "CellCenter",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.2,
            textColor=colors.HexColor("#1F2937"),
            alignment=TA_CENTER,
        ),
        "Header": ParagraphStyle(
            "Header",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "StatusSim": ParagraphStyle(
            "StatusSim",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#15803D"),
            alignment=TA_CENTER,
        ),
        "StatusNao": ParagraphStyle(
            "StatusNao",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#B91C1C"),
            alignment=TA_CENTER,
        ),
    }

    story: list[Any] = [
        Paragraph("Relatório de Arquivos no Cloud Storage - RREO/FNDE", styles["Title"]),
        Paragraph(
            f"Escopo: <b>{titulo_escopo}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Ano: <b>{ano}</b> "
            f"&nbsp;&nbsp;|&nbsp;&nbsp; Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles["Sub"],
        ),
    ]

    resumo_data = [
        [
            Paragraph("MUNICIPIOS", styles["SummaryLabel"]),
            Paragraph("COM RREO", styles["SummaryLabel"]),
            Paragraph("COM FNDE", styles["SummaryLabel"]),
            Paragraph("COM AMBOS", styles["SummaryLabel"]),
            Paragraph("SEM ARQUIVOS", styles["SummaryLabel"]),
        ],
        [
            Paragraph(str(resumo.municipios), styles["SummaryValue"]),
            Paragraph(str(resumo.com_rreo), styles["SummaryValue"]),
            Paragraph(str(resumo.com_fnde), styles["SummaryValue"]),
            Paragraph(str(resumo.com_ambos), styles["SummaryValue"]),
            Paragraph(str(resumo.sem_arquivos), styles["SummaryValue"]),
        ],
    ]
    resumo_table = Table(resumo_data, colWidths=[34 * mm] * 5)
    resumo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE3EE")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E5EAF2")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([resumo_table, Spacer(1, 5 * mm)])

    data: list[list[Any]] = [
        [
            Paragraph("CIDADE", styles["Header"]),
            Paragraph("ESTADO", styles["Header"]),
            Paragraph("RREO", styles["Header"]),
            Paragraph("FNDE", styles["Header"]),
        ]
    ]
    for item in itens:
        data.append(
            [
                Paragraph(item.cidade, styles["Cell"]),
                Paragraph(item.estado, styles["CellCenter"]),
                _sim_nao_paragraph(item.rreo, styles),
                _sim_nao_paragraph(item.fnde, styles),
            ]
        )

    tabela = LongTable(
        data,
        repeatRows=1,
        colWidths=[105 * mm, 28 * mm, 23 * mm, 23 * mm],
        hAlign="CENTER",
    )
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DEE8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    story.append(tabela)

    def _rodape(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.4)
        canvas.line(15 * mm, 10 * mm, A4[0] - 15 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(15 * mm, 6.5 * mm, "Extrator RREO Cloud - inventario de arquivos existentes no Google Cloud Storage")
        canvas.drawRightString(A4[0] - 15 * mm, 6.5 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()


def gerar_relatorio_cloud_pdf(
    planilha_base: str | Path,
    ano: int,
    ufs: Iterable[str],
    titulo_escopo: str,
    progress_callback: ProgressCallback | None = None,
) -> tuple[bytes, ResumoInventarioCloud]:
    linhas = inventariar_cloud(planilha_base, ano, ufs, progress_callback)
    pdf = gerar_pdf_inventario(linhas, ano, titulo_escopo)
    return pdf, resumir_inventario(linhas)
