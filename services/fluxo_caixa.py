from __future__ import annotations

import io
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import and_, func, or_, select

from database.db import session_scope
from models.entities import (
    CentroCusto,
    CodigoAPLB,
    ContaFinanceira,
    Favorecido,
    FluxoProjetado,
    GrupoCodigoVinculo,
    GrupoDRE,
    Lancamento,
)
from services.auditoria import registrar_auditoria
from services.financeiro import STATUS_OFICIAIS, moeda, saldos
from services.tenancy import get_active_tesouraria_id, obter_tesouraria

CENARIOS = ("REALISTA", "PESSIMISTA", "OTIMISTA")
FREQUENCIAS = ("ÚNICA", "SEMANAL", "QUINZENAL", "MENSAL", "BIMESTRAL", "TRIMESTRAL", "SEMESTRAL", "ANUAL")
VISOES = ("DIA", "SEMANA", "MÊS", "TRIMESTRE", "SEMESTRE", "ANO")


def saldo_projetado(saldo_inicial: Decimal, entradas: Decimal, saidas: Decimal) -> Decimal:
    return saldo_inicial + entradas - saidas


def _fmt_data(dt) -> str:
    if not dt:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%d/%m/%Y")
    return str(dt)


def _fmt_brl(v) -> str:
    s = f"{Decimal(str(v or 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _periodo_label(dt: date, visao: str) -> str:
    visao = (visao or "MÊS").upper()
    if visao == "DIA":
        return dt.strftime("%d/%m/%Y")
    if visao == "SEMANA":
        ini = dt - timedelta(days=dt.weekday())
        fim = ini + timedelta(days=6)
        return f"{ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
    if visao == "MÊS":
        return f"{dt.month:02d}/{dt.year}"
    if visao == "TRIMESTRE":
        return f"{((dt.month-1)//3)+1}º tri/{dt.year}"
    if visao == "SEMESTRE":
        return f"{1 if dt.month <= 6 else 2}º sem/{dt.year}"
    return str(dt.year)


def _periodo_ordem(dt: date, visao: str):
    visao = (visao or "MÊS").upper()
    if visao == "DIA":
        return dt
    if visao == "SEMANA":
        return dt - timedelta(days=dt.weekday())
    if visao == "MÊS":
        return date(dt.year, dt.month, 1)
    if visao == "TRIMESTRE":
        return date(dt.year, (((dt.month-1)//3)*3)+1, 1)
    if visao == "SEMESTRE":
        return date(dt.year, 1 if dt.month <= 6 else 7, 1)
    return date(dt.year, 1, 1)


def _dre_join():
    return (
        GrupoCodigoVinculo,
        GrupoDRE,
        and_(
            GrupoCodigoVinculo.codigo_aplb_id == CodigoAPLB.id,
            GrupoCodigoVinculo.ativo.is_(True),
        ),
    )


def listar_realizado(
    inicio: date,
    fim: date,
    origem_bc: str | None = None,
    codigo_id: int | None = None,
    grupo_dre_id: int | None = None,
    centro_custo_id: int | None = None,
    favorecido_id: int | None = None,
    natureza: str | None = None,
):
    """Lançamentos oficiais do fluxo realizado, sempre isolados pela tesouraria ativa."""
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        q = (
            select(Lancamento, CodigoAPLB, ContaFinanceira, CentroCusto, Favorecido, GrupoDRE)
            .outerjoin(CodigoAPLB, CodigoAPLB.id == Lancamento.codigo_aplb_id)
            .outerjoin(ContaFinanceira, ContaFinanceira.id == Lancamento.conta_financeira_id)
            .outerjoin(CentroCusto, CentroCusto.id == Lancamento.centro_custo_id)
            .outerjoin(Favorecido, Favorecido.id == Lancamento.favorecido_id)
            .outerjoin(
                GrupoCodigoVinculo,
                and_(
                    GrupoCodigoVinculo.codigo_aplb_id == Lancamento.codigo_aplb_id,
                    GrupoCodigoVinculo.ativo.is_(True),
                ),
            )
            .outerjoin(GrupoDRE, GrupoDRE.id == GrupoCodigoVinculo.grupo_dre_id)
            .where(
                Lancamento.tesouraria_id == tid,
                Lancamento.data_movimento >= inicio,
                Lancamento.data_movimento <= fim,
                Lancamento.status.in_(STATUS_OFICIAIS),
            )
        )
        if origem_bc:
            q = q.where(Lancamento.origem_bc == origem_bc)
        if codigo_id:
            q = q.where(Lancamento.codigo_aplb_id == int(codigo_id))
        if grupo_dre_id:
            q = q.where(GrupoDRE.id == int(grupo_dre_id))
        if centro_custo_id:
            q = q.where(Lancamento.centro_custo_id == int(centro_custo_id))
        if favorecido_id:
            q = q.where(Lancamento.favorecido_id == int(favorecido_id))
        if natureza:
            q = q.where(Lancamento.natureza == natureza)
        rows = s.execute(q.order_by(Lancamento.data_movimento, Lancamento.id)).all()
        out = []
        for l, c, conta, cc, fav, dre in rows:
            nome_fav = fav.nome if fav else (l.favorecido or "")
            out.append({
                "id": l.id,
                "data": l.data_movimento,
                "data_formatada": _fmt_data(l.data_movimento),
                "natureza": l.natureza,
                "valor": float(l.valor),
                "efeito": float(l.valor) if l.natureza == "ENTRADA" else -float(l.valor),
                "origem_bc": l.origem_bc,
                "origem": "Banco" if l.origem_bc == "B" else "Caixa" if l.origem_bc == "C" else l.origem_bc,
                "conta": conta.nome if conta else "",
                "codigo_id": c.id if c else None,
                "codigo": c.codigo if c else "",
                "codigo_descricao": c.descricao if c else "",
                "dre_id": dre.id if dre else None,
                "dre": f"{dre.codigo_grupo} - {dre.nome}" if dre else "",
                "centro_custo_id": cc.id if cc else None,
                "centro_custo": f"{cc.codigo} - {cc.nome}" if cc else "",
                "favorecido_id": fav.id if fav else None,
                "favorecido": nome_fav,
                "favorecido_tipo": fav.tipo if fav else "",
                "descricao": l.especificacao,
                "status": l.status,
            })
        return out


def agregar_realizado(rows: list[dict], visao: str, saldo_inicial: float = 0.0):
    grupos = {}
    for r in rows:
        dt = r["data"]
        chave = _periodo_ordem(dt, visao)
        g = grupos.setdefault(chave, {"ordem": chave, "período": _periodo_label(dt, visao), "entradas": 0.0, "saídas": 0.0})
        if r["natureza"] == "ENTRADA":
            g["entradas"] += float(r["valor"])
        else:
            g["saídas"] += float(r["valor"])
    saldo = float(saldo_inicial or 0)
    saida = []
    for chave in sorted(grupos):
        g = grupos[chave]
        g["resultado"] = g["entradas"] - g["saídas"]
        saldo += g["resultado"]
        g["saldo"] = saldo
        saida.append(g)
    return saida


def saldo_abertura(inicio: date, origem_bc: str | None = None) -> float:
    v = saldos(fim=inicio - timedelta(days=1))
    if origem_bc == "B":
        return float(v.get("B", 0) or 0)
    if origem_bc == "C":
        return float(v.get("C", 0) or 0)
    return float(v.get("GERAL", 0) or 0)


def resumo_realizado(rows: list[dict], saldo_inicial: float = 0.0):
    ent = sum(float(r["valor"]) for r in rows if r["natureza"] == "ENTRADA")
    sai = sum(float(r["valor"]) for r in rows if r["natureza"] == "SAIDA")
    return {"entradas": ent, "saidas": sai, "resultado": ent - sai, "saldo_inicial": float(saldo_inicial), "saldo_final": float(saldo_inicial) + ent - sai}


def _add_months(dt: date, months: int) -> date:
    total = dt.year * 12 + (dt.month - 1) + months
    y, m0 = divmod(total, 12)
    m = m0 + 1
    return date(y, m, min(dt.day, monthrange(y, m)[1]))


def _next_date(dt: date, frequencia: str) -> date | None:
    f = (frequencia or "ÚNICA").upper()
    if f == "SEMANAL":
        return dt + timedelta(days=7)
    if f == "QUINZENAL":
        return dt + timedelta(days=15)
    if f == "MENSAL":
        return _add_months(dt, 1)
    if f == "BIMESTRAL":
        return _add_months(dt, 2)
    if f == "TRIMESTRAL":
        return _add_months(dt, 3)
    if f == "SEMESTRAL":
        return _add_months(dt, 6)
    if f == "ANUAL":
        return _add_months(dt, 12)
    return None


def criar_previsao(
    data_prevista,
    natureza,
    valor,
    descricao,
    codigo_id=None,
    favorecido=None,
    recorrencia=None,
    probabilidade=1.0,
    status="PREVISTO",
    usuario_id=None,
    *,
    conta_id=None,
    centro_custo_id=None,
    favorecido_id=None,
    cenario="REALISTA",
    frequencia="ÚNICA",
    recorrente=False,
    data_fim_recorrencia=None,
):
    tid = get_active_tesouraria_id()
    cenario = (cenario or "REALISTA").upper()
    if cenario not in CENARIOS:
        raise ValueError("Cenário inválido.")
    frequencia = (frequencia or recorrencia or "ÚNICA").upper()
    if frequencia not in FREQUENCIAS:
        raise ValueError("Frequência inválida.")
    if not recorrente:
        frequencia = "ÚNICA"
        data_fim_recorrencia = None
    elif not data_fim_recorrencia or data_fim_recorrencia < data_prevista:
        raise ValueError("Informe uma data final de recorrência igual ou posterior à primeira previsão.")
    with session_scope() as s:
        if conta_id:
            conta = s.get(ContaFinanceira, int(conta_id))
            if not conta or conta.tesouraria_id != tid:
                raise ValueError("Conta financeira não pertence à unidade ativa.")
        if centro_custo_id:
            cc = s.get(CentroCusto, int(centro_custo_id))
            if not cc or cc.tesouraria_id != tid:
                raise ValueError("Centro de custo não pertence à unidade ativa.")
        if favorecido_id:
            fv = s.get(Favorecido, int(favorecido_id))
            if not fv or fv.tesouraria_id != tid:
                raise ValueError("Favorecido não pertence à unidade ativa.")
            favorecido = fv.nome
        x = FluxoProjetado(
            tesouraria_id=tid,
            data_prevista=data_prevista,
            natureza=natureza,
            valor=moeda(valor),
            codigo_aplb_id=codigo_id,
            descricao=(descricao or "").strip(),
            favorecido=(favorecido or "").strip() or None,
            recorrencia=frequencia,
            probabilidade=float(probabilidade),
            status=status,
            conta_financeira_id=conta_id,
            centro_custo_id=centro_custo_id,
            favorecido_id=favorecido_id,
            cenario=cenario,
            frequencia=frequencia,
            recorrente=bool(recorrente),
            data_fim_recorrencia=data_fim_recorrencia,
        )
        s.add(x)
        s.flush()
        rid = x.id
    registrar_auditoria(usuario_id, "CRIAR_PREVISAO", "fluxo_projetado", rid, novo={
        "data": data_prevista, "natureza": natureza, "valor": str(valor), "cenario": cenario,
        "frequencia": frequencia, "recorrente": bool(recorrente), "fim": data_fim_recorrencia,
    })
    return rid


def _expandir_previsao(obj: FluxoProjetado, inicio: date | None, fim: date | None):
    atual = obj.data_prevista
    limite = obj.data_fim_recorrencia if bool(obj.recorrente) else obj.data_prevista
    limite = min(limite, fim) if limite and fim else limite
    if fim is None and bool(obj.recorrente) and limite is None:
        limite = atual
    datas = []
    while atual and (limite is None or atual <= limite):
        if (inicio is None or atual >= inicio) and (fim is None or atual <= fim):
            datas.append(atual)
        prox = _next_date(atual, obj.frequencia or obj.recorrencia or "ÚNICA") if bool(obj.recorrente) else None
        if not prox or prox <= atual:
            break
        atual = prox
    return datas


def listar_projetado(
    inicio: date | None = None,
    fim: date | None = None,
    cenario: str | None = None,
    natureza: str | None = None,
    codigo_id: int | None = None,
    grupo_dre_id: int | None = None,
    centro_custo_id: int | None = None,
    favorecido_id: int | None = None,
    conta_id: int | None = None,
):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        q = (
            select(FluxoProjetado, CodigoAPLB, ContaFinanceira, CentroCusto, Favorecido, GrupoDRE)
            .outerjoin(CodigoAPLB, CodigoAPLB.id == FluxoProjetado.codigo_aplb_id)
            .outerjoin(ContaFinanceira, ContaFinanceira.id == FluxoProjetado.conta_financeira_id)
            .outerjoin(CentroCusto, CentroCusto.id == FluxoProjetado.centro_custo_id)
            .outerjoin(Favorecido, Favorecido.id == FluxoProjetado.favorecido_id)
            .outerjoin(
                GrupoCodigoVinculo,
                and_(GrupoCodigoVinculo.codigo_aplb_id == FluxoProjetado.codigo_aplb_id, GrupoCodigoVinculo.ativo.is_(True)),
            )
            .outerjoin(GrupoDRE, GrupoDRE.id == GrupoCodigoVinculo.grupo_dre_id)
            .where(FluxoProjetado.tesouraria_id == tid)
        )
        if fim:
            q = q.where(FluxoProjetado.data_prevista <= fim)
        if cenario:
            q = q.where(FluxoProjetado.cenario == cenario)
        if natureza:
            q = q.where(FluxoProjetado.natureza == natureza)
        if codigo_id:
            q = q.where(FluxoProjetado.codigo_aplb_id == int(codigo_id))
        if grupo_dre_id:
            q = q.where(GrupoDRE.id == int(grupo_dre_id))
        if centro_custo_id:
            q = q.where(FluxoProjetado.centro_custo_id == int(centro_custo_id))
        if favorecido_id:
            q = q.where(FluxoProjetado.favorecido_id == int(favorecido_id))
        if conta_id:
            q = q.where(FluxoProjetado.conta_financeira_id == int(conta_id))
        dbrows = s.execute(q.order_by(FluxoProjetado.data_prevista, FluxoProjetado.id)).all()
        out = []
        for x, c, conta, cc, fav, dre in dbrows:
            for dt in _expandir_previsao(x, inicio, fim):
                out.append({
                    "id": x.id,
                    "data": dt,
                    "data_formatada": _fmt_data(dt),
                    "natureza": x.natureza,
                    "valor": float(x.valor),
                    "valor_ponderado": float(x.valor) * float(x.probabilidade or 1),
                    "codigo_id": c.id if c else None,
                    "codigo": c.codigo if c else "",
                    "dre_id": dre.id if dre else None,
                    "dre": f"{dre.codigo_grupo} - {dre.nome}" if dre else "",
                    "centro_custo_id": cc.id if cc else None,
                    "centro_custo": f"{cc.codigo} - {cc.nome}" if cc else "",
                    "favorecido_id": fav.id if fav else None,
                    "favorecido": fav.nome if fav else (x.favorecido or ""),
                    "favorecido_tipo": fav.tipo if fav else "",
                    "conta_id": conta.id if conta else None,
                    "conta": conta.nome if conta else "",
                    "origem": conta.tipo.title() if conta else "",
                    "descricao": x.descricao,
                    "probabilidade": float(x.probabilidade or 1),
                    "status": x.status,
                    "cenario": x.cenario or "REALISTA",
                    "frequencia": x.frequencia or x.recorrencia or "ÚNICA",
                    "recorrente": bool(x.recorrente),
                    "fim_recorrencia": x.data_fim_recorrencia,
                })
        out.sort(key=lambda r: (r["data"], r["id"]))
        return out


def listar_fluxo_projetado(inicio=None, fim=None):
    """Compatibilidade com telas/testes antigos."""
    return listar_projetado(inicio, fim)


def resumo_projetado(rows: list[dict], saldo_inicial: float = 0.0):
    ent = sum(float(r["valor_ponderado"]) for r in rows if r["natureza"] == "ENTRADA")
    sai = sum(float(r["valor_ponderado"]) for r in rows if r["natureza"] == "SAIDA")
    return {"entradas": ent, "saidas": sai, "resultado": ent - sai, "saldo_inicial": float(saldo_inicial), "saldo_final": float(saldo_inicial) + ent - sai}


def agregar_projetado(rows: list[dict], visao: str, saldo_inicial: float = 0.0):
    grupos = {}
    for r in rows:
        dt = r["data"]
        chave = _periodo_ordem(dt, visao)
        g = grupos.setdefault(chave, {"ordem": chave, "período": _periodo_label(dt, visao), "entradas": 0.0, "saídas": 0.0})
        valor = float(r["valor_ponderado"])
        if r["natureza"] == "ENTRADA":
            g["entradas"] += valor
        else:
            g["saídas"] += valor
    saldo = float(saldo_inicial or 0)
    saida = []
    for chave in sorted(grupos):
        g = grupos[chave]
        g["resultado"] = g["entradas"] - g["saídas"]
        saldo += g["resultado"]
        g["saldo"] = saldo
        saida.append(g)
    return saida


def comparar_projetado_realizado(real_rows: list[dict], proj_rows: list[dict], visao: str):
    real = {r["período"]: r for r in agregar_realizado(real_rows, visao, 0)}
    proj = {r["período"]: r for r in agregar_projetado(proj_rows, visao, 0)}
    chaves_ordem = {}
    for r in real_rows:
        chaves_ordem[_periodo_label(r["data"], visao)] = _periodo_ordem(r["data"], visao)
    for r in proj_rows:
        chaves_ordem[_periodo_label(r["data"], visao)] = _periodo_ordem(r["data"], visao)
    out = []
    for per in sorted(chaves_ordem, key=lambda p: chaves_ordem[p]):
        rr, pp = real.get(per, {}), proj.get(per, {})
        out.append({
            "período": per,
            "realizado_entradas": rr.get("entradas", 0.0),
            "projetado_entradas": pp.get("entradas", 0.0),
            "realizado_saídas": rr.get("saídas", 0.0),
            "projetado_saídas": pp.get("saídas", 0.0),
            "realizado_resultado": rr.get("resultado", 0.0),
            "projetado_resultado": pp.get("resultado", 0.0),
            "desvio_resultado": rr.get("resultado", 0.0) - pp.get("resultado", 0.0),
        })
    return out


def detectar_alertas_deficit(agregado: list[dict]):
    alertas = []
    for r in agregado:
        if float(r.get("saldo", 0)) < 0:
            alertas.append({"período": r["período"], "saldo": float(r["saldo"]), "tipo": "DÉFICIT"})
        elif float(r.get("saídas", 0)) > float(r.get("entradas", 0)) and float(r.get("saldo", 0)) <= max(float(r.get("saídas", 0)) * 0.10, 0):
            alertas.append({"período": r["período"], "saldo": float(r["saldo"]), "tipo": "SALDO INSUFICIENTE"})
    return alertas


def excel_bytes(rows: list[dict], sheet="Fluxo") -> bytes:
    df = pd.DataFrame(rows)
    # Datas sempre em padrão brasileiro na exportação visual.
    for col in list(df.columns):
        if "data" in str(col).lower():
            df[col] = df[col].apply(lambda x: _fmt_data(x) if x not in (None, "") else "")
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet[:31])
        ws = writer.book[sheet[:31]]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max((len(str(c.value or "")) for c in col), default=8) + 2, 45)
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
    return bio.getvalue()


def pdf_bytes(rows: list[dict], titulo: str, colunas: list[tuple[str, str]] | None = None) -> bytes:
    bio = io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=landscape(A4), rightMargin=8*mm, leftMargin=8*mm, topMargin=8*mm, bottomMargin=8*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("flux_title", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=13, leading=15)
    tenant = obter_tesouraria(get_active_tesouraria_id()) or {}
    story = [Paragraph(titulo, title), Paragraph(
        f"{tenant.get('nome','TESOURARIA APLB')} · {tenant.get('cidade','')}/{tenant.get('uf','')} · gerado em {date.today().strftime('%d/%m/%Y')}",
        styles["Normal"]), Spacer(1, 4*mm)]
    if colunas is None:
        colunas = [("data_formatada", "Data"), ("natureza", "Tipo"), ("origem", "Banco/Caixa"), ("codigo", "Código"), ("dre", "DRE"), ("centro_custo", "Centro de custo"), ("favorecido", "Favorecido"), ("valor", "Valor")]
    data = [[label for _, label in colunas]]
    for r in rows:
        linha = []
        for key, _ in colunas:
            v = r.get(key, "")
            if key in ("valor", "valor_ponderado", "entradas", "saídas", "resultado", "saldo"):
                v = _fmt_brl(v)
            elif isinstance(v, date):
                v = _fmt_data(v)
            linha.append(Paragraph(str(v or ""), styles["BodyText"]))
        data.append(linha)
    if len(data) == 1:
        data.append([Paragraph("Nenhum registro encontrado.", styles["BodyText"])] + [""] * (len(colunas)-1))
    largura = 280*mm / max(len(colunas), 1)
    table = Table(data, repeatRows=1, colWidths=[largura] * len(colunas))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(table)
    doc.build(story)
    return bio.getvalue()
