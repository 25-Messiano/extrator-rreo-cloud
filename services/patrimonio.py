from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from sqlalchemy import select, func

from database.db import session_scope
from models.entities import Patrimonio, PatrimonioMovimento, PatrimonioAnexo, Lancamento, CodigoAPLB, Favorecido
from services.auditoria import registrar_auditoria
from services.financeiro import salvar_patrimonio
from services.tenancy import get_active_tesouraria_id, obter_tesouraria

SITUACOES = ("ATIVO", "INATIVO", "EM_MANUTENCAO", "OBSOLETO", "TRANSFERIDO", "BAIXADO")
ESTADOS_CONSERVACAO = ("EXCELENTE", "BOM", "REGULAR", "RUIM", "INSERVIVEL")
MAX_ANEXO_BYTES = 10 * 1024 * 1024


def listar_aquisicoes_patrimoniais_pendentes(limit: int = 500):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        q = (
            select(Lancamento, CodigoAPLB)
            .join(CodigoAPLB, CodigoAPLB.id == Lancamento.codigo_aplb_id)
            .outerjoin(Patrimonio, Patrimonio.lancamento_origem_id == Lancamento.id)
            .where(
                Lancamento.tesouraria_id == tid,
                CodigoAPLB.tesouraria_id == tid,
                CodigoAPLB.gera_patrimonio.is_(True),
                Lancamento.natureza == "SAIDA",
                Lancamento.status.in_(("APROVADO", "CONCILIADO", "FECHADO")),
                Patrimonio.id.is_(None),
            )
            .order_by(Lancamento.data_movimento.desc(), Lancamento.id.desc())
            .limit(limit)
        )
        rows = s.execute(q).all()
        return [{
            "lancamento_id": l.id, "data": l.data_movimento, "codigo": c.codigo,
            "codigo_descricao": c.descricao, "descricao": l.especificacao, "valor": float(l.valor),
            "fornecedor": l.favorecido or "", "fornecedor_id": l.favorecido_id,
            "documento": l.documento or "", "origem": l.origem_lancamento or "", "status": l.status,
        } for l, c in rows]


def cadastrar_de_lancamento(lancamento_id: int, numero: str | None = None, descricao: str | None = None,
                             categoria: str | None = None, local_uso: str | None = None,
                             responsavel: str | None = None, situacao: str = "ATIVO", usuario_id=None,
                             estado_conservacao: str | None = None, vida_util_anos: int | None = None):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        l = s.get(Lancamento, int(lancamento_id))
        if not l or l.tesouraria_id != tid:
            raise ValueError("Lançamento não encontrado nesta tesouraria.")
        c = s.get(CodigoAPLB, l.codigo_aplb_id) if l.codigo_aplb_id else None
        if not c or c.tesouraria_id != tid or not c.gera_patrimonio:
            raise ValueError("O código deste lançamento não está marcado como gerador de patrimônio.")
        if l.natureza != "SAIDA":
            raise ValueError("Somente aquisições registradas como SAÍDA podem originar patrimônio.")
        if s.scalar(select(Patrimonio.id).where(Patrimonio.lancamento_origem_id == l.id)):
            raise ValueError("Este lançamento já está vinculado a um bem patrimonial.")
        dados = {
            "descricao": (descricao or l.especificacao or c.descricao or "Bem patrimonial").strip(),
            "numero": (numero or "").strip() or None,
            "categoria": (categoria or c.descricao or "").strip() or None,
            "data_aquisicao": l.data_movimento, "valor": l.valor,
            "fornecedor": l.favorecido, "fornecedor_id": l.favorecido_id, "nota_fiscal": l.documento,
            "local_uso": (local_uso or "").strip() or None, "responsavel": (responsavel or "").strip() or None,
            "situacao": situacao if situacao in SITUACOES else "ATIVO",
            "estado_conservacao": estado_conservacao, "vida_util_anos": vida_util_anos,
            "lancamento_id": l.id,
        }
    rid = salvar_patrimonio(usuario_id=usuario_id, **dados)
    registrar_auditoria(usuario_id, "VINCULAR_LANCAMENTO_PATRIMONIO", "patrimonio", rid,
                        novo={"lancamento_id": int(lancamento_id)})
    return rid


def listar_para_relatorio(modo: str = "EM_USO"):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        anexos = dict(s.execute(select(PatrimonioAnexo.patrimonio_id, func.count(PatrimonioAnexo.id)).where(
            PatrimonioAnexo.tesouraria_id == tid, PatrimonioAnexo.ativo.is_(True)
        ).group_by(PatrimonioAnexo.patrimonio_id)).all())
        q = select(Patrimonio).where(Patrimonio.tesouraria_id == tid)
        if modo == "EM_USO":
            q = q.where(Patrimonio.situacao.in_(("ATIVO", "EM_MANUTENCAO")))
        elif modo == "ATIVOS": q = q.where(Patrimonio.situacao == "ATIVO")
        elif modo == "INATIVOS": q = q.where(Patrimonio.situacao == "INATIVO")
        elif modo == "OBSOLETOS": q = q.where(Patrimonio.situacao == "OBSOLETO")
        elif modo == "BAIXADOS": q = q.where(Patrimonio.situacao == "BAIXADO")
        elif modo == "TRANSFERIDOS": q = q.where(Patrimonio.situacao == "TRANSFERIDO")
        elif modo == "MANUTENCAO": q = q.where(Patrimonio.situacao == "EM_MANUTENCAO")
        rows = s.scalars(q.order_by(Patrimonio.descricao, Patrimonio.numero_patrimonial)).all()
        return [{
            "Número": p.numero_patrimonial or "", "Descrição": p.descricao, "Categoria": p.categoria or "",
            "Aquisição": p.data_aquisicao, "Valor (R$)": float(p.valor or 0), "Fornecedor": p.fornecedor or "",
            "Nota fiscal": p.nota_fiscal or "", "Local": p.local_uso or "", "Responsável": p.responsavel or "",
            "Conservação": p.estado_conservacao or "", "Vida útil (anos)": p.vida_util_anos or "",
            "Situação": p.situacao, "Anexos": int(anexos.get(p.id, 0)), "Lançamento origem": p.lancamento_origem_id or "",
        } for p in rows]


def adicionar_anexo(patrimonio_id: int, nome_arquivo: str, conteudo: bytes, mime_type: str | None = None,
                     descricao: str | None = None, usuario_id=None) -> int:
    tid = get_active_tesouraria_id()
    conteudo = bytes(conteudo or b"")
    if not conteudo: raise ValueError("O arquivo está vazio.")
    if len(conteudo) > MAX_ANEXO_BYTES: raise ValueError("Cada anexo pode ter no máximo 10 MB.")
    with session_scope() as s:
        p = s.get(Patrimonio, int(patrimonio_id))
        if not p or p.tesouraria_id != tid: raise ValueError("Bem patrimonial não encontrado nesta filial.")
        a = PatrimonioAnexo(tesouraria_id=tid, patrimonio_id=p.id, nome_arquivo=(nome_arquivo or "anexo").strip(),
                            mime_type=(mime_type or "application/octet-stream")[:120], tamanho_bytes=len(conteudo),
                            conteudo=conteudo, descricao=(descricao or "").strip() or None, ativo=True,
                            criado_por=usuario_id, criado_em=datetime.utcnow())
        s.add(a); s.flush(); rid=a.id
    registrar_auditoria(usuario_id, "ANEXAR_DOCUMENTO_PATRIMONIO", "patrimonio_anexos", rid,
                        novo={"patrimonio_id": patrimonio_id, "nome_arquivo": nome_arquivo, "tamanho_bytes": len(conteudo)})
    return rid


def listar_anexos(patrimonio_id: int):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        q = select(PatrimonioAnexo).join(Patrimonio, Patrimonio.id==PatrimonioAnexo.patrimonio_id).where(
            Patrimonio.id==int(patrimonio_id), Patrimonio.tesouraria_id==tid, PatrimonioAnexo.tesouraria_id==tid,
            PatrimonioAnexo.ativo.is_(True)).order_by(PatrimonioAnexo.criado_em.desc())
        return [{"id":a.id,"nome":a.nome_arquivo,"tipo":a.mime_type or "","tamanho":a.tamanho_bytes,
                 "descricao":a.descricao or "","criado_em":a.criado_em} for a in s.scalars(q).all()]


def obter_anexo(anexo_id: int):
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        a=s.get(PatrimonioAnexo,int(anexo_id))
        if not a or a.tesouraria_id != tid or not a.ativo: raise ValueError("Anexo não encontrado nesta filial.")
        p=s.get(Patrimonio,a.patrimonio_id)
        if not p or p.tesouraria_id != tid: raise ValueError("Anexo não pertence a esta filial.")
        return {"nome":a.nome_arquivo,"tipo":a.mime_type or "application/octet-stream","conteudo":bytes(a.conteudo)}


def arquivar_anexo(anexo_id: int, usuario_id=None):
    tid=get_active_tesouraria_id()
    with session_scope() as s:
        a=s.get(PatrimonioAnexo,int(anexo_id))
        if not a or a.tesouraria_id != tid: raise ValueError("Anexo não encontrado nesta filial.")
        a.ativo=False; a.removido_em=datetime.utcnow(); pid=a.patrimonio_id; nome=a.nome_arquivo
    registrar_auditoria(usuario_id,"ARQUIVAR_ANEXO_PATRIMONIO","patrimonio_anexos",anexo_id,
                        novo={"patrimonio_id":pid,"nome_arquivo":nome,"ativo":False})


def listar_competencias_movimentacao():
    tid = get_active_tesouraria_id(); comps=set()
    with session_scope() as s:
        aquis=s.scalars(select(Patrimonio.data_aquisicao).where(Patrimonio.tesouraria_id==tid,Patrimonio.data_aquisicao.is_not(None))).all()
        movs=s.scalars(select(PatrimonioMovimento.data_movimento).join(Patrimonio,Patrimonio.id==PatrimonioMovimento.patrimonio_id).where(Patrimonio.tesouraria_id==tid)).all()
    for dt in list(aquis)+list(movs):
        if dt: comps.add(f"{dt.year:04d}-{dt.month:02d}")
    return sorted(comps, reverse=True)


def listar_movimentacoes_competencia(ano: int, mes: int | None = None, tipo: str | None = None):
    tid=get_active_tesouraria_id(); inicio=date(int(ano),int(mes or 1),1)
    fim=date(int(ano)+1,1,1) if not mes or int(mes)==12 else date(int(ano),int(mes)+1,1)
    if not mes: fim=date(int(ano)+1,1,1)
    rows=[]
    with session_scope() as s:
        bens=s.scalars(select(Patrimonio).where(Patrimonio.tesouraria_id==tid,Patrimonio.data_aquisicao>=inicio,Patrimonio.data_aquisicao<fim)).all()
        if not tipo or tipo=="AQUISICAO":
            for p in bens:
                rows.append({"Data":p.data_aquisicao,"Competência":f"{p.data_aquisicao.month:02d}/{p.data_aquisicao.year:04d}","Tipo":"AQUISICAO",
                    "Número":p.numero_patrimonial or "","Descrição":p.descricao,"Situação anterior":"","Situação nova":"INICIAL",
                    "Local anterior":"","Local novo":p.local_uso or "","Responsável anterior":"","Responsável novo":p.responsavel or "",
                    "Valor (R$)":float(p.valor or 0),"Observação":"Cadastro/aquisição patrimonial","Patrimônio ID":p.id})
        q=select(PatrimonioMovimento,Patrimonio).join(Patrimonio,Patrimonio.id==PatrimonioMovimento.patrimonio_id).where(
            Patrimonio.tesouraria_id==tid,PatrimonioMovimento.data_movimento>=inicio,PatrimonioMovimento.data_movimento<fim)
        if tipo and tipo!="AQUISICAO": q=q.where(PatrimonioMovimento.tipo==tipo)
        movimentos=[] if tipo=="AQUISICAO" else s.execute(q).all()
        for m,p in movimentos:
            rows.append({"Data":m.data_movimento,"Competência":f"{m.data_movimento.month:02d}/{m.data_movimento.year:04d}","Tipo":m.tipo,
                "Número":p.numero_patrimonial or "","Descrição":p.descricao,"Situação anterior":m.situacao_anterior or "","Situação nova":m.situacao_nova or "",
                "Local anterior":m.local_anterior or "","Local novo":m.local_novo or "","Responsável anterior":m.responsavel_anterior or "",
                "Responsável novo":m.responsavel_novo or "","Valor (R$)":float(p.valor or 0),"Observação":m.observacao or "","Patrimônio ID":p.id})
    rows.sort(key=lambda r:(r["Data"] or date.min,r["Patrimônio ID"]), reverse=True); return rows


def resumo_movimentacao_competencia(ano:int,mes:int):
    rows=listar_movimentacoes_competencia(ano,mes); tipos={}
    for r in rows: tipos[r["Tipo"]]=tipos.get(r["Tipo"],0)+1
    return {"total":len(rows),"tipos":tipos,"rows":rows}


def _fmt_brl(v):
    ss=f"{Decimal(str(v or 0)):,.2f}".replace(",","X").replace(".",",").replace("X","."); return f"R$ {ss}"


def movimentacao_pdf_bytes(rows:list[dict],titulo:str)->bytes:
    bio=io.BytesIO(); doc=SimpleDocTemplate(bio,pagesize=landscape(A4),rightMargin=8*mm,leftMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm)
    styles=getSampleStyleSheet(); title=ParagraphStyle("mov_pat_title",parent=styles["Heading1"],alignment=TA_CENTER,fontSize=13,leading=15)
    tenant=obter_tesouraria(get_active_tesouraria_id()) or {}
    story=[Paragraph(titulo,title),Paragraph(f"{tenant.get('nome','TESOURARIA APLB')} · {tenant.get('cidade','')}/{tenant.get('uf','')} · gerado em {date.today().strftime('%d/%m/%Y')}",styles["Normal"]),Spacer(1,4*mm)]
    headers=["Data","Tipo","Número","Descrição","Sit. anterior","Sit. nova","Local novo","Valor"]; data=[headers]
    for r in rows:
        dt=r.get("Data"); data.append([dt.strftime("%d/%m/%Y") if hasattr(dt,"strftime") else str(dt or ""),str(r.get("Tipo","")),str(r.get("Número","")),Paragraph(str(r.get("Descrição","")),styles["BodyText"]),str(r.get("Situação anterior","")),str(r.get("Situação nova","")),Paragraph(str(r.get("Local novo","")),styles["BodyText"]),_fmt_brl(r.get("Valor (R$)",0))])
    if len(data)==1: data.append(["","","","Nenhuma movimentação encontrada.","","","",""])
    table=Table(data,repeatRows=1,colWidths=[22*mm,34*mm,24*mm,58*mm,30*mm,30*mm,52*mm,28*mm]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E5E7EB")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.2),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#CBD5E1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F8FAFC")])]))
    story.extend([table,Spacer(1,4*mm),Paragraph(f"Total de movimentações: {len(rows)}",styles["Normal"])]); doc.build(story); return bio.getvalue()


def relatorio_excel_bytes(rows:list[dict])->bytes:
    df=pd.DataFrame(rows)
    for col in df.columns:
        if "aquisi" in str(col).lower() or "data" in str(col).lower():
            df[col]=df[col].apply(lambda x:x.strftime("%d/%m/%Y") if hasattr(x,"strftime") else x)
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Patrimonio"); ws=writer.book["Patrimonio"]; ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
        for col in ws.columns:
            width=min(max((len(str(c.value or "")) for c in col),default=8)+2,45); ws.column_dimensions[col[0].column_letter].width=width
        for cell in ws[1]: cell.font=cell.font.copy(bold=True)
    return bio.getvalue()


def relatorio_pdf_bytes(rows:list[dict],titulo:str)->bytes:
    bio=io.BytesIO(); doc=SimpleDocTemplate(bio,pagesize=landscape(A3),rightMargin=8*mm,leftMargin=8*mm,topMargin=8*mm,bottomMargin=8*mm)
    styles=getSampleStyleSheet(); title=ParagraphStyle("pat_title",parent=styles["Heading1"],alignment=TA_CENTER,fontSize=14,leading=16)
    tenant=obter_tesouraria(get_active_tesouraria_id()) or {}
    story=[Paragraph(titulo,title),Paragraph(f"{tenant.get('nome','TESOURARIA APLB')} · {tenant.get('cidade','')}/{tenant.get('uf','')} · gerado em {date.today().strftime('%d/%m/%Y')}",styles["Normal"]),Spacer(1,5*mm)]
    headers=["Nº","Descrição","Categoria","Aquisição","Valor","Fornecedor","NF","Local","Responsável","Conservação","Vida útil","Situação","Anexos"]
    data=[headers]
    for r in rows:
        aq=r.get("Aquisição"); data.append([str(r.get("Número","")),Paragraph(str(r.get("Descrição","")),styles["BodyText"]),Paragraph(str(r.get("Categoria","")),styles["BodyText"]),aq.strftime("%d/%m/%Y") if hasattr(aq,"strftime") else str(aq or ""),_fmt_brl(r.get("Valor (R$)",0)),Paragraph(str(r.get("Fornecedor","")),styles["BodyText"]),str(r.get("Nota fiscal","")),Paragraph(str(r.get("Local","")),styles["BodyText"]),Paragraph(str(r.get("Responsável","")),styles["BodyText"]),str(r.get("Conservação","")),f"{r.get('Vida útil (anos)','')} ano(s)" if r.get('Vida útil (anos)') else "",str(r.get("Situação","")),str(r.get("Anexos",0))])
    if len(data)==1: data.append(["","Nenhum bem encontrado para este filtro.","","","","","","","","","","",""])
    widths=[18,52,34,24,27,42,22,38,38,28,22,25,16]; table=Table(data,repeatRows=1,colWidths=[w*mm for w in widths])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E5E7EB")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),6.5),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#CBD5E1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F8FAFC")]),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2)]))
    story.extend([table,Spacer(1,4*mm)]); total=sum(Decimal(str(r.get("Valor (R$)",0) or 0)) for r in rows); story.append(Paragraph(f"Total de bens: {len(rows)} · Valor total: {_fmt_brl(total)}",styles["Normal"])); doc.build(story); return bio.getvalue()
