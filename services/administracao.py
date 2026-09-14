from __future__ import annotations
import json, os, shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select, func, or_, and_, Integer
from database.db import session_scope, engine
from models.entities import (ContaFinanceira, SaldoInicial, CentroCusto, Patrimonio, PatrimonioMovimento,
    FechamentoMensal, Lancamento, ImportacaoExtrato, ItemConferencia, Conciliacao, Usuario, Auditoria,
    AcessoLog, ConfiguracaoSistema, CodigoAPLB, Favorecido)
from services.auditoria import registrar_auditoria
from services.financeiro import STATUS_OFICIAIS, saldos
from services.tenancy import get_active_tesouraria_id, tenant_where

TODAS_ACOES=["LANCAR","CORRIGIR","IMPORTAR","CONFERIR","CONCILIAR","CONSULTAR","RELATORIOS","PATRIMONIO","FLUXO","FECHAR","CADASTROS","USUARIOS","CONFIGURAR","AUDITORIA","BACKUP","MONITORAR"]

def atualizar_conta(conta_id,nome,tipo,banco=None,agencia=None,conta=None,ativo=True,usuario_id=None):
    with session_scope() as s:
        x=s.get(ContaFinanceira,conta_id)
        if not x or x.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Conta não encontrada nesta tesouraria.")
        ant={"nome":x.nome,"tipo":x.tipo,"banco":x.banco,"agencia":x.agencia,"conta":x.conta,"ativo":x.ativo}
        x.nome=nome.strip();x.tipo=tipo;x.banco=(banco or "").strip() or None;x.agencia=(agencia or "").strip() or None;x.conta=(conta or "").strip() or None;x.ativo=bool(ativo)
        novo={"nome":x.nome,"tipo":x.tipo,"banco":x.banco,"agencia":x.agencia,"conta":x.conta,"ativo":x.ativo}
    registrar_auditoria(usuario_id,"ALTERAR_CONTA","contas_financeiras",conta_id,ant,novo)

def salvar_saldo_inicial(conta_id,data_ref,valor,observacao=None,usuario_id=None):
    with session_scope() as s:
        x=s.scalar(select(SaldoInicial).where(SaldoInicial.conta_financeira_id==conta_id,SaldoInicial.data_referencia==data_ref, tenant_where(SaldoInicial.tesouraria_id)))
        ant=None
        if x: ant={"valor":str(x.valor),"observacao":x.observacao};x.valor=Decimal(str(valor));x.observacao=observacao
        else: x=SaldoInicial(tesouraria_id=get_active_tesouraria_id(),conta_financeira_id=conta_id,data_referencia=data_ref,valor=Decimal(str(valor)),observacao=observacao);s.add(x);s.flush()
        rid=x.id
    registrar_auditoria(usuario_id,"SALDO_INICIAL","saldos_iniciais",rid,ant,{"conta_id":conta_id,"data":str(data_ref),"valor":str(valor)})
    return rid

def listar_saldos_iniciais():
    with session_scope() as s:
        rows=s.execute(select(SaldoInicial,ContaFinanceira).join(ContaFinanceira,ContaFinanceira.id==SaldoInicial.conta_financeira_id).where(tenant_where(SaldoInicial.tesouraria_id)).order_by(SaldoInicial.data_referencia.desc())).all()
        return [{"id":x.id,"conta":c.nome,"tipo":c.tipo,"data":x.data_referencia,"valor":float(x.valor),"observacao":x.observacao or ""} for x,c in rows]

def atualizar_patrimonio(pid, **campos):
    usuario_id = campos.pop("usuario_id", None)
    obs = campos.pop("observacao_movimento", None)
    data_mov = campos.pop("data_movimento", None) or date.today()
    with session_scope() as s:
        p = s.get(Patrimonio, pid)
        if not p or p.tesouraria_id != get_active_tesouraria_id():
            raise ValueError("Bem patrimonial não encontrado nesta tesouraria.")
        ant = {k: getattr(p, k, None) for k in [
            "numero_patrimonial", "descricao", "categoria", "data_aquisicao", "valor", "fornecedor", "fornecedor_id",
            "nota_fiscal", "local_uso", "responsavel", "estado_conservacao", "vida_util_anos", "situacao"
        ]}
        local_ant = p.local_uso
        resp_ant = p.responsavel
        sit_ant = p.situacao
        for k, v in campos.items():
            if hasattr(p, k):
                setattr(p, k, v)
        novo = {k: getattr(p, k, None) for k in ant}

        mudou = local_ant != p.local_uso or resp_ant != p.responsavel or sit_ant != p.situacao
        if mudou:
            if sit_ant != p.situacao:
                tipo_por_situacao = {
                    "OBSOLETO": "OBSOLESCENCIA",
                    "BAIXADO": "BAIXA",
                    "TRANSFERIDO": "TRANSFERENCIA",
                    "EM_MANUTENCAO": "MANUTENCAO",
                    "INATIVO": "INATIVACAO",
                    "ATIVO": "REATIVACAO",
                }
                if sit_ant == "EM_MANUTENCAO" and p.situacao == "ATIVO":
                    tipo = "RETORNO_MANUTENCAO"
                else:
                    tipo = tipo_por_situacao.get(p.situacao, "ALTERACAO_SITUACAO")
            else:
                tipo = "TRANSFERENCIA/ALTERACAO"
            s.add(PatrimonioMovimento(
                patrimonio_id=pid, tipo=tipo, data_movimento=data_mov,
                local_anterior=local_ant, local_novo=p.local_uso,
                responsavel_anterior=resp_ant, responsavel_novo=p.responsavel,
                situacao_anterior=sit_ant, situacao_nova=p.situacao,
                observacao=obs, usuario_id=usuario_id,
            ))
    registrar_auditoria(usuario_id, "ALTERAR_PATRIMONIO", "patrimonio", pid, ant, novo, motivo=obs)


def listar_movimentos_patrimonio(pid=None):
    with session_scope() as s:
        q = (
            select(PatrimonioMovimento)
            .join(Patrimonio, Patrimonio.id == PatrimonioMovimento.patrimonio_id)
            .where(tenant_where(Patrimonio.tesouraria_id))
            .order_by(PatrimonioMovimento.data_movimento.desc(), PatrimonioMovimento.criado_em.desc())
        )
        if pid:
            q = q.where(PatrimonioMovimento.patrimonio_id == pid)
        return [{
            "id": x.id, "patrimonio_id": x.patrimonio_id, "tipo": x.tipo, "data": x.data_movimento,
            "local_anterior": x.local_anterior or "", "local_novo": x.local_novo or "",
            "responsavel_anterior": x.responsavel_anterior or "", "responsavel_novo": x.responsavel_novo or "",
            "situacao_anterior": x.situacao_anterior or "", "situacao_nova": x.situacao_nova or "",
            "observacao": x.observacao or "",
        } for x in s.scalars(q).all()]


def status_fechamentos(ano=None):
    with session_scope() as s:
        q=select(FechamentoMensal).where(tenant_where(FechamentoMensal.tesouraria_id)).order_by(FechamentoMensal.ano.desc(),FechamentoMensal.mes.desc())
        if ano:q=q.where(FechamentoMensal.ano==ano)
        return [{"ano":x.ano,"mes":x.mes,"status":x.status,"fechado_em":x.fechado_em,"reaberto_em":x.reaberto_em,"motivo_reabertura":x.motivo_reabertura or ""} for x in s.scalars(q).all()]

def diagnostico_fechamento(ano,mes):
    """V15: pré-fechamento por competência, com bloqueios e alertas financeiros."""
    comp=f"{ano:04d}-{mes:02d}"; ini=date(ano,mes,1); fim=date(ano+1,1,1) if mes==12 else date(ano,mes+1,1)
    filtro_l=or_(Lancamento.competencia==comp,and_(Lancamento.competencia.is_(None),Lancamento.data_movimento>=ini,Lancamento.data_movimento<fim))
    with session_scope() as s:
        fech=s.scalar(select(FechamentoMensal).where(FechamentoMensal.ano==ano,FechamentoMensal.mes==mes, tenant_where(FechamentoMensal.tesouraria_id)))
        pend_imp=s.scalar(select(func.count(ImportacaoExtrato.id)).where(ImportacaoExtrato.competencia==comp,ImportacaoExtrato.status.in_(["EM_CONFERENCIA","PENDENTE"]), tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        pend_it=s.scalar(select(func.count(ItemConferencia.id)).join(ImportacaoExtrato,ImportacaoExtrato.id==ItemConferencia.importacao_id).where(ImportacaoExtrato.competencia==comp,ItemConferencia.status.in_(["PENDENTE","CORRIGIR","CONFERIR_DUPLICIDADE"]), tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        pend_l=s.scalar(select(func.count(Lancamento.id)).where(filtro_l,Lancamento.status.in_(["RASCUNHO","EM_CONFERENCIA"]), tenant_where(Lancamento.tesouraria_id))) or 0
        qtd=s.scalar(select(func.count(Lancamento.id)).where(filtro_l,Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))) or 0
        entradas=s.scalar(select(func.coalesce(func.sum(Lancamento.valor),0)).where(filtro_l,Lancamento.natureza=="ENTRADA",Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))) or 0
        saidas=s.scalar(select(func.coalesce(func.sum(Lancamento.valor),0)).where(filtro_l,Lancamento.natureza=="SAIDA",Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))) or 0
        banco_ids=list(s.scalars(select(ContaFinanceira.id).where(ContaFinanceira.tipo=="BANCO",ContaFinanceira.ativo.is_(True), tenant_where(ContaFinanceira.tesouraria_id))).all())
        lanc_b=list(s.scalars(select(Lancamento).where(filtro_l,Lancamento.conta_financeira_id.in_(banco_ids),Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))).all()) if banco_ids else []
        cons={x.lancamento_id:x.status for x in s.scalars(select(Conciliacao).where(Conciliacao.lancamento_id.in_([l.id for l in lanc_b]))).all()} if lanc_b else {}
        nao_conc=sum(1 for l in lanc_b if cons.get(l.id)!="CONCILIADO")
    bloqueios=[]
    if pend_imp:bloqueios.append(f"{pend_imp} importação(ões) em conferência")
    if pend_it:bloqueios.append(f"{pend_it} item(ns) de extrato pendente(s)")
    if pend_l:bloqueios.append(f"{pend_l} lançamento(s) não aprovado(s)")
    return {"competencia":comp,"status_periodo":fech.status if fech else "ABERTO","importacoes_em_conferencia":int(pend_imp),"itens_pendentes":int(pend_it),"lancamentos_pendentes":int(pend_l),"movimentos_bancarios_nao_conciliados":int(nao_conc),"quantidade_lancamentos":int(qtd),"total_entradas":float(entradas),"total_saidas":float(saidas),"resultado":float(entradas-saidas),"bloqueios":bloqueios,"pode_fechar":not bloqueios and (not fech or fech.status!="FECHADO")}


def listar_usuarios():
    with session_scope() as s:
        return [{"id":u.id,"nome":u.nome,"login":u.login,"email":u.email or "","perfil":u.perfil,"ativo":u.ativo,"ultimo_acesso":u.ultimo_acesso,"permissoes":json.loads(u.permissoes_json) if u.permissoes_json else []} for u in s.scalars(select(Usuario).order_by(Usuario.nome)).all()]

def atualizar_usuario(uid,perfil=None,ativo=None,permissoes=None,usuario_id=None):
    from services.security import PERFIS_VALIDOS, eh_admin_ativo
    if not eh_admin_ativo(usuario_id):
        raise PermissionError("Operação permitida somente a Administrador ativo.")
    if perfil is not None and perfil not in PERFIS_VALIDOS:
        raise ValueError("Perfil inválido.")
    if permissoes is not None:
        invalidas=set(permissoes)-set(TODAS_ACOES)
        if invalidas:
            raise ValueError("Permissão(ões) inválida(s): " + ", ".join(sorted(invalidas)))
    with session_scope() as s:
        u=s.get(Usuario,uid)
        if not u: raise ValueError("Usuário não encontrado.")
        ant={"perfil":u.perfil,"ativo":u.ativo,"permissoes_json":u.permissoes_json}
        novo_perfil=perfil if perfil is not None else u.perfil
        novo_ativo=bool(ativo) if ativo is not None else bool(u.ativo)
        # Nunca permitir remover o último administrador ativo do sistema.
        vai_deixar_de_ser_admin=(u.perfil=="ADMINISTRADOR" and u.ativo and (novo_perfil!="ADMINISTRADOR" or not novo_ativo))
        if vai_deixar_de_ser_admin:
            outros=s.scalar(select(func.count(Usuario.id)).where(Usuario.id!=u.id,Usuario.perfil=="ADMINISTRADOR",Usuario.ativo.is_(True))) or 0
            if int(outros)==0:
                raise ValueError("Não é permitido desativar ou rebaixar o último Administrador ativo.")
        if perfil is not None:u.perfil=perfil
        if ativo is not None:u.ativo=novo_ativo
        if permissoes is not None:u.permissoes_json=(json.dumps(sorted(set(permissoes)),ensure_ascii=False) if permissoes else None)
        novo={"perfil":u.perfil,"ativo":u.ativo,"permissoes_json":u.permissoes_json}
    registrar_auditoria(usuario_id,"ALTERAR_USUARIO","usuarios",uid,ant,novo)

def listar_auditoria_filtrada(inicio=None,fim=None,acao=None,entidade=None,usuario_id=None,limit=5000):
    with session_scope() as s:
        q=select(Auditoria,Usuario).outerjoin(Usuario,Usuario.id==Auditoria.usuario_id).where(tenant_where(Auditoria.tesouraria_id))
        if inicio:q=q.where(Auditoria.criado_em>=datetime.combine(inicio,datetime.min.time()))
        if fim:q=q.where(Auditoria.criado_em<datetime.combine(fim+timedelta(days=1),datetime.min.time()))
        if acao:q=q.where(Auditoria.acao==acao)
        if entidade:q=q.where(Auditoria.entidade==entidade)
        if usuario_id:q=q.where(Auditoria.usuario_id==usuario_id)
        rows=s.execute(q.order_by(Auditoria.criado_em.desc()).limit(limit)).all()
        return [{"id":a.id,"data_hora":a.criado_em,"usuario":u.nome if u else "Sistema","acao":a.acao,"entidade":a.entidade,"registro_id":a.registro_id,"motivo":a.motivo or "","anterior":a.anterior_json or "","novo":a.novo_json or ""} for a,u in rows]

def get_config(chave,default=None):
    with session_scope() as s:
        x=s.get(ConfiguracaoSistema,chave); return x.valor if x else default

def set_config(chave,valor,usuario_id=None):
    with session_scope() as s:
        x=s.get(ConfiguracaoSistema,chave); ant=x.valor if x else None
        if not x:x=ConfiguracaoSistema(chave=chave);s.add(x)
        x.valor=str(valor) if valor is not None else None;x.atualizado_em=datetime.utcnow()
    registrar_auditoria(usuario_id,"CONFIGURAR","configuracoes_sistema",motivo=chave,anterior={"valor":ant},novo={"valor":valor})

def listar_configs():
    with session_scope() as s:return [{"chave":x.chave,"valor":x.valor,"atualizado_em":x.atualizado_em} for x in s.scalars(select(ConfiguracaoSistema).order_by(ConfiguracaoSistema.chave)).all()]

def conciliacao_automatica(competencia=None,usuario_id=None):
    with session_scope() as s:
        qi=select(ItemConferencia,ImportacaoExtrato).join(ImportacaoExtrato,ImportacaoExtrato.id==ItemConferencia.importacao_id).where(ItemConferencia.status.in_(["LIBERADO","APROVADO"]), tenant_where(ImportacaoExtrato.tesouraria_id))
        if competencia:qi=qi.where(ImportacaoExtrato.competencia==competencia)
        itens=s.execute(qi).all(); criadas=0;amb=0
        for item,imp in itens:
            ql=select(Lancamento).where(Lancamento.data_movimento==item.data_movimento,Lancamento.valor==item.valor,Lancamento.natureza==item.natureza,Lancamento.origem_bc==item.origem_bc,Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))
            if imp.conta_financeira_id: ql=ql.where(Lancamento.conta_financeira_id==imp.conta_financeira_id)
            cand=s.scalars(ql).all()
            if item.lancamento_gerado_id:cand=[x for x in cand if x.id==item.lancamento_gerado_id] or cand
            if len(cand)==1:
                l=cand[0]; c=s.scalar(select(Conciliacao).where(Conciliacao.lancamento_id==l.id))
                if not c:c=Conciliacao(lancamento_id=l.id,importacao_item_id=item.id);s.add(c)
                c.status="CONCILIADO";c.conciliado_por=usuario_id;c.conciliado_em=datetime.utcnow();c.observacao="Conciliação automática por data/valor/natureza/conta.";l.status="CONCILIADO" if l.status=="APROVADO" else l.status;criadas+=1
            elif len(cand)>1:amb+=1
    registrar_auditoria(usuario_id,"CONCILIACAO_AUTOMATICA","conciliacoes",novo={"conciliadas":criadas,"ambiguas":amb,"competencia":competencia})
    return criadas,amb

def _dt_iso(v):
    return v.isoformat() if v else None

def monitoramento_resumo():
    """V17: painel somente leitura de saúde, operação, segurança e continuidade."""
    agora=datetime.utcnow(); d24=agora-timedelta(days=1); d7=agora-timedelta(days=7); d30=agora-timedelta(days=30)
    with session_scope() as s:
        total_l=s.scalar(select(func.count(Lancamento.id)).where(tenant_where(Lancamento.tesouraria_id))) or 0
        of=s.scalar(select(func.count(Lancamento.id)).where(Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))) or 0
        canc=s.scalar(select(func.count(Lancamento.id)).where(Lancamento.status=="CANCELADO", tenant_where(Lancamento.tesouraria_id))) or 0
        pend=s.scalar(select(func.count(ItemConferencia.id)).join(ImportacaoExtrato, ImportacaoExtrato.id==ItemConferencia.importacao_id).where(ItemConferencia.status.in_(["PENDENTE","CORRIGIR","CONFERIR_DUPLICIDADE"]), tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        imp=s.scalar(select(func.count(ImportacaoExtrato.id)).where(ImportacaoExtrato.status.in_(["EM_CONFERENCIA","PENDENTE"]), tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        acessos24=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(True),AcessoLog.criado_em>=d24)) or 0
        falhas24=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(False),AcessoLog.criado_em>=d24)) or 0
        acessos7=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(True),AcessoLog.criado_em>=d7)) or 0
        falhas7=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(False),AcessoLog.criado_em>=d7)) or 0
        acessos30=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(True),AcessoLog.criado_em>=d30)) or 0
        falhas30=s.scalar(select(func.count(AcessoLog.id)).where(AcessoLog.sucesso.is_(False),AcessoLog.criado_em>=d30)) or 0
        usuarios=s.scalar(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True))) or 0
        ultimo_acesso=s.scalar(select(func.max(AcessoLog.criado_em)).where(AcessoLog.sucesso.is_(True)))
        ultima_falha=s.scalar(select(func.max(AcessoLog.criado_em)).where(AcessoLog.sucesso.is_(False)))
        ultimo_fech=s.scalar(select(FechamentoMensal).where(FechamentoMensal.status=="FECHADO", tenant_where(FechamentoMensal.tesouraria_id)).order_by(FechamentoMensal.fechado_em.desc()).limit(1))
        fechados=s.scalar(select(func.count(FechamentoMensal.id)).where(FechamentoMensal.status=="FECHADO", tenant_where(FechamentoMensal.tesouraria_id))) or 0
        conciliados=s.scalar(select(func.count(Conciliacao.id)).join(Lancamento, Lancamento.id==Conciliacao.lancamento_id).where(Conciliacao.status=="CONCILIADO", tenant_where(Lancamento.tesouraria_id))) or 0
        ai30=s.scalar(select(func.count(ItemConferencia.id)).join(ImportacaoExtrato, ImportacaoExtrato.id==ItemConferencia.importacao_id).where(ItemConferencia.origem_classificacao=="OPENAI", tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        dias=s.execute(select(func.date(AcessoLog.criado_em),func.sum(AcessoLog.sucesso.cast(Integer)),func.sum((~AcessoLog.sucesso).cast(Integer))).where(AcessoLog.criado_em>=d7).group_by(func.date(AcessoLog.criado_em)).order_by(func.date(AcessoLog.criado_em))).all()
    try:
        from services.backup import status_ultimo_backup
        ub=status_ultimo_backup()
    except Exception:
        ub=None
    backup_age=None
    if ub and ub.get("gerado_em"):
        try: backup_age=(agora-datetime.fromisoformat(ub["gerado_em"].replace("Z",""))).total_seconds()/3600
        except Exception: pass
    backend=engine.url.get_backend_name()
    db_ok=backend=="postgresql"
    backup_ok=backup_age is not None and backup_age<=36
    backup_warn=backup_age is not None and backup_age<=72
    ai_config=bool(os.getenv("OPENAI_API_KEY","").strip())
    cloud_backup=bool(os.getenv("CLOUD_BACKUP_BUCKET","").strip() and os.getenv("CLOUD_BACKUP_ACCESS_KEY","").strip() and os.getenv("CLOUD_BACKUP_SECRET_KEY","").strip())
    alertas=[]
    if not db_ok: alertas.append({"nivel":"CRITICO","titulo":"Banco fora do PostgreSQL Cloud","detalhe":f"Backend atual: {backend}."})
    if not ub: alertas.append({"nivel":"CRITICO","titulo":"Backup não localizado","detalhe":"Nenhum backup automático foi localizado nesta instância."})
    elif not backup_warn: alertas.append({"nivel":"CRITICO","titulo":"Backup desatualizado","detalhe":f"Último backup há {backup_age:.1f} horas."})
    elif not backup_ok: alertas.append({"nivel":"ATENCAO","titulo":"Backup precisa renovar","detalhe":f"Último backup há {backup_age:.1f} horas."})
    if not cloud_backup: alertas.append({"nivel":"ATENCAO","titulo":"Cópia externa do backup não configurada","detalhe":"O backup local existe, mas CLOUD_BACKUP_* ainda não forma um cofre externo permanente."})
    if pend: alertas.append({"nivel":"ATENCAO","titulo":"Itens aguardando conferência","detalhe":f"{int(pend)} item(ns) pendente(s)."})
    if imp: alertas.append({"nivel":"ATENCAO","titulo":"Extratos em conferência","detalhe":f"{int(imp)} importação(ões) ainda aberta(s)."})
    if falhas24>=5: alertas.append({"nivel":"CRITICO","titulo":"Muitas falhas de login","detalhe":f"{int(falhas24)} falhas nas últimas 24h."})
    elif falhas24: alertas.append({"nivel":"ATENCAO","titulo":"Falhas de login recentes","detalhe":f"{int(falhas24)} falha(s) nas últimas 24h."})
    saude={
        "Sistema":{"status":"NORMAL" if db_ok else "CRITICO","detalhe":"Aplicação operacional"},
        "PostgreSQL":{"status":"NORMAL" if db_ok else "CRITICO","detalhe":backend},
        "Backup":{"status":"NORMAL" if backup_ok else ("ATENCAO" if backup_warn else "CRITICO"),"detalhe":ub.get("gerado_em") if ub else "Sem backup"},
        "IA / OpenAI":{"status":"NORMAL" if ai_config else "ATENCAO","detalhe":"Configurada" if ai_config else "Chave não configurada"},
        "Backup externo":{"status":"NORMAL" if cloud_backup else "ATENCAO","detalhe":"Configurado" if cloud_backup else "Não configurado"},
    }
    return {"lancamentos_total":int(total_l),"lancamentos_oficiais":int(of),"cancelados":int(canc),"itens_conferencia_pendentes":int(pend),"importacoes_em_conferencia":int(imp),"acessos_24h":int(acessos24),"falhas_login_24h":int(falhas24),"acessos_7d":int(acessos7),"falhas_login_7d":int(falhas7),"acessos_30d":int(acessos30),"falhas_login_30d":int(falhas30),"usuarios_ativos":int(usuarios),"backend":backend,"ultimo_acesso":_dt_iso(ultimo_acesso),"ultima_falha_login":_dt_iso(ultima_falha),"fechamentos_ativos":int(fechados),"ultimo_fechamento":(f"{ultimo_fech.ano:04d}-{ultimo_fech.mes:02d}" if ultimo_fech else None),"conciliacoes_concluidas":int(conciliados),"itens_classificados_ia":int(ai30),"ultimo_backup":ub,"saude":saude,"alertas":alertas,"historico_7d":[{"dia":str(d),"acessos":int(a or 0),"falhas":int(f or 0)} for d,a,f in dias]}
