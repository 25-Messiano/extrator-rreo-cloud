from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.database.consultas import (
    buscar_por_g,
    buscar_por_m,
    estatisticas,
    listar_ano,
    listar_eventos_por_tipo,
    listar_festas_ativas,
    listar_intervalo_ids,
    listar_mes_g,
    listar_mes_m,
)

MESES_G = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}
MESES_M = {
    1: "Rúben", 2: "Simeão", 3: "Levi", 4: "Judá", 5: "Dã", 6: "Naftali", 7: "Gade",
    8: "Aser", 9: "Issacar", 10: "Zebulom", 11: "Diná", 12: "José", 13: "Benjamim",
}

REPORT_TYPES = {
    "mensal": "Relatório Mensal",
    "anual": "Relatório Anual",
    "correspondencia": "Correspondência G <-> M",
    "lua": "Fases da Lua",
    "estacoes": "Estações do Ano",
    "festas": "Festas Bíblicas",
    "data": "Data Específica",
    "intervalo": "Intervalo Personalizado",
    "auditoria": "Auditoria das Fontes",
}


@dataclass
class ReportRequest:
    tipo: str
    calendario: str = "both"
    referencia: str = "g"
    ano: int | None = None
    mes: int | None = None
    data: str = ""
    inicio: str = ""
    fim: str = ""
    lua: bool = True
    estacoes: bool = True
    pascoa: bool = True
    festas: bool = True


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor("#282330"), spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#706A76"), spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#463C55"), spaceBefore=7, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7, leading=12, textColor=colors.HexColor("#2E2B31")),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2, leading=9.5, textColor=colors.HexColor("#67616C")),
        "center": ParagraphStyle("center", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, alignment=TA_CENTER),
        "left": ParagraphStyle("left", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.5, alignment=TA_LEFT),
    }


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E2DFE5"))
    canvas.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#77727B"))
    canvas.drawString(16 * mm, 7.5 * mm, "Fonte dos dados: registros oficiais do calendário.")
    canvas.drawRightString(A4[0] - 16 * mm, 7.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _event_names(r: dict, req: ReportRequest) -> list[str]:
    out: list[str] = []
    for e in r.get("eventos", []):
        tipo = e.get("tipo")
        if tipo == "lua" and not req.lua:
            continue
        if tipo == "estacao" and not req.estacoes:
            continue
        if tipo == "pascoa" and not req.pascoa:
            continue
        out.append(e.get("nome", ""))
    if req.festas:
        out.extend(f.get("nome", "") for f in r.get("festas", []))
    # Preserve order and remove duplicates.
    return list(dict.fromkeys(x for x in out if x))


def _date_pair(r: dict, mode: str) -> str:
    if mode == "g":
        return f"G. {r['data_g']}"
    if mode == "m":
        return f"M. {r['data_m']}"
    return f"G. {r['data_g']}  <->  M. {r['data_m']}"


def _table(rows: list[list], widths=None, repeat_rows=1, font_size=7.4):
    table = LongTable(rows, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#51465F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DED9E2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF9FB")]),
    ]))
    return table


def _resolve_date(valor: str, referencia: str):
    if not valor.strip():
        raise ValueError("Informe a data.")
    r = buscar_por_g(valor) if referencia == "g" else buscar_por_m(valor)
    if not r:
        raise ValueError("A data informada não foi encontrada no registro oficial.")
    return r


def _header(story, title: str, subtitle: str, st):
    story.append(Paragraph(title, st["title"]))
    story.append(Paragraph(subtitle, st["subtitle"]))


def _rows_calendar(registros: Iterable[dict], req: ReportRequest, st):
    if req.calendario == "g":
        rows = [["Data G", "Dia da semana", "Marcadores"]]
        for r in registros:
            rows.append([
                Paragraph(r["data_g"], st["small"]),
                r["dia_semana"],
                Paragraph(", ".join(_event_names(r, req)) or "-", st["small"]),
            ])
        return rows, [42*mm, 30*mm, 105*mm]
    if req.calendario == "m":
        rows = [["Data M", "Dia da semana", "Marcadores"]]
        for r in registros:
            rows.append([
                Paragraph(r["data_m"], st["small"]),
                r["dia_semana"],
                Paragraph(", ".join(_event_names(r, req)) or "-", st["small"]),
            ])
        return rows, [42*mm, 30*mm, 105*mm]
    rows = [["Calendário G", "Calendário M", "Dia da semana", "Marcadores"]]
    for r in registros:
        rows.append([
            Paragraph(r["data_g"], st["small"]),
            Paragraph(r["data_m"], st["small"]),
            r["dia_semana"],
            Paragraph(", ".join(_event_names(r, req)) or "-", st["small"]),
        ])
    return rows, [36*mm, 36*mm, 25*mm, 80*mm]


def _build_month(req: ReportRequest, story, st):
    if req.ano is None or req.mes is None:
        raise ValueError("Informe ano e mês.")
    if req.referencia == "m":
        regs = listar_mes_m(req.mes, req.ano)
        month_name = MESES_M.get(req.mes, f"Mês {req.mes}")
        label = f"{month_name} - ano M {req.ano}"
    else:
        regs = listar_mes_g(req.mes, req.ano)
        month_name = MESES_G.get(req.mes, f"Mês {req.mes}")
        label = f"{month_name} - ano G {req.ano}"
    if not regs:
        raise ValueError("O período informado não foi encontrado na base oficial.")
    _header(story, "Relatório Mensal do Calendário", label, st)
    rows, widths = _rows_calendar(regs, req, st)
    story.append(_table(rows, widths=widths))


def _build_year(req: ReportRequest, story, st):
    if req.ano is None:
        raise ValueError("Informe o ano.")
    regs = listar_ano(req.referencia, req.ano, enriquecer=True)
    if not regs:
        raise ValueError("O ano informado não foi encontrado na base oficial.")
    label = "Calendário M" if req.referencia == "m" else "Calendário G"
    _header(story, "Relatório Anual", f"{label} - ano {req.ano}", st)
    key = "m_mes" if req.referencia == "m" else "g_mes"
    month_names = MESES_M if req.referencia == "m" else MESES_G
    current = None
    section: list[dict] = []
    for r in regs + [None]:
        mes = r[key] if r else None
        if current is None:
            current = mes
        if mes != current:
            story.append(Paragraph(month_names.get(current, f"Mês {current}"), st["h2"]))
            rows, widths = _rows_calendar(section, req, st)
            story.append(_table(rows, widths=widths, font_size=7.0))
            story.append(Spacer(1, 5*mm))
            section = []
            current = mes
        if r:
            section.append(r)


def _build_correspondence(req: ReportRequest, story, st):
    a = _resolve_date(req.inicio, req.referencia)
    b = _resolve_date(req.fim, req.referencia)
    regs = listar_intervalo_ids(a["id"], b["id"], limite=10000, enriquecer=False)
    _header(story, "Relatório de Correspondência G <-> M", f"{_date_pair(a, 'both')} até {_date_pair(b, 'both')}", st)
    rows = [["#", "Data G", "Data M", "Dia da semana"]]
    for r in regs:
        rows.append([str(r["id"]), r["data_g"], r["data_m"], r["dia_semana"]])
    story.append(_table(rows, widths=[22*mm, 50*mm, 50*mm, 40*mm], font_size=7.8))


def _build_event_report(req: ReportRequest, story, st, event_type: str, title: str):
    if req.inicio and req.fim:
        a = _resolve_date(req.inicio, req.referencia)
        b = _resolve_date(req.fim, req.referencia)
        id1, id2 = a["id"], b["id"]
        subtitle = f"{_date_pair(a, 'both')} até {_date_pair(b, 'both')}"
    elif req.ano is not None:
        regs_ano = listar_ano(req.referencia, req.ano, enriquecer=False)
        if not regs_ano:
            raise ValueError("O ano informado não foi encontrado na base oficial.")
        id1, id2 = regs_ano[0]["id"], regs_ano[-1]["id"]
        label = "M" if req.referencia == "m" else "G"
        subtitle = f"Ano {label} {req.ano}"
    else:
        raise ValueError("Informe um ano ou um intervalo para este relatório.")
    rows_db = listar_eventos_por_tipo(event_type, id1, id2, limite=20000)
    _header(story, title, subtitle, st)
    rows = [["Data G", "Data M", "Dia", "Evento"]]
    for r in rows_db:
        rows.append([r["data_g"], r["data_m"], r["dia_semana"], Paragraph(r["nome"], st["small"])])
    if len(rows) == 1:
        story.append(Paragraph("Nenhum registro foi encontrado para o período selecionado.", st["body"]))
    else:
        story.append(_table(rows, widths=[45*mm, 45*mm, 22*mm, 65*mm], font_size=7.6))


def _build_feasts(req: ReportRequest, story, st):
    _header(story, "Relatório de Festas Bíblicas", "Somente registros ATIVO do catálogo oficial", st)
    festas = listar_festas_ativas()
    rows = [["Mês M", "Dia(s)", "Festa", "Referência"]]
    for f in festas:
        if f["id"] == "PASCOA" and not req.pascoa:
            continue
        dias = str(f["dia_inicio"]) if f["dia_inicio"] == f["dia_fim"] else f"{f['dia_inicio']} a {f['dia_fim']}"
        rows.append([
            f"{f['mes']:02d} - {MESES_M.get(f['mes'], '')}",
            dias,
            Paragraph(f["nome"], st["small"]),
            Paragraph(f["referencia"] or "-", st["small"]),
        ])
    story.append(_table(rows, widths=[40*mm, 22*mm, 60*mm, 55*mm], font_size=7.5))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Observação: entradas com status AGUARDA_REGRA não são incluídas no relatório nem na interface.", st["small"]))


def _build_specific_date(req: ReportRequest, story, st):
    r = _resolve_date(req.data, req.referencia)
    _header(story, "Relatório de Data Específica", _date_pair(r, "both"), st)
    details = [
        ["Calendário G", r["data_g"]],
        ["Calendário M", r["data_m"]],
        ["Dia da semana", r["dia_semana"]],
    ]
    t = Table(details, colWidths=[45*mm, 105*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#EEEAF2")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#DED9E2")),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))
    events = _event_names(r, req)
    story.append(Paragraph("Marcadores e eventos", st["h2"]))
    if events:
        for name in events:
            story.append(Paragraph(f"• {name}", st["body"]))
    else:
        story.append(Paragraph("Nenhum marcador habilitado foi registrado para esta data.", st["body"]))


def _build_interval(req: ReportRequest, story, st):
    a = _resolve_date(req.inicio, req.referencia)
    b = _resolve_date(req.fim, req.referencia)
    regs = listar_intervalo_ids(a["id"], b["id"], limite=5000, enriquecer=True)
    _header(story, "Relatório de Intervalo Personalizado", f"{_date_pair(a, 'both')} até {_date_pair(b, 'both')}", st)
    rows, widths = _rows_calendar(regs, req, st)
    story.append(_table(rows, widths=widths, font_size=7.2))


def _build_audit(req: ReportRequest, story, st):
    stats = estatisticas()
    festas = listar_festas_ativas()
    _header(story, "Relatório Técnico de Auditoria", "Resumo operacional sem exposição de credenciais ou caminhos internos", st)
    rows = [
        ["Indicador", "Valor"],
        ["Registros G <-> M", f"{stats['total']:,}".replace(",", ".")],
        ["Limite Calendário G", f"{stats['limites']['g'][0]} a {stats['limites']['g'][1]}"],
        ["Limite Calendário M", f"{stats['limites']['m'][0]} a {stats['limites']['m'][1]}"],
        ["Festas bíblicas ATIVO", str(len(festas))],
        ["Política de fonte", "Registros oficiais do calendário"],
    ]
    story.append(_table(rows, widths=[70*mm, 100*mm], font_size=8.3))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Este relatório não mostra bucket, paths, tokens, secrets ou credenciais.", st["small"]))


def generate_pdf(req: ReportRequest) -> tuple[bytes, str]:
    if req.tipo not in REPORT_TYPES:
        raise ValueError("Tipo de relatório inválido.")
    if req.calendario not in {"both", "g", "m"}:
        raise ValueError("Modo de calendário inválido.")
    if req.referencia not in {"g", "m"}:
        raise ValueError("Calendário de referência inválido.")

    st = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16*mm,
        leftMargin=16*mm,
        topMargin=17*mm,
        bottomMargin=17*mm,
        title=REPORT_TYPES[req.tipo],
        author="Calendário Messiano",
        subject="Relatório gerado a partir dos registros oficiais do calendário",
    )
    story = []

    if req.tipo == "mensal":
        _build_month(req, story, st)
    elif req.tipo == "anual":
        _build_year(req, story, st)
    elif req.tipo == "correspondencia":
        _build_correspondence(req, story, st)
    elif req.tipo == "lua":
        _build_event_report(req, story, st, "lua", "Relatório de Fases da Lua")
    elif req.tipo == "estacoes":
        _build_event_report(req, story, st, "estacao", "Relatório de Estações do Ano")
    elif req.tipo == "festas":
        _build_feasts(req, story, st)
    elif req.tipo == "data":
        _build_specific_date(req, story, st)
    elif req.tipo == "intervalo":
        _build_interval(req, story, st)
    elif req.tipo == "auditoria":
        _build_audit(req, story, st)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    filename = f"calendario_messiano_{req.tipo}.pdf"
    return buffer.getvalue(), filename
