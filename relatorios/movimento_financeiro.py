from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from calendar import monthrange

from sqlalchemy import select, and_, or_, func

from database.db import session_scope
from models.entities import Lancamento, CodigoAPLB, CargaInicialItem, SaldoInicial, ContaFinanceira
from services.tenancy import get_active_tesouraria_id, tenant_where
from services.financeiro import STATUS_OFICIAIS, saldos

ROOT = Path(__file__).resolve().parents[1]
MESES = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO",
    7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO",
}


def br_money(value: Decimal | float | int | None) -> str:
    if value is None:
        return "-"
    v = Decimal(str(value)).quantize(Decimal("0.01"))
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{s}" if v < 0 else s


def code_display(codigo: str | None) -> str:
    if not codigo:
        return ""
    c = str(codigo).strip()
    return c.zfill(4) if c.isdigit() and len(c) <= 4 else c


def _month_filter(ano: int, mes: int):
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, monthrange(ano, mes)[1])
    comp = f"{ano:04d}-{mes:02d}"
    return inicio, fim, or_(
        Lancamento.competencia == comp,
        and_(Lancamento.competencia.is_(None), Lancamento.data_movimento >= inicio, Lancamento.data_movimento <= fim),
    )


def movimento_mes(ano: int, mes: int) -> dict:
    inicio, fim, filtro = _month_filter(ano, mes)
    with session_scope() as s:
        q = (
            select(Lancamento, CodigoAPLB, CargaInicialItem)
            .outerjoin(CodigoAPLB, CodigoAPLB.id == Lancamento.codigo_aplb_id)
            .outerjoin(CargaInicialItem, CargaInicialItem.lancamento_id == Lancamento.id)
            .where(filtro, Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))
        )
        result = s.execute(q).all()

    # O modelo histórico apresenta todos os movimentos de Banco antes dos de Caixa.
    # Para a carga original, a sequência do PDF tem prioridade absoluta.
    def sort_key(item):
        l, _c, ci = item
        # V19: regra visual oficial — Banco inteiro primeiro e Caixa depois.
        # Dentro de cada bloco, preserva a sequência original do PDF quando existir.
        bc_ord = 0 if l.origem_bc == "B" else 1
        if ci is not None:
            return (bc_ord, 0, ci.seq_origem)
        return (bc_ord, 1, l.data_movimento, l.id)

    result.sort(key=sort_key)
    saldo_ant = saldos(fim=date.fromordinal(inicio.toordinal() - 1))
    # SaldoInicial representa a abertura da competência e não uma receita. Quando
    # a referência coincide com o primeiro dia do mês (como janeiro/2026), ele
    # precisa compor o saldo de abertura mesmo não existindo no dia anterior.
    with session_scope() as s:
        sis = s.execute(
            select(SaldoInicial, ContaFinanceira)
            .join(ContaFinanceira, ContaFinanceira.id == SaldoInicial.conta_financeira_id)
            .where(SaldoInicial.data_referencia == inicio, tenant_where(SaldoInicial.tesouraria_id))
        ).all()
    if sis:
        saldo_ant = dict(saldo_ant)
        for si, conta in sis:
            bc = 'B' if conta.tipo == 'BANCO' else 'C'
            saldo_ant[bc] = Decimal(saldo_ant.get(bc, 0)) + Decimal(si.valor)
        saldo_ant['GERAL'] = Decimal(saldo_ant.get('B', 0)) + Decimal(saldo_ant.get('C', 0))
    saldo_fim = saldos(fim=fim)
    running = Decimal(saldo_ant.get("GERAL", 0))
    rows = []
    totals = {"entrada_banco": Decimal("0"), "saida_banco": Decimal("0"), "entrada_caixa": Decimal("0"), "saida_caixa": Decimal("0")}
    source_pages = {}

    for l, c, ci in result:
        val = Decimal(l.valor)
        if l.natureza == "ENTRADA":
            running += val
        else:
            running -= val
        eb = val if l.origem_bc == "B" and l.natureza == "ENTRADA" else None
        sb = val if l.origem_bc == "B" and l.natureza == "SAIDA" else None
        ec = val if l.origem_bc == "C" and l.natureza == "ENTRADA" else None
        sc = val if l.origem_bc == "C" and l.natureza == "SAIDA" else None
        if eb is not None: totals["entrada_banco"] += val
        if sb is not None: totals["saida_banco"] += val
        if ec is not None: totals["entrada_caixa"] += val
        if sc is not None: totals["saida_caixa"] += val
        row = {
            "id": l.id,
            "data": l.data_movimento,
            "codigo": code_display(c.codigo if c else ""),
            "bc": l.origem_bc,
            "especificacao": l.especificacao,
            "entrada_banco": eb,
            "saida_banco": sb,
            "entrada_caixa": ec,
            "saida_caixa": sc,
            "saldo": running,
            "pagina_origem": ci.pagina if ci else None,
            "seq_origem": ci.seq_origem if ci else None,
            "arquivo_origem": ci.arquivo_origem if ci else None,
            "origem_lancamento": l.origem_lancamento,
        }
        rows.append(row)
        if ci:
            source_pages.setdefault(ci.pagina, 0)
            source_pages[ci.pagina] += 1

    return {
        "ano": ano, "mes": mes, "mes_nome": MESES[mes], "inicio": inicio, "fim": fim,
        "saldo_inicio_banco": Decimal(saldo_ant.get("B", 0)),
        "saldo_inicio_caixa": Decimal(saldo_ant.get("C", 0)),
        "saldo_inicio_geral": Decimal(saldo_ant.get("GERAL", 0)),
        "saldo_fim_banco": Decimal(saldo_fim.get("B", 0)),
        "saldo_fim_caixa": Decimal(saldo_fim.get("C", 0)),
        "saldo_fim_geral": Decimal(saldo_fim.get("GERAL", 0)),
        "rows": rows, "totals": totals, "source_pages": source_pages,
    }


def pdf_original_exato_se_valido(ano: int, mes: int) -> bytes | None:
    """Retorna o PDF histórico original quando a base oficial ainda é exatamente a carga daquele arquivo.

    Isso garante fidelidade 100% (inclusive fontes, quebras, cores, vírgulas e paginação) para os
    demonstrativos consolidados originais. Se houver qualquer inclusão/correção/cancelamento no mês,
    cai automaticamente para o gerador dinâmico.
    """
    path = ROOT / f"{mes:02d}_{ano}.pdf"
    if not path.exists():
        return None
    inicio, fim, filtro = _month_filter(ano, mes)
    arquivo = path.name
    with session_scope() as s:
        total_arquivo = s.scalar(select(func.count(CargaInicialItem.id)).where(CargaInicialItem.arquivo_origem == arquivo)) or 0
        ativos_arquivo = s.scalar(
            select(func.count(Lancamento.id))
            .join(CargaInicialItem, CargaInicialItem.lancamento_id == Lancamento.id)
            .where(CargaInicialItem.arquivo_origem == arquivo, Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))
        ) or 0
        extras = s.scalar(
            select(func.count(Lancamento.id)).where(
                filtro,
                Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id),
                Lancamento.origem_lancamento != "CARGA_PDF_2026",
            )
        ) or 0
    if total_arquivo and total_arquivo == ativos_arquivo and extras == 0:
        return path.read_bytes()
    return None


def _report_geometry(formato: str = "modelo"):
    from reportlab.lib.pagesizes import landscape, A4
    if formato == "oficio":
        page = (216/25.4*72, 330/25.4*72)
        return landscape(page), "oficio"
    return landscape(A4), "modelo"


def _font_setup():
    """Arial-compatible font when available, falling back to Helvetica."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import subprocess
    try:
        regular = subprocess.check_output(["fc-match", "-f", "%{file}", "Arial"], text=True).strip()
        bold = subprocess.check_output(["fc-match", "-f", "%{file}", "Arial:style=Bold"], text=True).strip()
        if regular and bold:
            if "APLBArial" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("APLBArial", regular))
            if "APLBArial-Bold" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("APLBArial-Bold", bold))
            return "APLBArial", "APLBArial-Bold"
    except Exception:
        pass
    return "Helvetica", "Helvetica-Bold"



def _vertical_pages(data: dict) -> list[list[dict]]:
    """Pagina verticalmente o demonstrativo em uma unica faixa A:I.

    Quando os lancamentos vieram da carga historica, preserva exatamente a pagina
    de origem do PDF consolidado (jan/2026 = 5 paginas). Para meses novos, calcula
    paginas pela altura estimada das descricoes, sempre mantendo todas as colunas
    na mesma folha.
    """
    rows = data.get("rows", [])
    if rows and all(r.get("pagina_origem") for r in rows):
        max_source = max(int(r["pagina_origem"]) for r in rows)
        return [[r for r in rows if int(r.get("pagina_origem") or 0) == p] for p in range(1, max_source + 1)]

    pages: list[list[dict]] = []
    current: list[dict] = []
    used = 0.0
    for r in rows:
        text = r.get("especificacao") or ""
        # pagina 1 perde espaco com o cabecalho institucional.
        limit = 24.0 if not pages else 34.0
        weight = max(1.0, min(4.2, (len(text) + 72) / 73.0))
        if current and used + weight > limit:
            pages.append(current)
            current = []
            used = 0.0
        current.append(r)
        used += weight
    if current or not pages:
        pages.append(current)
    return pages


def _page_row_heights(rows: list[dict], available: float) -> list[float]:
    if not rows:
        return []
    weights=[]
    for r in rows:
        text=r.get('especificacao') or ''
        lines=max(1,(len(text)+74)//75)
        weights.append(max(1.0,min(4.0,float(lines))))
    unit=available/max(sum(weights),1)
    # referencia tem linhas compactas, mas descricoes longas crescem.
    return [max(11.0,min(34.0,unit*w)) for w in weights]


def gerar_pdf_movimento(data: dict, formato: str = "modelo") -> bytes:
    """Gera o modelo principal em UMA faixa horizontal, como o PDF de 5 paginas.

    Todas as colunas ficam juntas em cada folha:
    Dia | Codigo | C/B | Especificacao | Entrada/Banco | Saida/Banco |
    Entrada/Caixa | Saida/Caixa | Saldo C/B.
    """
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.lib import colors

    (W,H),_= _report_geometry(formato)
    model_w,model_h=841.8,595.2
    sx,sy=W/model_w,H/model_h
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=(W,H))
    FONT,FONT_BOLD=_font_setup()
    # Linhas verticais medidas do modelo consolidado de 5 paginas.
    xm=[10,59,92,121,418,511,601,695,770,832]
    x=[v*sx for v in xm]
    left,right=x[0],x[-1]
    blue=colors.HexColor('#00A6D9'); red=colors.red
    yellow=colors.HexColor('#FFC000'); green=colors.HexColor('#92D050')

    def draw_text(xx,yy,text,size=5.8,bold=False,color=colors.black,align='left'):
        font=FONT_BOLD if bold else FONT; fs=size*min(sx,sy); t=str(text or '')
        c.setFont(font,fs); c.setFillColor(color)
        if align=='right': xx-=stringWidth(t,font,fs)
        elif align=='center': xx-=stringWidth(t,font,fs)/2
        c.drawString(xx,yy,t)

    def wrap(text,maxw,font,fs):
        words=str(text or '').split(); lines=[]; cur=''
        for w in words:
            test=(cur+' '+w).strip()
            if not cur or stringWidth(test,font,fs)<=maxw: cur=test
            else: lines.append(cur); cur=w
        if cur: lines.append(cur)
        return lines or ['']

    def cell(x0,x1,yt,h,text,size=5.3,bold=False,color=colors.black,align='left'):
        font=FONT_BOLD if bold else FONT; fs=size*min(sx,sy); maxw=x1-x0-4*sx
        lines=wrap(text,maxw,font,fs); lead=fs+0.6*sy
        total=len(lines)*lead; yy=yt-(h-total)/2-fs
        for line in lines:
            if align=='right': xx=x1-2*sx-stringWidth(line,font,fs)
            elif align=='center': xx=(x0+x1)/2-stringWidth(line,font,fs)/2
            else: xx=x0+2*sx
            c.setFont(font,fs); c.setFillColor(color); c.drawString(xx,yy,line); yy-=lead

    def grid(yt,h,row=None,blank_saldo=None):
        c.setStrokeColor(colors.black); c.setLineWidth(0.62*min(sx,sy))
        for xx in x: c.line(xx,yt,xx,yt-h)
        c.line(left,yt,right,yt); c.line(left,yt-h,right,yt-h)
        if row is None:
            for col in range(4,8): cell(x[col],x[col+1],yt,h,'-',5.0,align='right')
            if blank_saldo is not None: cell(x[8],x[9],yt,h,br_money(blank_saldo),5.2,bold=True,color=blue,align='right')
            return
        fill=yellow if row.get('bc')=='B' else green
        c.setFillColor(fill); c.rect(x[2],yt-h,x[3]-x[2],h,stroke=0,fill=1)
        cell(x[0],x[1],yt,h,row['data'].strftime('%d/%m/%Y'),4.8,align='center')
        cell(x[1],x[2],yt,h,row.get('codigo',''),5.3,bold=True,align='center')
        cell(x[2],x[3],yt,h,row.get('bc',''),5.2,bold=True,align='center')
        cell(x[3],x[4],yt,h,row.get('especificacao',''),4.9,bold=False)
        vals=[row.get('entrada_banco'),row.get('saida_banco'),row.get('entrada_caixa'),row.get('saida_caixa'),row.get('saldo')]
        for j,v in enumerate(vals,4):
            if j==8:
                cell(x[j],x[j+1],yt,h,br_money(v),5.1,bold=True,color=blue,align='right')
            else:
                col=blue if j in (4,6) and v is not None else red if j in (5,7) and v is not None else colors.black
                cell(x[j],x[j+1],yt,h,'-' if v is None else br_money(v),5.1,bold=v is not None,color=col,align='right')

    pages=_vertical_pages(data); total_pages=len(pages)
    for pno,rows in enumerate(pages,1):
        if pno==1:
            y=H-14*sy
            # tres faixas institucionais
            for idx,t in enumerate([
                'APLB - SINDICATO DOS TRABALHADORES EM EDUCAÇÃO DO ESTADO DA BAHIA',
                'DELEGACIA SINDICAL DO SISAL, ARACI - BAHIA',
                'DEMONSTRATIVO DO MOVIMENTO FINANCEIRO BANCO/CAIXA - CNPJ 14.029.219/0001-28',
            ]):
                bh=16*sy; c.rect(left,y-bh,right-left,bh,stroke=1,fill=0)
                if idx==2:
                    fs=5.6*min(sx,sy); parts=[('DEMONSTRATIVO DO MOVIMENTO FINANCEIRO ',colors.black),('BANCO/CAIXA',red),(' - CNPJ 14.029.219/0001-28',colors.black)]
                    tw=sum(stringWidth(t,FONT_BOLD,fs) for t,_ in parts); xx=(left+right-tw)/2
                    for t,col in parts:
                        c.setFont(FONT_BOLD,fs); c.setFillColor(col); c.drawString(xx,y-11*sy,t); xx+=stringWidth(t,FONT_BOLD,fs)
                else: draw_text((left+right)/2,y-11*sy,t,5.7,True,align='center')
                y-=bh
            # exercicio / mes / saldos gerais
            bh=33*sy; c.rect(left,y-bh,right-left,bh,stroke=1,fill=0)
            draw_text(x[6]-5*sx,y-10*sy,f'Exercício: {data["ano"]}',5.3,True,red,'right')
            draw_text(x[7]+2*sx,y-10*sy,'Mês:',5.3,True)
            draw_text(right-5*sx,y-10*sy,data['mes_nome'],5.3,True,red,'right')
            draw_text(x[6]-5*sx,y-21*sy,'Saldo no início do mês:',5.2,True,align='right'); draw_text(x[6]+4*sx,y-21*sy,'R$',5.2,False,blue)
            draw_text(x[8]-5*sx,y-21*sy,br_money(data['saldo_inicio_geral']),5.3,True,blue,'right')
            draw_text(x[6]-5*sx,y-31*sy,'Saldo no fim do mês:',5.2,True,align='right'); draw_text(x[6]+4*sx,y-31*sy,'R$',5.2,False,blue)
            c.setFillColor(colors.yellow); c.rect(x[7],y-33*sy,x[8]-x[7],11*sy,stroke=0,fill=1)
            draw_text(x[8]-5*sx,y-31*sy,br_money(data['saldo_fim_geral']),5.3,True,blue,'right')
            y-=bh
            # saldos banco/caixa + saldo geral
            bh=43*sy; c.rect(left,y-bh,right-left,bh,stroke=1,fill=0)
            draw_text(x[4]-5*sx,y-16*sy,'SALDOS BANCO/CAIXA-->>',5.4,True,align='right')
            c.setFillColor(yellow); c.rect(x[4],y-13*sy,x[6]-x[4],13*sy,stroke=1,fill=1); draw_text((x[4]+x[6])/2,y-10*sy,'BANCO',5.5,True,align='center')
            c.setFillColor(green); c.rect(x[6],y-13*sy,x[8]-x[6],13*sy,stroke=1,fill=1); draw_text((x[6]+x[8])/2,y-10*sy,'CAIXA',5.5,True,align='center')
            c.rect(x[8],y-43*sy,x[9]-x[8],43*sy,stroke=1,fill=0); cell(x[8],x[9],y,43*sy,'Sado Geral',5.4,True,align='center')
            vals=[('Saldo início do Mês-->>',data['saldo_inicio_banco'],data['saldo_inicio_caixa']),('Saldo fim do Mês-->>',data['saldo_fim_banco'],data['saldo_fim_caixa'])]
            for j,(lab,bv,cv) in enumerate(vals):
                yy=y-(25+j*12)*sy
                draw_text(x[5]-4*sx,yy,lab,4.8,align='right'); draw_text(x[6]-4*sx,yy,br_money(bv),5.1,True,blue,'right')
                draw_text(x[7]-4*sx,yy,lab,4.8,align='right'); draw_text(x[8]-4*sx,yy,br_money(cv),5.1,True,blue,'right')
            y-=bh
            hh=15*sy
            headers=['Dia','Código','C/B','Especificação','Entrada/Banco','Saída/Banco','Entrada/Caixa','Saída/Caixa','SadoC/B']
            for xx in x: c.line(xx,y,xx,y-hh)
            c.line(left,y,right,y); c.line(left,y-hh,right,y-hh)
            for i,hdr in enumerate(headers):
                color=blue if i in (4,6,8) else red if i in (5,7) else colors.black
                cell(x[i],x[i+1],y,hh,hdr,4.9,True,color,'center')
            y-=hh
            for _ in range(3):
                rh=12*sy; grid(y,rh,None,data['saldo_inicio_geral']); y-=rh
            available=y-52*sy
        else:
            y=H-16*sy; available=y-48*sy

        heights=_page_row_heights(rows,available)
        for row,rh in zip(rows,heights): grid(y,rh,row); y-=rh

        if pno==total_pages:
            rh=14*sy
            if y<62*sy: y=62*sy
            for xx in x: c.line(xx,y,xx,y-rh)
            c.line(left,y,right,y); c.line(left,y-rh,right,y-rh)
            cell(x[1],x[2],y,rh,str(len(data['rows'])+1),5.3,True,align='center')
            cell(x[2],x[4],y,rh,'TOTAL..............................................................................................................................',4.8,True,align='right')
            vals=[data['totals']['entrada_banco'],data['totals']['saida_banco'],data['totals']['entrada_caixa'],data['totals']['saida_caixa']]
            for j,v in enumerate(vals,4):
                color=blue if j in (4,6) else red
                cell(x[j],x[j+1],y,rh,br_money(v),5.2,True,color,'right')
            cell(x[8],x[9],y,rh,'-',5.0,False,colors.black,'right')

        draw_text(W/2,22*sy,f"{data['mes_nome']} - {data['ano']} --> Página {pno} de {total_pages}",7.6,False,colors.black,'center')
        c.showPage()
    c.save(); return buf.getvalue()


def gerar_excel_movimento(data: dict, formato: str = "modelo") -> bytes:
    """Excel fiel ao modelo principal: todas as 9 colunas em uma folha de largura."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.worksheet.pagebreak import Break

    wb=Workbook(); ws=wb.active; ws.title=f"{data['mes_nome']}_{data['ano']}"
    ws.sheet_view.showGridLines=False
    ws.page_setup.orientation='landscape'; ws.page_setup.paperSize='9' if formato!='oficio' else '14'
    ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0; ws.page_setup.pageOrder='downThenOver'
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_margins.left=0.10; ws.page_margins.right=0.10; ws.page_margins.top=0.20; ws.page_margins.bottom=0.30
    widths={'A':11,'B':8,'C':6,'D':60,'E':18,'F':18,'G':18,'H':18,'I':15}
    for col,w in widths.items(): ws.column_dimensions[col].width=w
    thin=Side(style='thin',color='000000'); border=Border(left=thin,right=thin,top=thin,bottom=thin)
    center=Alignment(horizontal='center',vertical='center',wrap_text=True); lefta=Alignment(horizontal='left',vertical='center',wrap_text=True); righta=Alignment(horizontal='right',vertical='center')
    blue='00A6D9'; red='FF0000'; yellow='FFC000'; green='92D050'; arial='Arial'
    r=1
    for t in ['APLB - SINDICATO DOS TRABALHADORES EM EDUCAÇÃO DO ESTADO DA BAHIA','DELEGACIA SINDICAL DO SISAL, ARACI - BAHIA','DEMONSTRATIVO DO MOVIMENTO FINANCEIRO BANCO/CAIXA - CNPJ 14.029.219/0001-28']:
        ws.merge_cells(start_row=r,start_column=1,end_row=r,end_column=9); cc=ws.cell(r,1,t); cc.font=Font(name=arial,size=8,bold=True); cc.alignment=center
        for col in range(1,10): ws.cell(r,col).border=border
        ws.row_dimensions[r].height=16; r+=1
    # Cabecalho exercicio/saldos gerais
    for rr in range(r,r+3):
        for col in range(1,10): ws.cell(rr,col).border=border
    ws.cell(r,6,f'Exercício: {data["ano"]}').font=Font(name=arial,size=7,bold=True,color=red); ws.cell(r,6).alignment=righta
    ws.cell(r,8,'Mês:').font=Font(name=arial,size=7,bold=True); ws.cell(r,8).alignment=righta; ws.cell(r,9,data['mes_nome']).font=Font(name=arial,size=7,bold=True,color=red); ws.cell(r,9).alignment=center
    ws.cell(r+1,6,'Saldo no início do mês:').font=Font(name=arial,size=7,bold=True); ws.cell(r+1,6).alignment=righta; ws.cell(r+1,7,'R$').font=Font(name=arial,size=7,color=blue)
    ws.cell(r+1,8,float(data['saldo_inicio_geral'])); ws.cell(r+1,8).number_format='#,##0.00'; ws.cell(r+1,8).font=Font(name=arial,size=7,bold=True,color=blue); ws.cell(r+1,8).alignment=righta
    ws.cell(r+2,6,'Saldo no fim do mês:').font=Font(name=arial,size=7,bold=True); ws.cell(r+2,6).alignment=righta; ws.cell(r+2,7,'R$').font=Font(name=arial,size=7,color=blue)
    ws.cell(r+2,8,float(data['saldo_fim_geral'])); ws.cell(r+2,8).number_format='#,##0.00'; ws.cell(r+2,8).font=Font(name=arial,size=7,bold=True,color=blue); ws.cell(r+2,8).alignment=righta
    ws.cell(r+2,9,'-').fill=PatternFill('solid',fgColor='FFFF00'); ws.cell(r+2,9).font=Font(name=arial,size=7,color=red); ws.cell(r+2,9).alignment=righta
    r+=3
    ws.merge_cells(start_row=r,start_column=1,end_row=r+2,end_column=4); ws.cell(r,1,'SALDOS BANCO/CAIXA-->>').font=Font(name=arial,size=7,bold=True); ws.cell(r,1).alignment=righta
    ws.merge_cells(start_row=r,start_column=5,end_row=r,end_column=6); ws.cell(r,5,'BANCO').fill=PatternFill('solid',fgColor=yellow); ws.cell(r,5).font=Font(name=arial,size=7,bold=True); ws.cell(r,5).alignment=center
    ws.merge_cells(start_row=r,start_column=7,end_row=r,end_column=8); ws.cell(r,7,'CAIXA').fill=PatternFill('solid',fgColor=green); ws.cell(r,7).font=Font(name=arial,size=7,bold=True); ws.cell(r,7).alignment=center
    ws.merge_cells(start_row=r,start_column=9,end_row=r+2,end_column=9); ws.cell(r,9,'Sado Geral').font=Font(name=arial,size=7,bold=True); ws.cell(r,9).alignment=center
    for rr in range(r,r+3):
        for col in range(1,10): ws.cell(rr,col).border=border
    for j,(lab,bv,cv) in enumerate([('Saldo início do Mês-->>',data['saldo_inicio_banco'],data['saldo_inicio_caixa']),('Saldo fim do Mês-->>',data['saldo_fim_banco'],data['saldo_fim_caixa'])],1):
        ws.cell(r+j,5,lab).alignment=righta; ws.cell(r+j,5).font=Font(name=arial,size=7)
        ws.cell(r+j,6,float(bv)); ws.cell(r+j,6).number_format='#,##0.00'; ws.cell(r+j,6).font=Font(name=arial,size=7,bold=True,color=blue); ws.cell(r+j,6).alignment=righta
        ws.cell(r+j,7,lab).alignment=righta; ws.cell(r+j,7).font=Font(name=arial,size=7)
        ws.cell(r+j,8,float(cv)); ws.cell(r+j,8).number_format='#,##0.00'; ws.cell(r+j,8).font=Font(name=arial,size=7,bold=True,color=blue); ws.cell(r+j,8).alignment=righta
    r+=3
    headers=['Dia','Código','C/B','Especificação','Entrada/Banco','Saída/Banco','Entrada/Caixa','Saída/Caixa','SadoC/B']
    for col,hdr in enumerate(headers,1):
        cc=ws.cell(r,col,hdr); cc.border=border; cc.alignment=center; cc.font=Font(name=arial,size=7,bold=True,color=(blue if col in (5,7,9) else red if col in (6,8) else '000000'))
    r+=1
    for _ in range(3):
        for col in range(1,10): ws.cell(r,col).border=border
        for col in range(5,9): ws.cell(r,col,'-').alignment=righta
        ws.cell(r,9,float(data['saldo_inicio_geral'])); ws.cell(r,9).number_format='#,##0.00'; ws.cell(r,9).font=Font(name=arial,size=7,bold=True,color=blue); ws.cell(r,9).alignment=righta
        ws.row_dimensions[r].height=14; r+=1

    pages=_vertical_pages(data)
    for pidx,prows in enumerate(pages,1):
        for row in prows:
            vals=[row['data'],row['codigo'],row['bc'],row['especificacao'],row['entrada_banco'],row['saida_banco'],row['entrada_caixa'],row['saida_caixa'],row['saldo']]
            for col,v in enumerate(vals,1):
                cc=ws.cell(r,col); cc.border=border
                if col==1: cc.value=v; cc.number_format='dd/mm/yyyy'; cc.alignment=center
                elif col in (2,3): cc.value=v; cc.alignment=center; cc.font=Font(name=arial,size=7,bold=(col==2))
                elif col==4: cc.value=v; cc.alignment=lefta; cc.font=Font(name=arial,size=7)
                else:
                    cc.value='-' if v is None else float(v); cc.alignment=righta
                    if v is not None: cc.number_format='#,##0.00'; cc.font=Font(name=arial,size=7,bold=True,color=(blue if col in (5,7,9) else red))
                    else: cc.font=Font(name=arial,size=7)
            ws.cell(r,3).fill=PatternFill('solid',fgColor=yellow if row['bc']=='B' else green)
            lines=max(1,(len(row.get('especificacao') or '')+72)//73); ws.row_dimensions[r].height=max(14,min(44,12+7*(lines-1)))
            r+=1
        if pidx<len(pages): ws.row_breaks.append(Break(id=r-1))
    for col in range(1,10): ws.cell(r,col).border=border
    ws.cell(r,2,len(data['rows'])+1); ws.cell(r,2).alignment=center
    ws.merge_cells(start_row=r,start_column=3,end_row=r,end_column=4); ws.cell(r,3,'TOTAL..............................................................................................................................'); ws.cell(r,3).font=Font(name=arial,size=7,bold=True); ws.cell(r,3).alignment=righta
    for col,v in enumerate([data['totals']['entrada_banco'],data['totals']['saida_banco'],data['totals']['entrada_caixa'],data['totals']['saida_caixa']],5):
        cc=ws.cell(r,col,float(v)); cc.number_format='#,##0.00'; cc.alignment=righta; cc.font=Font(name=arial,size=7,bold=True,color=(blue if col in (5,7) else red))
    ws.cell(r,9,'-').alignment=righta
    ws.print_area=f'A1:I{r}'
    ws.oddFooter.center.text=f"{data['mes_nome']} - {data['ano']} --> Página &P de &N"; ws.oddFooter.center.size=9
    ws.evenFooter.center.text=f"{data['mes_nome']} - {data['ano']} --> Página &P de &N"; ws.evenFooter.center.size=9
    out=BytesIO(); wb.save(out); return out.getvalue()
