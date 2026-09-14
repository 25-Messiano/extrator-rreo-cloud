from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from database.db import session_scope
from models.entities import (TrabalhadorFolha, EventoFolha, FolhaCompetencia, ReciboAvulso, Favorecido,
    ParametroFolha, HistoricoSalarial, CalendarioFolha, FolhaSnapshot, ChecklistFolha)

def tid():
 import streamlit as st; return int(st.session_state.get('tesouraria_id') or st.session_state.get('portal_tesouraria_id'))
def trabalhadores():
 with session_scope() as s:return [{'id':x.id,'nome':x.nome,'cpf':x.cpf,'cargo':x.cargo,'vinculo':x.vinculo,'salario_base':float(x.salario_base or 0),'ativo':x.ativo} for x in s.scalars(select(TrabalhadorFolha).where(TrabalhadorFolha.tesouraria_id==tid()).order_by(TrabalhadorFolha.nome))]
def salvar_trabalhador(nome,cpf,rg,tel,end,cargo,vinculo,salario):
 with session_scope() as s:
  x=TrabalhadorFolha(tesouraria_id=tid(),nome=nome.strip(),cpf=cpf.strip() or None,rg=rg.strip() or None,telefone=tel.strip() or None,endereco=end.strip() or None,cargo=cargo.strip() or None,vinculo=vinculo,salario_base=Decimal(str(salario)));s.add(x);s.flush();return x.id
def eventos():
 with session_scope() as s:return [{'id':x.id,'codigo':x.codigo,'descricao':x.descricao,'natureza':x.natureza,'formula':x.formula,'ativo':x.ativo} for x in s.scalars(select(EventoFolha).where(EventoFolha.tesouraria_id==tid()).order_by(EventoFolha.codigo))]
def salvar_evento(c,d,n,f):
 with session_scope() as s:x=EventoFolha(tesouraria_id=tid(),codigo=c,descricao=d,natureza=n,formula=f or None);s.add(x);s.flush();return x.id
def folhas():
 with session_scope() as s:return [{'id':x.id,'competencia':x.competencia,'tipo':x.tipo,'status':x.status} for x in s.scalars(select(FolhaCompetencia).where(FolhaCompetencia.tesouraria_id==tid()).order_by(FolhaCompetencia.id.desc()))]
def criar_folha(comp,tipo,obs,uid):
 with session_scope() as s:x=FolhaCompetencia(tesouraria_id=tid(),competencia=comp,tipo=tipo,observacao=obs or None,criado_por=uid);s.add(x);s.flush();return x.id
def prestadores():
 with session_scope() as s:return [{'id':x.id,'nome':x.nome,'documento':x.documento or '','telefone':x.telefone or ''} for x in s.scalars(select(Favorecido).where(Favorecido.tesouraria_id==tid(),Favorecido.ativo==True).order_by(Favorecido.nome))]
def recibos():
 with session_scope() as s:return [{'id':x.id,'nº':f'{x.numero:04d}','nome':x.nome,'data':x.data_recibo.strftime('%d/%m/%Y'),'competência':x.competencia,'valor':float(x.valor),'status':x.status} for x in s.scalars(select(ReciboAvulso).where(ReciboAvulso.tesouraria_id==tid()).order_by(ReciboAvulso.numero.desc()))]
def ultimo(fid):
 with session_scope() as s:
  x=s.scalar(select(ReciboAvulso).where(ReciboAvulso.tesouraria_id==tid(),ReciboAvulso.favorecido_id==fid).order_by(ReciboAvulso.numero.desc()).limit(1))
  return None if not x else {'nome':x.nome,'cpf':x.cpf or '','rg':x.rg or '','telefone':x.telefone or '','endereco':x.endereco or '','servico':x.servico,'documento_blob':x.documento_blob}
def salvar_recibo(fid,nome,cpf,rg,tel,end,dt,comp,valor,servico,doc,pag,uid):
 with session_scope() as s:
  num=(s.scalar(select(func.max(ReciboAvulso.numero)).where(ReciboAvulso.tesouraria_id==tid())) or 0)+1
  x=ReciboAvulso(tesouraria_id=tid(),numero=num,favorecido_id=fid,nome=nome,cpf=cpf or None,rg=rg or None,telefone=tel or None,endereco=end or None,data_recibo=dt,competencia=comp,valor=Decimal(str(valor)),servico=servico,status='EMITIDO',criado_por=uid)
  if doc:x.documento_nome=doc.name;x.documento_mime=doc.type;x.documento_blob=doc.getvalue()
  if pag:x.comprovante_nome=pag.name;x.comprovante_mime=pag.type;x.comprovante_blob=pag.getvalue()
  s.add(x);s.flush();return x.id

def pdf_recibo(rid):
 from io import BytesIO
 from reportlab.pdfgen import canvas
 from reportlab.lib.pagesizes import A4
 from reportlab.lib.utils import ImageReader
 from reportlab.pdfbase.pdfmetrics import stringWidth
 from models.entities import Tesouraria
 with session_scope() as s:
  r=s.get(ReciboAvulso,rid); t=s.get(Tesouraria,r.tesouraria_id)
  dados={k:getattr(r,k) for k in ['numero','nome','cpf','rg','telefone','endereco','data_recibo','competencia','valor','servico','documento_blob','comprovante_blob']}; inst={'nome':t.nome,'cnpj':t.cnpj or '','cidade':t.cidade or '','uf':t.uf or ''}
 b=BytesIO();c=canvas.Canvas(b,pagesize=A4);W,H=A4
 def wrap(txt,x,y,maxw,font='Helvetica',size=9,leading=12):
  c.setFont(font,size); words=str(txt).split();line=''
  for w in words:
   test=(line+' '+w).strip()
   if stringWidth(test,font,size)>maxw:
    c.drawString(x,y,line);y-=leading;line=w
   else:line=test
  if line:c.drawString(x,y,line);y-=leading
  return y
 x=48; top=H-55; width=W-96
 c.rect(x,top-205,width,205);c.setFont('Helvetica-Bold',13);c.drawCentredString(W/2,top-18,'RECIBO - PAGAMENTO')
 c.setFont('Helvetica-Bold',9);c.drawString(x+15,top-38,'Valor   R$');c.drawString(x+120,top-38,f"{float(dados['valor']):,.2f}".replace(',','X').replace('.',',').replace('X','.'))
 texto=(f"Eu, {dados['nome']}, portador(a) do RG nº {dados['rg'] or '________________'}, CPF nº {dados['cpf'] or '________________'}, "
        f"Telefone {dados['telefone'] or '________________'}, residente em {dados['endereco'] or '________________'}, declaro ter recebido de {inst['nome']}, "
        f"CNPJ nº {inst['cnpj']}, a importância acima mencionada, referente aos serviços prestados como {dados['servico']}, referente à competência {dados['competencia']}.")
 y=wrap(texto,x+15,top-62,width-30,size=8.5,leading=11)
 c.line(x+15,top-166,x+330,top-166);c.setFont('Helvetica',7);c.drawString(x+40,top-178,'Assinatura manual ou digital do prestador')
 c.setFont('Helvetica-Bold',8);c.drawRightString(x+width-15,top-168,f"{inst['cidade']}-{inst['uf']}, {dados['data_recibo'].strftime('%d/%m/%Y')}");c.drawRightString(x+width-15,top-184,f"CÓD.: {dados['numero']:04d}")
 def img(blob,y0,h,label):
  c.rect(x,y0,width,h);c.setFont('Helvetica-Bold',8);c.drawString(x+8,y0+h-13,label)
  if blob:
   try:c.drawImage(ImageReader(BytesIO(blob)),x+20,y0+15,width-40,h-35,preserveAspectRatio=True,anchor='c')
   except Exception:pass
 img(dados['documento_blob'],top-405,185,'DOCUMENTO DO PRESTADOR')
 img(dados['comprovante_blob'],top-610,185,'COMPROVANTE DE PAGAMENTO')
 c.rect(x,35,width,70); thirds=width/3
 for i in [1,2]:c.line(x+thirds*i,35,x+thirds*i,105)
 for i,title in enumerate(['Dados Gerais','Vistos / Diretor','Tesouraria']):
  xx=x+thirds*i;c.setFont('Helvetica-Bold',8);c.drawCentredString(xx+thirds/2,92,title);c.line(xx+15,52,xx+thirds-15,52);c.setFont('Helvetica',7);c.drawCentredString(xx+thirds/2,42,'Assinatura')
 c.save();return b.getvalue()


# ---------------- V26.10: parâmetros, vigências e governança ----------------
def parametros_folha(grupo=None):
 with session_scope() as s:
  q=select(ParametroFolha).where(ParametroFolha.tesouraria_id==tid())
  if grupo and grupo!='TODOS': q=q.where(ParametroFolha.grupo==grupo)
  rows=s.scalars(q.order_by(ParametroFolha.grupo,ParametroFolha.chave,ParametroFolha.vigencia_inicio.desc())).all()
  return [{'id':x.id,'grupo':x.grupo,'chave':x.chave,'descricao':x.descricao,'valor':float(x.valor_decimal) if x.valor_decimal is not None else x.valor_texto,
           'início':x.vigencia_inicio.strftime('%d/%m/%Y'),'fim':x.vigencia_fim.strftime('%d/%m/%Y') if x.vigencia_fim else '—','ativo':x.ativo,'fonte':x.fonte_referencia or ''} for x in rows]

def salvar_parametro(grupo,chave,descricao,valor_decimal,valor_texto,inicio,fim,fonte,obs,uid):
 from services.auditoria import registrar_auditoria
 with session_scope() as s:
  x=ParametroFolha(tesouraria_id=tid(),grupo=grupo,chave=chave.strip().upper(),descricao=descricao.strip(),valor_decimal=Decimal(str(valor_decimal)) if valor_decimal not in (None,'') else None,
   valor_texto=(valor_texto or '').strip() or None,vigencia_inicio=inicio,vigencia_fim=fim,fonte_referencia=(fonte or '').strip() or None,observacao=(obs or '').strip() or None,criado_por=uid)
  s.add(x);s.flush();rid=x.id
 registrar_auditoria(uid,'CRIAR_VIGENCIA','PARAMETRO_FOLHA',rid,novo={'grupo':grupo,'chave':chave,'inicio':str(inicio),'fim':str(fim) if fim else None})
 return rid

def parametros_vigentes_em(dia):
 with session_scope() as s:
  rows=s.scalars(select(ParametroFolha).where(ParametroFolha.tesouraria_id==tid(),ParametroFolha.ativo==True,
      ParametroFolha.vigencia_inicio<=dia,or_(ParametroFolha.vigencia_fim==None,ParametroFolha.vigencia_fim>=dia))).all()
  return rows

def alertas_parametros(competencia):
 try:
  mes,ano=map(int,competencia.split('/')); from datetime import date as _d; dia=_d(ano,mes,1)
 except Exception:return ['Competência inválida. Use MM/AAAA.']
 vig=parametros_vigentes_em(dia); grupos={x.grupo for x in vig}; alertas=[]
 essenciais={'PISO','INSS','IRRF'}
 for g in sorted(essenciais-grupos):alertas.append(f'Não há parâmetro vigente do grupo {g} para {competencia}.')
 return alertas

def historico_salarial(trabalhador_id=None):
 with session_scope() as s:
  q=select(HistoricoSalarial).where(HistoricoSalarial.tesouraria_id==tid())
  if trabalhador_id:q=q.where(HistoricoSalarial.trabalhador_id==trabalhador_id)
  rows=s.scalars(q.order_by(HistoricoSalarial.vigencia_inicio.desc())).all()
  nomes={x.id:x.nome for x in s.scalars(select(TrabalhadorFolha).where(TrabalhadorFolha.tesouraria_id==tid())).all()}
  return [{'id':x.id,'trabalhador':nomes.get(x.trabalhador_id,str(x.trabalhador_id)),'salário':float(x.salario),'início':x.vigencia_inicio.strftime('%d/%m/%Y'),
           'fim':x.vigencia_fim.strftime('%d/%m/%Y') if x.vigencia_fim else '—','motivo':x.motivo or ''} for x in rows]

def nova_vigencia_salarial(trabalhador_id,salario,inicio,motivo,uid):
 from datetime import timedelta
 from services.auditoria import registrar_auditoria
 with session_scope() as s:
  anteriores=s.scalars(select(HistoricoSalarial).where(HistoricoSalarial.tesouraria_id==tid(),HistoricoSalarial.trabalhador_id==trabalhador_id,HistoricoSalarial.vigencia_fim==None)).all()
  for a in anteriores:
   if a.vigencia_inicio < inicio:a.vigencia_fim=inicio-timedelta(days=1)
  x=HistoricoSalarial(tesouraria_id=tid(),trabalhador_id=trabalhador_id,salario=Decimal(str(salario)),vigencia_inicio=inicio,motivo=motivo or None,criado_por=uid);s.add(x)
  t=s.get(TrabalhadorFolha,trabalhador_id);t.salario_base=Decimal(str(salario));s.flush();rid=x.id
 registrar_auditoria(uid,'NOVA_VIGENCIA_SALARIAL','TRABALHADOR_FOLHA',trabalhador_id,novo={'salario':salario,'inicio':str(inicio),'motivo':motivo})
 return rid

def calendario_folha():
 with session_scope() as s:
  rows=s.scalars(select(CalendarioFolha).where(CalendarioFolha.tesouraria_id==tid()).order_by(CalendarioFolha.competencia.desc())).all()
  f=lambda d:d.strftime('%d/%m/%Y') if d else '—'
  return [{'id':x.id,'competência':x.competencia,'tipo':x.tipo,'abertura':f(x.data_abertura),'limite eventos':f(x.data_limite_eventos),'conferência':f(x.data_conferencia),'fechamento':f(x.data_fechamento),'pagamento':f(x.data_pagamento_prevista)} for x in rows]

def salvar_calendario(comp,tipo,abertura,limite,conferencia,fechamento,pagamento,obs):
 with session_scope() as s:
  x=s.scalar(select(CalendarioFolha).where(CalendarioFolha.tesouraria_id==tid(),CalendarioFolha.competencia==comp,CalendarioFolha.tipo==tipo))
  if not x:x=CalendarioFolha(tesouraria_id=tid(),competencia=comp,tipo=tipo);s.add(x)
  x.data_abertura=abertura;x.data_limite_eventos=limite;x.data_conferencia=conferencia;x.data_fechamento=fechamento;x.data_pagamento_prevista=pagamento;x.observacao=obs or None;s.flush();return x.id

CHECKLIST_PADRAO=['Parâmetros e vigências conferidos','Trabalhadores ativos conferidos','Eventos e valores variáveis conferidos','Contas bancárias/dados de pagamento conferidos','Centro de custo/classificação conferidos','Encargos revisados','Folha comparada com competência anterior','Aprovação responsável registrada']
def checklist_folha(folha_id):
 with session_scope() as s:
  rows=s.scalars(select(ChecklistFolha).where(ChecklistFolha.tesouraria_id==tid(),ChecklistFolha.folha_id==folha_id).order_by(ChecklistFolha.id)).all()
  if not rows:
   for item in CHECKLIST_PADRAO:s.add(ChecklistFolha(tesouraria_id=tid(),folha_id=folha_id,item=item))
   s.flush();rows=s.scalars(select(ChecklistFolha).where(ChecklistFolha.tesouraria_id==tid(),ChecklistFolha.folha_id==folha_id).order_by(ChecklistFolha.id)).all()
  return [{'id':x.id,'item':x.item,'concluído':bool(x.concluido),'observação':x.observacao or ''} for x in rows]

def atualizar_checklist(item_id,concluido,obs,uid):
 with session_scope() as s:
  x=s.get(ChecklistFolha,item_id)
  if not x or x.tesouraria_id!=tid():raise ValueError('Item inválido.')
  x.concluido=bool(concluido);x.observacao=obs or None;x.atualizado_por=uid

def transicionar_folha(folha_id,novo_status,uid):
 import json
 from services.auditoria import registrar_auditoria
 ordem={'RASCUNHO':['EM_CONFERENCIA'],'EM_CONFERENCIA':['APROVADA','RASCUNHO'],'APROVADA':['FECHADA','EM_CONFERENCIA'],'FECHADA':['PAGA'],'PAGA':[]}
 with session_scope() as s:
  f=s.get(FolhaCompetencia,folha_id)
  if not f or f.tesouraria_id!=tid():raise ValueError('Folha inválida.')
  anterior=f.status
  if novo_status not in ordem.get(anterior,[]):raise ValueError(f'Transição {anterior} → {novo_status} não permitida.')
  if novo_status=='FECHADA':
   itens=s.scalars(select(ChecklistFolha).where(ChecklistFolha.tesouraria_id==tid(),ChecklistFolha.folha_id==folha_id)).all()
   if not itens or not all(x.concluido for x in itens):raise ValueError('Conclua todo o Checklist de Fechamento antes de fechar a folha.')
   params=parametros_folha()
   snap={'folha':{'id':f.id,'competencia':f.competencia,'tipo':f.tipo},'parametros':params,'checklist':[{'item':x.item,'concluido':x.concluido,'observacao':x.observacao} for x in itens]}
   s.add(FolhaSnapshot(tesouraria_id=tid(),folha_id=f.id,etapa='FECHAMENTO',snapshot_json=json.dumps(snap,ensure_ascii=False,default=str),criado_por=uid))
  f.status=novo_status
 registrar_auditoria(uid,'TRANSICAO_FOLHA','FOLHA_COMPETENCIA',folha_id,anterior={'status':anterior},novo={'status':novo_status})

def snapshots_folha(folha_id):
 with session_scope() as s:
  rows=s.scalars(select(FolhaSnapshot).where(FolhaSnapshot.tesouraria_id==tid(),FolhaSnapshot.folha_id==folha_id).order_by(FolhaSnapshot.criado_em.desc())).all()
  return [{'id':x.id,'etapa':x.etapa,'data':x.criado_em.strftime('%d/%m/%Y %H:%M'),'criado_por':x.criado_por} for x in rows]
