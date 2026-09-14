from __future__ import annotations
from collections import defaultdict
from datetime import date
from calendar import monthrange
from decimal import Decimal
from io import BytesIO

from services.financeiro import listar_lancamentos, listar_codigos, saldos
from relatorios.movimento_financeiro import movimento_mes, br_money, MESES

MESES_CURTOS={1:'JAN',2:'FEV',3:'MAR',4:'ABR',5:'MAI',6:'JUN',7:'JUL',8:'AGO',9:'SET',10:'OUT',11:'NOV',12:'DEZ'}
VALIDOS={'APROVADO','CONCILIADO','FECHADO'}

# Papel Ofício/Folio: 8,5 x 13 pol. (216 x 330 mm).
# Regra V9: relatórios largos em paisagem; relatórios compactos em retrato.
OFICIO=(216/25.4*72,330/25.4*72)
RETRATO_IDS={'lista_codigos'}

def _orientacao_relatorio(report_id:str)->str:
    return 'portrait' if report_id in RETRATO_IDS else 'landscape'

def _configurar_impressao_excel(ws, report_id:str):
    ws.page_setup.orientation=_orientacao_relatorio(report_id)
    ws.page_setup.paperSize='14'  # Folio 8.5 x 13 in (Ofício)
    ws.page_setup.fitToWidth=1
    ws.page_setup.fitToHeight=0
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.sheet_properties.pageSetUpPr.autoPageBreaks=False
    ws.print_options.horizontalCentered=True
    ws.page_margins.left=0.25; ws.page_margins.right=0.25
    ws.page_margins.top=0.35; ws.page_margins.bottom=0.35
    ws.page_margins.header=0.15; ws.page_margins.footer=0.15
    ws.print_area=f'A1:{ws.cell(ws.max_row,ws.max_column).coordinate}'

REPORT_CATALOG=[
 {'id':'movimento','nome':'Movimento Financeiro Mensal','grupo':'Mensais','periodo':'mes','descricao':'Demonstrativo detalhado Banco/Caixa com saldo acumulado.'},
 {'id':'dre','nome':'DRE / Relatório de Execução Financeira','grupo':'Contábil','periodo':'mes','descricao':'DRE oficial derivada dos lançamentos e regras contábeis.'},
 {'id':'entradas_saidas','nome':'Entradas e Saídas - Bruto / Valor Nominal','grupo':'Analíticos','periodo':'ano','descricao':'Entradas e saídas por código e mês, sem base paralela.'},
 {'id':'lista_codigos','nome':'Lista de Códigos','grupo':'Cadastros','periodo':'ano','descricao':'Catálogo de códigos oficiais e referência.'},
 {'id':'prestacao_assembleia','nome':'Prestação de Contas - Assembleia','grupo':'Prestação de Contas','periodo':'intervalo','descricao':'Movimentação do período para prestação de contas.'},
 {'id':'sem_bruto_1','nome':'Resumo Geral Banco + Caixa - 1º Semestre Bruto','grupo':'Semestrais','periodo':'semestre1','descricao':'Resumo bruto de janeiro a junho.'},
 {'id':'sem_bruto_2','nome':'Resumo Geral Banco + Caixa - 2º Semestre Bruto','grupo':'Semestrais','periodo':'semestre2','descricao':'Resumo bruto de julho a dezembro.'},
 {'id':'sem_liquido_1','nome':'Resumo Geral Banco + Caixa - 1º Semestre Líquido','grupo':'Semestrais','periodo':'semestre1','descricao':'Resumo líquido, excluindo transferências internas Banco/Caixa.'},
 {'id':'sem_liquido_2','nome':'Resumo Geral Banco + Caixa - 2º Semestre Líquido','grupo':'Semestrais','periodo':'semestre2','descricao':'Resumo líquido, excluindo transferências internas Banco/Caixa.'},
 {'id':'resumo_banco','nome':'Resumo Geral de Banco','grupo':'Resumos','periodo':'ano','descricao':'Entradas e saídas de Banco por código e mês.'},
 {'id':'resumo_caixa','nome':'Resumo Geral de Caixa','grupo':'Resumos','periodo':'ano','descricao':'Entradas e saídas de Caixa por código e mês.'},
 {'id':'resumo_banco_caixa','nome':'Resumo Geral - Banco e Caixa','grupo':'Resumos','periodo':'ano','descricao':'Consolidação Banco + Caixa por código e mês, com 1º e 2º semestre.'},
 {'id':'saldos_anos','nome':'Saldos de Vários Anos','grupo':'Históricos','periodo':'anos','descricao':'Saldo final mensal de Banco, Caixa e consolidado.'},
 {'id':'suprimento_caixa','nome':'Suprimento de Caixa','grupo':'Resumos','periodo':'ano','descricao':'Confronta saída do Banco e entrada no Caixa do código 0801, mês a mês.'},
 {'id':'suprimento_1','nome':'Suprimento de Caixa - 1º Semestre (legado)','grupo':'Semestrais','periodo':'semestre1','descricao':'Visão legada do código 0801 de janeiro a junho.'},
 {'id':'suprimento_2','nome':'Suprimento de Caixa - 2º Semestre (legado)','grupo':'Semestrais','periodo':'semestre2','descricao':'Visão legada do código 0801 de julho a dezembro.'},
]

def _periodo(ano:int, meses:list[int]):
    return date(ano,min(meses),1),date(ano,max(meses),monthrange(ano,max(meses))[1])

def _rows(inicio:date,fim:date):
    return [r for r in listar_lancamentos(inicio,fim,limit=100000) if r.get('status') in VALIDOS]

def _code_norm(c):
    s=str(c or '').strip()
    if s.isdigit(): return s.zfill(4)
    return s

def _is_internal(r):
    return r.get('origem')=='TRANSFERENCIA_INTERNA' or _code_norm(r.get('codigo'))=='0801' or 'SUPRIMENTO DE CAIXA' in (r.get('especificacao') or '').upper()

def matriz_codigos(ano:int, meses:list[int], bc:str|None=None, liquido:bool=False):
    ini,fim=_periodo(ano,meses); rows=_rows(ini,fim)
    agg=defaultdict(lambda:defaultdict(lambda:{'ENTRADA':Decimal('0'),'SAIDA':Decimal('0')}))
    desc={}
    for r in rows:
        if bc and r['B/C']!=bc: continue
        if liquido and _is_internal(r): continue
        m=r['data'].month; cod=_code_norm(r['codigo']) or 'SEM CÓDIGO'; desc[cod]=r.get('codigo_descricao') or r.get('especificacao') or ''
        agg[cod][m][r['natureza']]+=Decimal(str(r['valor']))
    out=[]
    for cod in sorted(agg, key=lambda x:(not x.isdigit(),x)):
        item={'codigo':cod,'descricao':desc.get(cod,'')}
        for m in meses:
            item[f'e{m}']=float(agg[cod][m]['ENTRADA']); item[f's{m}']=float(agg[cod][m]['SAIDA']); item[f'l{m}']=float(agg[cod][m]['ENTRADA']-agg[cod][m]['SAIDA'])
        out.append(item)
    return out

def suprimento(ano:int, meses:list[int]):
    ini,fim=_periodo(ano,meses); rows=_rows(ini,fim); vals={m:Decimal('0') for m in meses}
    for r in rows:
        if r['data'].month not in vals: continue
        if _code_norm(r['codigo'])=='0801' or 'SUPRIMENTO DE CAIXA' in (r.get('especificacao') or '').upper():
            if r['B/C']=='B' and r['natureza']=='SAIDA': vals[r['data'].month]+=Decimal(str(r['valor']))
    return vals

def saldos_mensais(ano_ini:int, ano_fim:int):
    out=[]
    for ano in range(ano_ini,ano_fim+1):
        row={'ano':ano,'B':{},'C':{},'T':{}}
        for m in range(1,13):
            mov=movimento_mes(ano,m)
            row['B'][m]=Decimal(str(mov['saldo_fim_banco'])); row['C'][m]=Decimal(str(mov['saldo_fim_caixa'])); row['T'][m]=Decimal(str(mov['saldo_fim_geral']))
        out.append(row)
    return out

def preview_rows(report_id:str,ano:int,mes:int=1,ano_ini:int|None=None,ano_fim:int|None=None):
    if report_id=='resumo_banco': return matriz_codigos(ano,list(range(1,13)),'B')
    if report_id=='resumo_caixa': return matriz_codigos(ano,list(range(1,13)),'C')
    if report_id=='entradas_saidas': return matriz_codigos(ano,list(range(1,13)))
    if report_id in ('sem_bruto_1','sem_liquido_1'): return matriz_codigos(ano,list(range(1,7)),liquido=report_id.startswith('sem_liquido'))
    if report_id in ('sem_bruto_2','sem_liquido_2'): return matriz_codigos(ano,list(range(7,13)),liquido=report_id.startswith('sem_liquido'))
    if report_id=='lista_codigos': return listar_codigos()
    if report_id.startswith('suprimento_'):
        meses=list(range(1,7)) if report_id.endswith('1') else list(range(7,13)); vals=suprimento(ano,meses)
        return [{'codigo':'0801','descricao':'SUPRIMENTO DE CAIXA',**{MESES[m]:float(vals[m]) for m in meses},'TOTAL':float(sum(vals.values()))}]
    if report_id=='saldos_anos': return saldos_mensais(ano_ini or 2026,ano_fim or ano)
    return []

def _xlsx_base(title:str):
    from openpyxl import Workbook
    from openpyxl.styles import Font,Alignment,Border,Side
    wb=Workbook(); ws=wb.active; ws.title='Relatório'; ws.sheet_view.showGridLines=False
    ws['A1']=title; ws['A1'].font=Font(bold=True,size=14); ws['A1'].alignment=Alignment(horizontal='center'); return wb,ws

def gerar_excel_tabular(report_id:str,ano:int,mes:int=1,ano_ini:int|None=None,ano_fim:int|None=None)->bytes:
    from openpyxl.styles import Font,Alignment,Border,Side
    cat=next(x for x in REPORT_CATALOG if x['id']==report_id); wb,ws=_xlsx_base(cat['nome']); thin=Side(style='thin',color='000000')
    if report_id=='saldos_anos':
        rows=preview_rows(report_id,ano,ano_ini=ano_ini,ano_fim=ano_fim); r=3
        for key,label in [('B','SALDOS BANCO'),('C','SALDOS CAIXA'),('T','SALDOS BANCO + CAIXA')]:
            ws.cell(r,1,f'{label} - ANOS {ano_ini} A {ano_fim}').font=Font(bold=True); r+=1
            headers=['ANO']+[MESES[m] for m in range(1,13)]
            for j,h in enumerate(headers,1): ws.cell(r,j,h).font=Font(bold=True)
            r+=1
            for row in rows:
                ws.cell(r,1,row['ano'])
                for m in range(1,13): ws.cell(r,m+1,float(row[key][m])).number_format='#,##0.00;[Red](#,##0.00);-'
                r+=1
            r+=2
    elif report_id.startswith('suprimento_'):
        rows=preview_rows(report_id,ano); meses=list(range(1,7)) if report_id.endswith('1') else list(range(7,13)); headers=['COD']+[MESES[m] for m in meses]+['TOTAL']; r=3
        for j,h in enumerate(headers,1): ws.cell(r,j,h).font=Font(bold=True)
        r+=1; rr=rows[0]
        ws.cell(r,1,'801')
        for j,m in enumerate(meses,2): ws.cell(r,j,rr[MESES[m]]).number_format='#,##0.00;[Red](#,##0.00);-'
        ws.cell(r,len(headers),rr['TOTAL']).number_format='#,##0.00;[Red](#,##0.00);-'
    elif report_id=='lista_codigos':
        rows=preview_rows(report_id,ano); headers=['CÓDIGO','DESCRIÇÃO','NATUREZA','ATIVO']; r=3
        for j,h in enumerate(headers,1): ws.cell(r,j,h).font=Font(bold=True)
        for item in rows:
            r+=1; vals=[item.get('codigo',''),item.get('descricao',''),item.get('natureza',''),item.get('ativo',True)]
            for j,v in enumerate(vals,1): ws.cell(r,j,v)
    else:
        rows=preview_rows(report_id,ano); meses=(list(range(1,7)) if report_id.endswith('_1') else list(range(7,13)) if report_id.endswith('_2') else list(range(1,13)))
        headers=['CÓDIGO','REFERÊNCIA']
        mode='both' if report_id in ('entradas_saidas',) or report_id.startswith('sem_') else ('B' if report_id=='resumo_banco' else 'C')
        if mode=='both':
            for m in meses: headers += [f'{MESES[m]} ENTRADA',f'{MESES[m]} SAÍDA',f'{MESES[m]} LÍQUIDO']
        else:
            for m in meses: headers += [f'{MESES[m]} ENTRADA',f'{MESES[m]} SAÍDA']
        r=3
        for j,h in enumerate(headers,1): ws.cell(r,j,h).font=Font(bold=True); ws.cell(r,j).alignment=Alignment(horizontal='center',wrap_text=True)
        for item in rows:
            r+=1; ws.cell(r,1,item['codigo']); ws.cell(r,2,item['descricao'])
            c=3
            for m in meses:
                for key in ([f'e{m}',f's{m}',f'l{m}'] if mode=='both' else [f'e{m}',f's{m}']):
                    ws.cell(r,c,item.get(key,0)).number_format='#,##0.00;[Red](#,##0.00);-'; c+=1
    # shared format
    for col in range(1,ws.max_column+1): ws.column_dimensions[ws.cell(1,col).column_letter].width=14 if col>2 else (12 if col==1 else 42)
    for row in ws.iter_rows():
        for cell in row: cell.alignment=Alignment(vertical='center',wrap_text=True); cell.border=Border(bottom=thin if cell.row in (3,) else Side(style=None))
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=max(2,ws.max_column));
    _configurar_impressao_excel(ws,report_id)
    out=BytesIO(); wb.save(out); return out.getvalue()

def gerar_pdf_tabular(report_id:str,ano:int,mes:int=1,ano_ini:int|None=None,ano_fim:int|None=None)->bytes:
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer,PageBreak
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    cat=next(x for x in REPORT_CATALOG if x['id']==report_id); buf=BytesIO(); page_size=OFICIO if _orientacao_relatorio(report_id)=='portrait' else landscape(OFICIO); doc=SimpleDocTemplate(buf,pagesize=page_size,leftMargin=18,rightMargin=18,topMargin=18,bottomMargin=18)
    styles=getSampleStyleSheet(); title=ParagraphStyle('t',parent=styles['Title'],fontSize=11,leading=13,spaceAfter=8); small=ParagraphStyle('s',parent=styles['BodyText'],fontSize=6,leading=7)
    story=[Paragraph(cat['nome'],title),Paragraph(f'Exercício: {ano}',small),Spacer(1,6)]
    def fmt(v): return br_money(v) if v not in (None,'') else '-'
    if report_id=='saldos_anos':
        rows=preview_rows(report_id,ano,ano_ini=ano_ini,ano_fim=ano_fim)
        for key,label in [('B','SALDOS BANCO'),('C','SALDOS CAIXA'),('T','SALDOS: BANCO + CAIXA')]:
            story.append(Paragraph(f'{label} - ANOS {ano_ini} A {ano_fim}',title)); data=[['ANO']+[MESES[m] for m in range(1,13)]]
            for rr in rows: data.append([rr['ano']]+[fmt(rr[key][m]) for m in range(1,13)])
            t=Table(data,repeatRows=1,colWidths=[42]+[58]*12); t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',5.5),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.4,colors.black),('ALIGN',(1,1),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE')])); story += [t,Spacer(1,10)]
    elif report_id.startswith('suprimento_'):
        rr=preview_rows(report_id,ano)[0]; meses=list(range(1,7)) if report_id.endswith('1') else list(range(7,13)); data=[['COD']+[MESES[m] for m in meses]+['TOTAL'],['801']+[fmt(rr[MESES[m]]) for m in meses]+[fmt(rr['TOTAL'])]]; t=Table(data,colWidths=[50]+[90]*(len(data[0])-1)); t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',8),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.5,colors.black),('ALIGN',(1,1),(-1,-1),'RIGHT')])); story.append(t)
    elif report_id=='lista_codigos':
        rows=preview_rows(report_id,ano); data=[['CÓDIGO','DESCRIÇÃO','NATUREZA','ATIVO']]+[[x.get('codigo',''),Paragraph(x.get('descricao',''),small),x.get('natureza',''), 'SIM' if x.get('ativo',True) else 'NÃO'] for x in rows]; t=Table(data,repeatRows=1,colWidths=[70,520,100,60]); t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',6),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.4,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE')])); story.append(t)
    else:
        rows=preview_rows(report_id,ano); meses=(list(range(1,7)) if report_id.endswith('_1') else list(range(7,13)) if report_id.endswith('_2') else list(range(1,13)))
        mode='both' if report_id in ('entradas_saidas',) or report_id.startswith('sem_') else 'bc'
        hdr=['CÓDIGO','REFERÊNCIA']
        for m in meses: hdr += ([f'{MESES_CURTOS[m]} E',f'{MESES_CURTOS[m]} S',f'{MESES_CURTOS[m]} L'] if mode=='both' else [f'{MESES_CURTOS[m]} E',f'{MESES_CURTOS[m]} S'])
        data=[hdr]
        for x in rows:
            rr=[x['codigo'],Paragraph(x['descricao'],small)]
            for m in meses: rr += ([fmt(x.get(f'e{m}',0)),fmt(x.get(f's{m}',0)),fmt(x.get(f'l{m}',0))] if mode=='both' else [fmt(x.get(f'e{m}',0)),fmt(x.get(f's{m}',0))])
            data.append(rr)
        page_w=landscape(OFICIO)[0]-36; first=[45,170]; rem=page_w-sum(first); n=max(1,len(hdr)-2); widths=first+[rem/n]*n
        t=Table(data,repeatRows=1,colWidths=widths); t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',4.8),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.25,colors.black),('ALIGN',(2,1),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE')])); story.append(t)
    doc.build(story); return buf.getvalue()

def prestacao_periodo(inicio:date,fim:date):
    rows=_rows(inicio,fim); total_ent=sum(Decimal(str(r['valor'])) for r in rows if r['natureza']=='ENTRADA'); total_sai=sum(Decimal(str(r['valor'])) for r in rows if r['natureza']=='SAIDA')
    return rows,total_ent,total_sai

def gerar_excel_prestacao(inicio:date,fim:date)->bytes:
    from openpyxl.styles import Font,Alignment
    rows,ent,sai=prestacao_periodo(inicio,fim); wb,ws=_xlsx_base('PRESTAÇÃO DE CONTAS - ASSEMBLEIA'); ws['A2']=f'Período {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}'
    headers=['DATA','CÓDIGO','C/B','ESPECIFICAÇÃO','ENTRADA','SAÍDA'];
    for j,h in enumerate(headers,1): ws.cell(4,j,h).font=Font(bold=True)
    r=4
    for x in sorted(rows,key=lambda q:(q['data'],q['id'])):
        r+=1; vals=[x['data'],x['codigo'],x['B/C'],x['especificacao'],x['valor'] if x['natureza']=='ENTRADA' else 0,x['valor'] if x['natureza']=='SAIDA' else 0]
        for j,v in enumerate(vals,1): ws.cell(r,j,v); ws.cell(r,j).alignment=Alignment(wrap_text=True,vertical='top')
        ws.cell(r,5).number_format=ws.cell(r,6).number_format='#,##0.00;[Red](#,##0.00);-'
    r+=1; ws.cell(r,4,'TOTAL').font=Font(bold=True); ws.cell(r,5,float(ent)); ws.cell(r,6,float(sai)); ws.cell(r,5).number_format=ws.cell(r,6).number_format='#,##0.00;[Red](#,##0.00);-'
    ws.column_dimensions['A'].width=13;ws.column_dimensions['B'].width=10;ws.column_dimensions['C'].width=7;ws.column_dimensions['D'].width=80;ws.column_dimensions['E'].width=16;ws.column_dimensions['F'].width=16
    ws.merge_cells('A1:F1'); _configurar_impressao_excel(ws,'prestacao_assembleia'); out=BytesIO(); wb.save(out); return out.getvalue()

def gerar_pdf_prestacao(inicio:date,fim:date)->bytes:
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors
    rows,ent,sai=prestacao_periodo(inicio,fim); buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(OFICIO),leftMargin=18,rightMargin=18,topMargin=18,bottomMargin=18); styles=getSampleStyleSheet(); small=ParagraphStyle('x',parent=styles['BodyText'],fontSize=5.5,leading=6.5)
    data=[['DATA','CÓDIGO','C/B','ESPECIFICAÇÃO','ENTRADA','SAÍDA']]
    for x in sorted(rows,key=lambda q:(q['data'],q['id'])): data.append([x['data'].strftime('%d/%m/%Y'),x['codigo'],x['B/C'],Paragraph(x['especificacao'],small),br_money(x['valor']) if x['natureza']=='ENTRADA' else '-',br_money(x['valor']) if x['natureza']=='SAIDA' else '-'])
    data.append(['','','','TOTAL',br_money(ent),br_money(sai)])
    t=Table(data,repeatRows=1,colWidths=[65,55,35,500,75,75]);t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',5.5),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.3,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(4,1),(-1,-1),'RIGHT')])); doc.build([Paragraph(f'PRESTAÇÃO DE CONTAS - Período {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}',styles['Heading2']),t]); return buf.getvalue()
