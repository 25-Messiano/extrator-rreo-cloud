from __future__ import annotations
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from database.db import session_scope
from models.entities import PrestacaoContas, Tesouraria, Lancamento
from services.financeiro import STATUS_OFICIAIS
from services.auditoria import registrar_auditoria

STATUS_DECISAO=("APROVADA","REJEITADA","DEVOLVIDA")

def _filtro_comp(comp):
    return Lancamento.competencia==comp

def criar_prestacao(tesouraria_id:int,competencia:str,usuario_id:int,observacao=""):
    with session_scope() as s:
        versao=(s.scalar(select(func.max(PrestacaoContas.versao)).where(PrestacaoContas.tesouraria_id==tesouraria_id,PrestacaoContas.competencia==competencia)) or 0)+1
        rows=s.scalars(select(Lancamento).where(Lancamento.tesouraria_id==tesouraria_id,_filtro_comp(competencia),Lancamento.status.in_(STATUS_OFICIAIS))).all()
        ent=sum((Decimal(x.valor) for x in rows if x.natureza=="ENTRADA"),Decimal("0")); sai=sum((Decimal(x.valor) for x in rows if x.natureza=="SAIDA"),Decimal("0"))
        snap={"competencia":competencia,"quantidade":len(rows),"entradas":str(ent),"saidas":str(sai),"resultado":str(ent-sai),"lancamentos":[x.id for x in rows]}
        p=PrestacaoContas(tesouraria_id=tesouraria_id,competencia=competencia,versao=versao,status="ENVIADA",snapshot_json=json.dumps(snap,ensure_ascii=False),observacao_envio=(observacao or "").strip() or None,enviada_por=usuario_id,enviada_em=datetime.utcnow()); s.add(p); s.flush(); rid=p.id
    registrar_auditoria(usuario_id,"ENVIAR_PRESTACAO","prestacoes_contas",rid,novo={"tesouraria_id":tesouraria_id,"competencia":competencia,"versao":versao})
    return rid

def listar_prestacoes(tesouraria_id=None,status=None):
    with session_scope() as s:
        q=select(PrestacaoContas,Tesouraria).join(Tesouraria,Tesouraria.id==PrestacaoContas.tesouraria_id)
        if tesouraria_id:q=q.where(PrestacaoContas.tesouraria_id==tesouraria_id)
        if status:q=q.where(PrestacaoContas.status==status)
        q=q.order_by(PrestacaoContas.criada_em.desc())
        out=[]
        for x,t in s.execute(q).all():
            try:snap=json.loads(x.snapshot_json or "{}")
            except Exception:snap={}
            out.append({"id":x.id,"tesouraria_id":x.tesouraria_id,"tesouraria":t.nome,"competencia":x.competencia,"versao":x.versao,"status":x.status,"entradas":snap.get("entradas","0"),"saidas":snap.get("saidas","0"),"resultado":snap.get("resultado","0"),"quantidade":snap.get("quantidade",0),"observacao":x.observacao_envio or "","parecer":x.parecer_auditoria or "","enviada_em":x.enviada_em,"analisada_em":x.analisada_em})
        return out

def decidir_prestacao(prestacao_id:int,decisao:str,parecer:str,usuario_id:int):
    decisao=decisao.upper().strip(); parecer=(parecer or "").strip()
    if decisao not in STATUS_DECISAO: raise ValueError("Decisão inválida.")
    if not parecer: raise ValueError("Informe o parecer/justificativa da auditoria.")
    with session_scope() as s:
        p=s.get(PrestacaoContas,prestacao_id)
        if not p: raise ValueError("Prestação não encontrada.")
        ant={"status":p.status}; p.status=decisao; p.parecer_auditoria=parecer; p.analisada_por=usuario_id; p.analisada_em=datetime.utcnow(); tid=p.tesouraria_id
    registrar_auditoria(usuario_id,"DECIDIR_PRESTACAO","prestacoes_contas",prestacao_id,ant,{"status":decisao,"parecer":parecer},parecer)
    return tid
