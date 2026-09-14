from __future__ import annotations
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, func, or_, and_
from sqlalchemy.exc import IntegrityError

from database.db import session_scope
from models.entities import (
    CodigoAPLB, GrupoDRE, GrupoCodigoVinculo, ContaFinanceira, Favorecido, SaldoInicial,
    Lancamento, FluxoProjetado, Patrimonio, FechamentoMensal, Conciliacao,
    ImportacaoExtrato, ItemConferencia, CentroCusto,
)
from services.auditoria import registrar_auditoria
from services.tenancy import get_active_tesouraria_id, tenant_where

STATUS_OFICIAIS = ("APROVADO", "CONCILIADO", "FECHADO")


def moeda(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def norm(s: str | None) -> str:
    return " ".join((s or "").upper().strip().split())


def fingerprint(conta_id, data_mov, valor, documento="", especificacao="", codigo_id=None, origem_bc="", natureza="", favorecido_id=None, favorecido="") -> str:
    raw = "|".join([str(get_active_tesouraria_id() or ""), str(conta_id or ""), str(data_mov), f"{moeda(valor):.2f}", str(codigo_id or ""), norm(origem_bc), norm(natureza), str(favorecido_id or ""), norm(favorecido), norm(documento), norm(especificacao)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def periodo_competencia_fechado(competencia: str | None = None, data_mov: date | None = None) -> bool:
    """V15: bloqueia pelo mês contábil (competência); usa a data apenas como fallback."""
    if competencia:
        try:
            ano, mes = map(int, competencia[:7].split("-"))
        except Exception:
            if data_mov is None:
                return False
            ano, mes = data_mov.year, data_mov.month
    elif data_mov is not None:
        ano, mes = data_mov.year, data_mov.month
    else:
        return False
    with session_scope() as s:
        return bool(s.scalar(select(FechamentoMensal.id).where(
            FechamentoMensal.ano == ano, FechamentoMensal.mes == mes, FechamentoMensal.status == "FECHADO", FechamentoMensal.tesouraria_id == get_active_tesouraria_id())))


def periodo_fechado(data_mov: date) -> bool:
    with session_scope() as s:
        f = s.scalar(select(FechamentoMensal).where(
            FechamentoMensal.ano == data_mov.year,
            FechamentoMensal.mes == data_mov.month,
            FechamentoMensal.status == "FECHADO",
            FechamentoMensal.tesouraria_id == get_active_tesouraria_id(),
        ))
        return bool(f)


def _codigo_tenant_id(tesouraria_id=None):
    if tesouraria_id is not None:
        return int(tesouraria_id)
    tid=get_active_tesouraria_id()
    if tid is not None:
        return tid
    # Compatibilidade para rotinas administrativas/testes fora do Streamlit.
    from models.entities import Tesouraria
    with session_scope() as s:
        return s.scalar(select(Tesouraria.id).where(Tesouraria.codigo=="CENTRAL"))


def listar_codigos(ativos=True, tesouraria_id=None):
    """V25.10: lista somente o Plano de Codigos da filial selecionada."""
    tid=_codigo_tenant_id(tesouraria_id)
    with session_scope() as s:
        q=select(CodigoAPLB).order_by(CodigoAPLB.codigo)
        if tid is not None:
            q=q.where(CodigoAPLB.tesouraria_id==tid)
        if ativos:
            q=q.where(CodigoAPLB.ativo.is_(True))
        return [{
            "id":x.id,"tesouraria_id":x.tesouraria_id,"codigo":x.codigo,"descricao":x.descricao,
            "natureza":x.natureza_padrao,"ativo":x.ativo,
            "permite_entrada":bool(x.permite_entrada),"permite_saida":bool(x.permite_saida),
            "gera_patrimonio":bool(x.gera_patrimonio),"observacao":x.observacao,
        } for x in s.scalars(q).all()]


def salvar_codigo(codigo, descricao, natureza=None, observacao=None, codigo_id=None, usuario_id=None, ativo=None, permite_entrada=None, permite_saida=None, tesouraria_id=None, gera_patrimonio=None):
    codigo=re.sub(r"\s+","",str(codigo or "")); codigo=codigo.zfill(4) if codigo.isdigit() and len(codigo)<=4 else codigo.strip()
    descricao=(descricao or "").strip(); tid=_codigo_tenant_id(tesouraria_id)
    if not tid: raise ValueError("Selecione a filial proprietaria do Plano de Codigos.")
    if not codigo: raise ValueError("Informe o codigo.")
    if not descricao: raise ValueError("Informe a descricao do codigo.")
    nat=(natureza or "").strip().upper()
    if permite_entrada is None and permite_saida is None:
        if nat=="ENTRADA": permite_entrada,permite_saida=True,True
        elif nat=="SAIDA": permite_entrada,permite_saida=False,True
        elif nat=="AMBOS": permite_entrada,permite_saida=True,True
        else: permite_entrada,permite_saida=False,False
    permite_entrada,permite_saida=bool(permite_entrada),bool(permite_saida)
    if not permite_entrada and not permite_saida: raise ValueError("O codigo precisa estar autorizado para Entrada, Saida ou ambos.")
    natureza_compat="AMBOS" if permite_entrada and permite_saida else ("ENTRADA" if permite_entrada else "SAIDA")
    with session_scope() as s:
        if codigo_id:
            obj=s.get(CodigoAPLB,codigo_id)
            if not obj or obj.tesouraria_id!=tid: raise ValueError("Codigo nao encontrado nesta filial.")
            repetido=s.scalar(select(CodigoAPLB.id).where(CodigoAPLB.tesouraria_id==tid,CodigoAPLB.codigo==codigo,CodigoAPLB.id!=codigo_id))
            if repetido: raise ValueError("Ja existe outro cadastro com esse codigo nesta filial.")
            ant={"tesouraria_id":tid,"codigo":obj.codigo,"descricao":obj.descricao,"natureza":obj.natureza_padrao,"permite_entrada":bool(obj.permite_entrada),"permite_saida":bool(obj.permite_saida),"gera_patrimonio":bool(obj.gera_patrimonio),"ativo":obj.ativo,"observacao":obj.observacao}
            obj.codigo,obj.descricao,obj.natureza_padrao,obj.observacao=codigo,descricao,natureza_compat,observacao
            obj.permite_entrada,obj.permite_saida=permite_entrada,permite_saida
            if gera_patrimonio is not None: obj.gera_patrimonio=bool(gera_patrimonio)
            if ativo is not None: obj.ativo=bool(ativo)
            s.flush(); rid=obj.id; acao="ALTERAR_CODIGO"
        else:
            if s.scalar(select(CodigoAPLB.id).where(CodigoAPLB.tesouraria_id==tid,CodigoAPLB.codigo==codigo)):
                raise ValueError("Codigo ja cadastrado nesta filial.")
            obj=CodigoAPLB(tesouraria_id=tid,codigo=codigo,descricao=descricao,natureza_padrao=natureza_compat,permite_entrada=permite_entrada,permite_saida=permite_saida,gera_patrimonio=bool(gera_patrimonio),observacao=observacao,ativo=True if ativo is None else bool(ativo))
            s.add(obj); s.flush(); rid=obj.id; ant=None; acao="CRIAR_CODIGO"
        novo={"tesouraria_id":tid,"codigo":obj.codigo,"descricao":obj.descricao,"natureza":obj.natureza_padrao,"permite_entrada":bool(obj.permite_entrada),"permite_saida":bool(obj.permite_saida),"gera_patrimonio":bool(obj.gera_patrimonio),"ativo":obj.ativo,"observacao":obj.observacao}
    registrar_auditoria(usuario_id,acao,"codigos_aplb",rid,ant,novo); return rid


def codigo_permite_natureza(codigo_id:int|None,natureza:str)->bool:
    if not codigo_id:return True
    nat=(natureza or "").strip().upper(); tid=get_active_tesouraria_id()
    with session_scope() as s:
        c=s.get(CodigoAPLB,codigo_id)
        if not c or not c.ativo or (tid is not None and c.tesouraria_id!=tid): return False
        return bool(c.permite_entrada) if nat=="ENTRADA" else bool(c.permite_saida) if nat=="SAIDA" else False


def definir_codigo_ativo(codigo_id:int,ativo:bool,usuario_id=None,tesouraria_id=None):
    tid=_codigo_tenant_id(tesouraria_id)
    with session_scope() as s:
        obj=s.get(CodigoAPLB,codigo_id)
        if not obj or (tid is not None and obj.tesouraria_id!=tid): raise ValueError("Codigo nao encontrado nesta filial.")
        ant={"ativo":obj.ativo}; obj.ativo=bool(ativo); desativados=[]
        if not ativo:
            for v in s.scalars(select(GrupoCodigoVinculo).where(GrupoCodigoVinculo.codigo_aplb_id==codigo_id,GrupoCodigoVinculo.ativo.is_(True))).all():
                v.ativo=False; desativados.append(v.id)
        s.flush(); novo={"ativo":obj.ativo,"vinculos_dre_desativados":desativados}
    registrar_auditoria(usuario_id,"ATIVAR_CODIGO" if ativo else "INATIVAR_CODIGO","codigos_aplb",codigo_id,ant,novo); return codigo_id


def listar_grupos():
    with session_scope() as s:
        rows=s.scalars(select(GrupoDRE).order_by(GrupoDRE.ordem,GrupoDRE.codigo_grupo)).all()
        return [{"id":g.id,"codigo_grupo":g.codigo_grupo,"nome":g.nome,"grupo_pai_id":g.grupo_pai_id,"ativo":g.ativo,"ordem":g.ordem} for g in rows]


def salvar_grupo(codigo_grupo,nome,grupo_pai_id=None,ordem=0,grupo_id=None,usuario_id=None):
    codigo_grupo=(codigo_grupo or "").strip(); nome=(nome or "").strip()
    if not codigo_grupo or not nome: raise ValueError("Informe o codigo e o nome do grupo DRE.")
    with session_scope() as s:
        if grupo_id:
            g=s.get(GrupoDRE,grupo_id)
            if not g: raise ValueError("Grupo DRE nao encontrado.")
            ant={"codigo_grupo":g.codigo_grupo,"nome":g.nome,"grupo_pai_id":g.grupo_pai_id,"ordem":g.ordem}
            g.codigo_grupo=codigo_grupo;g.nome=nome;g.grupo_pai_id=grupo_pai_id;g.ordem=int(ordem);rid=g.id;acao="ALTERAR_GRUPO_DRE"
        else:
            if s.scalar(select(GrupoDRE.id).where(GrupoDRE.codigo_grupo==codigo_grupo)): raise ValueError("Esse grupo DRE ja existe.")
            g=GrupoDRE(codigo_grupo=codigo_grupo,nome=nome,grupo_pai_id=grupo_pai_id,ordem=int(ordem),ativo=True);s.add(g);s.flush();rid=g.id;ant=None;acao="CRIAR_GRUPO_DRE"
        novo={"codigo_grupo":g.codigo_grupo,"nome":g.nome,"grupo_pai_id":g.grupo_pai_id,"ordem":g.ordem}
    registrar_auditoria(usuario_id,acao,"grupos_dre",rid,ant,novo);return rid


def _vinculo_ativo_do_codigo(s,codigo_id:int):
    return s.execute(select(GrupoCodigoVinculo,GrupoDRE).join(GrupoDRE,GrupoDRE.id==GrupoCodigoVinculo.grupo_dre_id).where(GrupoCodigoVinculo.codigo_aplb_id==codigo_id,GrupoCodigoVinculo.ativo.is_(True)).order_by(GrupoCodigoVinculo.id.desc())).first()


def vincular_codigo_grupo(grupo_id,codigo_id,vigencia_inicio=None,vigencia_fim=None,usuario_id=None):
    with session_scope() as s:
        codigo=s.get(CodigoAPLB,codigo_id);grupo=s.get(GrupoDRE,grupo_id)
        if not codigo or not grupo: raise ValueError("Codigo ou grupo DRE nao encontrado.")
        if not codigo.ativo: raise ValueError(f"O codigo {codigo.codigo} esta inativo.")
        atual=_vinculo_ativo_do_codigo(s,codigo_id)
        if atual:
            v0,g0=atual
            if v0.grupo_dre_id==grupo_id:return v0.id
            raise ValueError(f"O codigo {codigo.codigo} já está vinculado ao grupo {g0.codigo_grupo} - {g0.nome}.")
        v=GrupoCodigoVinculo(grupo_dre_id=grupo_id,codigo_aplb_id=codigo_id,vigencia_inicio=vigencia_inicio,vigencia_fim=vigencia_fim,ativo=True);s.add(v);s.flush();rid=v.id
    registrar_auditoria(usuario_id,"VINCULAR_CODIGO_GRUPO","grupo_codigo_vinculo",rid,novo={"grupo_id":grupo_id,"codigo_id":codigo_id,"tesouraria_id":codigo.tesouraria_id});return rid


def desvincular_codigo_grupo(codigo_id:int,usuario_id=None):
    with session_scope() as s:
        atual=_vinculo_ativo_do_codigo(s,codigo_id)
        if not atual:return False
        v,g=atual;ant={"grupo_id":v.grupo_dre_id,"grupo":g.codigo_grupo,"codigo_id":codigo_id,"ativo":True};v.ativo=False;rid=v.id
    registrar_auditoria(usuario_id,"DESVINCULAR_CODIGO_GRUPO","grupo_codigo_vinculo",rid,ant,{"ativo":False});return True


def mover_codigo_grupo(codigo_id:int,novo_grupo_id:int,usuario_id=None):
    with session_scope() as s:
        codigo=s.get(CodigoAPLB,codigo_id);novo=s.get(GrupoDRE,novo_grupo_id)
        if not codigo or not novo: raise ValueError("Codigo ou grupo DRE nao encontrado.")
        if not codigo.ativo: raise ValueError(f"O codigo {codigo.codigo} esta inativo.")
        atual=_vinculo_ativo_do_codigo(s,codigo_id);anterior=None
        if atual:
            v0,g0=atual
            if v0.grupo_dre_id==novo_grupo_id:return v0.id
            anterior={"vinculo_id":v0.id,"grupo_id":g0.id,"grupo":g0.codigo_grupo,"nome":g0.nome};v0.ativo=False
        v=GrupoCodigoVinculo(grupo_dre_id=novo_grupo_id,codigo_aplb_id=codigo_id,ativo=True);s.add(v);s.flush();rid=v.id
        ni={"vinculo_id":rid,"grupo_id":novo.id,"grupo":novo.codigo_grupo,"nome":novo.nome,"codigo_id":codigo_id,"codigo":codigo.codigo,"tesouraria_id":codigo.tesouraria_id}
    registrar_auditoria(usuario_id,"MOVER_CODIGO_GRUPO_DRE","grupo_codigo_vinculo",rid,anterior,ni);return rid


def configurar_codigos_grupo(grupo_id:int,codigo_ids:list[int],usuario_id=None,tesouraria_id=None):
    tid=_codigo_tenant_id(tesouraria_id); desejados={int(x) for x in (codigo_ids or [])}
    if not tid: raise ValueError("Selecione uma filial para configurar a DRE.")
    with session_scope() as s:
        grupo=s.get(GrupoDRE,grupo_id)
        if not grupo: raise ValueError("Grupo DRE nao encontrado.")
        codigos={c.id:c for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==tid,CodigoAPLB.id.in_(desejados) if desejados else False)).all()} if desejados else {}
        if desejados-set(codigos):raise ValueError("Ha codigo(s) invalido(s) na selecao desta filial.")
        inativos=[c.codigo for c in codigos.values() if not c.ativo]
        if inativos:raise ValueError("Codigo(s) inativo(s): "+", ".join(inativos))
        conflitos=[]
        for cid in desejados:
            atual=_vinculo_ativo_do_codigo(s,cid)
            if atual and atual[0].grupo_dre_id!=grupo_id:conflitos.append(f"{codigos[cid].codigo} -> {atual[1].codigo_grupo}")
        if conflitos:raise ValueError("Um codigo nao pode ficar em dois grupos DRE. Conflitos: "+"; ".join(conflitos))
        ativos=s.scalars(select(GrupoCodigoVinculo).join(CodigoAPLB,CodigoAPLB.id==GrupoCodigoVinculo.codigo_aplb_id).where(GrupoCodigoVinculo.grupo_dre_id==grupo_id,GrupoCodigoVinculo.ativo.is_(True),CodigoAPLB.tesouraria_id==tid)).all()
        atuais={v.codigo_aplb_id:v for v in ativos};removidos=[];adicionados=[]
        for cid,v in atuais.items():
            if cid not in desejados:v.ativo=False;removidos.append(cid)
        for cid in desejados-set(atuais):
            s.add(GrupoCodigoVinculo(grupo_dre_id=grupo_id,codigo_aplb_id=cid,ativo=True));adicionados.append(cid)
        s.flush();ant={"tesouraria_id":tid,"grupo_id":grupo_id,"codigos":sorted(atuais)};novo={"tesouraria_id":tid,"grupo_id":grupo_id,"codigos":sorted(desejados),"adicionados":sorted(adicionados),"removidos":sorted(removidos)}
    registrar_auditoria(usuario_id,"CONFIGURAR_CODIGOS_GRUPO_DRE","grupos_dre",grupo_id,ant,novo);return novo


def listar_vinculos(incluir_inativos=False,tesouraria_id=None):
    tid=_codigo_tenant_id(tesouraria_id)
    with session_scope() as s:
        q=select(GrupoCodigoVinculo,GrupoDRE,CodigoAPLB).join(GrupoDRE,GrupoDRE.id==GrupoCodigoVinculo.grupo_dre_id).join(CodigoAPLB,CodigoAPLB.id==GrupoCodigoVinculo.codigo_aplb_id)
        if tid is not None:q=q.where(CodigoAPLB.tesouraria_id==tid)
        if not incluir_inativos:q=q.where(GrupoCodigoVinculo.ativo.is_(True))
        rows=s.execute(q.order_by(GrupoDRE.ordem,GrupoDRE.codigo_grupo,CodigoAPLB.codigo,GrupoCodigoVinculo.id)).all()
        return [{"vinculo_id":v.id,"tesouraria_id":c.tesouraria_id,"grupo_id":g.id,"grupo":g.codigo_grupo,"grupo_nome":g.nome,"codigo_id":c.id,"codigo":c.codigo,"codigo_descricao":c.descricao,"codigo_ativo":c.ativo,"ativo":v.ativo,"inicio":v.vigencia_inicio,"fim":v.vigencia_fim} for v,g,c in rows]


def auditoria_configuracao_dre(tesouraria_id=None):
    tid=_codigo_tenant_id(tesouraria_id)
    with session_scope() as s:
        q=select(CodigoAPLB).order_by(CodigoAPLB.codigo)
        if tid is not None:q=q.where(CodigoAPLB.tesouraria_id==tid)
        codigos=s.scalars(q).all()
        vq=select(GrupoCodigoVinculo,GrupoDRE).join(GrupoDRE,GrupoDRE.id==GrupoCodigoVinculo.grupo_dre_id).join(CodigoAPLB,CodigoAPLB.id==GrupoCodigoVinculo.codigo_aplb_id).where(GrupoCodigoVinculo.ativo.is_(True))
        if tid is not None:vq=vq.where(CodigoAPLB.tesouraria_id==tid)
        vincs=s.execute(vq).all();por_codigo={}
        for v,g in vincs:por_codigo.setdefault(v.codigo_aplb_id,[]).append((v,g))
        duplicados=[];sem_grupo=[];rows=[]
        for c in codigos:
            vg=por_codigo.get(c.id,[])
            if c.ativo and not vg:sem_grupo.append(c.codigo)
            if len(vg)>1:duplicados.append(c.codigo)
            grupo=vg[0][1] if len(vg)==1 else None
            rows.append({"codigo":c.codigo,"descricao":c.descricao,"entrada":"SIM" if c.permite_entrada else "NAO","saida":"SIM" if c.permite_saida else "NAO","ativo":c.ativo,"grupo":grupo.codigo_grupo if grupo else "","grupo_nome":grupo.nome if grupo else "","situacao":"DUPLICADO" if len(vg)>1 else ("CONFIGURADO" if grupo else ("SEM GRUPO" if c.ativo else "INATIVO"))})
        return {"codigos":rows,"total":len(codigos),"ativos":sum(1 for c in codigos if c.ativo),"sem_grupo":sem_grupo,"duplicados":duplicados,"ok":not duplicados}

def listar_contas(ativas=True):
    with session_scope() as s:
        q=select(ContaFinanceira).where(tenant_where(ContaFinanceira.tesouraria_id)).order_by(ContaFinanceira.tipo,ContaFinanceira.nome)
        if ativas:q=q.where(ContaFinanceira.ativo.is_(True))
        return [{"id":x.id,"nome":x.nome,"tipo":x.tipo,"banco":x.banco,"agencia":x.agencia,"conta":x.conta,"ativo":x.ativo} for x in s.scalars(q).all()]


def salvar_conta(nome,tipo,banco=None,agencia=None,conta=None,usuario_id=None):
    with session_scope() as s:
        x=ContaFinanceira(tesouraria_id=get_active_tesouraria_id(),nome=nome.strip(),tipo=tipo,banco=(banco or "").strip() or None,agencia=(agencia or "").strip() or None,conta=(conta or "").strip() or None,ativo=True);s.add(x);s.flush();rid=x.id
    registrar_auditoria(usuario_id,"CRIAR_CONTA","contas_financeiras",rid,novo={"nome":nome,"tipo":tipo});return rid


def listar_favorecidos(ativos=True):
    with session_scope() as s:
        q=select(Favorecido).where(tenant_where(Favorecido.tesouraria_id)).order_by(Favorecido.nome)
        if ativos:q=q.where(Favorecido.ativo.is_(True))
        return [{"id":x.id,"codigo":x.codigo_cadastro or f"CAD-{x.id:06d}","nome":x.nome,"documento":x.documento,"tipo":x.tipo,"email":x.email,"telefone":x.telefone,"pix":x.pix,"banco":x.banco,"agencia":x.agencia,"conta":x.conta,"ativo":x.ativo} for x in s.scalars(q).all()]


def _prefixo_favorecido(tipo):
    return {"COLABORADOR":"COL","FORNECEDOR":"FOR","PRESTADOR":"PRE","ENTIDADE":"ENT","SINDICATO/NUCLEO":"SIN","ORGAO_PUBLICO":"ORG"}.get(norm(tipo).replace(" ","_"),"CAD")


def salvar_favorecido(nome,documento=None,tipo="OUTRO",email=None,telefone=None,observacao=None,usuario_id=None,pix=None,banco=None,agencia=None,conta=None):
    nome=(nome or "").strip()
    if not nome: raise ValueError("Informe o nome/razão social.")
    doc=(documento or "").strip() or None
    with session_scope() as s:
        if doc and s.scalar(select(Favorecido.id).where(Favorecido.documento==doc, tenant_where(Favorecido.tesouraria_id))):
            raise ValueError("Já existe pessoa/entidade com este CPF/CNPJ/documento.")
        x=Favorecido(tesouraria_id=get_active_tesouraria_id(),nome=nome,documento=doc,tipo=tipo,email=(email or "").strip() or None,telefone=(telefone or "").strip() or None,observacao=observacao,ativo=True,pix=(pix or "").strip() or None,banco=(banco or "").strip() or None,agencia=(agencia or "").strip() or None,conta=(conta or "").strip() or None)
        s.add(x);s.flush(); x.codigo_cadastro=f"{_prefixo_favorecido(tipo)}-{x.id:06d}"; rid=x.id; codigo=x.codigo_cadastro
    registrar_auditoria(usuario_id,"CRIAR_FAVORECIDO","favorecidos",rid,novo={"codigo":codigo,"nome":nome,"documento":doc,"tipo":tipo});return rid


def criar_lancamento(data_movimento,codigo_id,origem_bc,natureza,especificacao,valor,conta_id=None,favorecido=None,documento=None,competencia=None,status="APROVADO",origem="MANUAL",usuario_id=None,lancamento_original_id=None,favorecido_id=None,centro_custo_id=None):
    if periodo_competencia_fechado(competencia, data_movimento):
        raise ValueError("A competência informada está fechada. Reabra o período antes de lançar.")
    fp=fingerprint(conta_id,data_movimento,valor,documento,especificacao,codigo_id,origem_bc,natureza,favorecido_id,favorecido)
    with session_scope() as s:
        tid=get_active_tesouraria_id()
        if conta_id:
            ct=s.get(ContaFinanceira,conta_id)
            if not ct or ct.tesouraria_id != tid: raise ValueError("Conta financeira não pertence à unidade ativa.")
        if centro_custo_id:
            cc=s.get(CentroCusto,centro_custo_id)
            if not cc or cc.tesouraria_id != tid: raise ValueError("Centro de custo não pertence à unidade ativa.")
        if favorecido_id:
            fv=s.get(Favorecido,favorecido_id)
            if not fv or fv.tesouraria_id != tid: raise ValueError("Favorecido não pertence à unidade ativa.")
        if lancamento_original_id:
            lo=s.get(Lancamento,lancamento_original_id)
            if not lo or lo.tesouraria_id != tid: raise ValueError("Lançamento original não pertence à unidade ativa.")
        if s.scalar(select(Lancamento.id).where(Lancamento.fingerprint==fp, tenant_where(Lancamento.tesouraria_id))):
            raise ValueError("Possível duplicidade: já existe lançamento com a mesma impressão digital.")
        l=Lancamento(tesouraria_id=tid,data_movimento=data_movimento,competencia=competencia,codigo_aplb_id=codigo_id,origem_bc=origem_bc,natureza=natureza,especificacao=especificacao.strip(),favorecido=(favorecido or "").strip() or None,favorecido_id=favorecido_id,documento=(documento or "").strip() or None,valor=moeda(valor),conta_financeira_id=conta_id,centro_custo_id=centro_custo_id,status=status,origem_lancamento=origem,fingerprint=fp,lancamento_original_id=lancamento_original_id,criado_por=usuario_id)
        s.add(l);s.flush();rid=l.id
    registrar_auditoria(usuario_id,"CRIAR_LANCAMENTO","lancamentos",rid,novo={"data":data_movimento,"natureza":natureza,"valor":str(valor),"origem_bc":origem_bc});return rid


def criar_transferencia_interna(data_movimento,valor,conta_banco_id,conta_caixa_id,especificacao="SUPRIMENTO DE CAIXA",codigo_id=None,usuario_id=None):
    saida=criar_lancamento(data_movimento,codigo_id,"B","SAIDA",especificacao,valor,conta_banco_id,status="APROVADO",origem="TRANSFERENCIA_INTERNA",usuario_id=usuario_id)
    entrada=criar_lancamento(data_movimento,codigo_id,"C","ENTRADA",especificacao,valor,conta_caixa_id,status="APROVADO",origem="TRANSFERENCIA_INTERNA",usuario_id=usuario_id,lancamento_original_id=saida)
    return saida,entrada


def listar_lancamentos(inicio=None,fim=None,origem_bc=None,natureza=None,codigo_id=None,status=None,texto=None,valor_min=None,valor_max=None,limit=2000,include_cancelados=False):
    with session_scope() as s:
        q=select(Lancamento,CodigoAPLB,ContaFinanceira).outerjoin(CodigoAPLB,CodigoAPLB.id==Lancamento.codigo_aplb_id).outerjoin(ContaFinanceira,ContaFinanceira.id==Lancamento.conta_financeira_id)
        filtros=[tenant_where(Lancamento.tesouraria_id)]
        if inicio:filtros.append(Lancamento.data_movimento>=inicio)
        if fim:filtros.append(Lancamento.data_movimento<=fim)
        if origem_bc:filtros.append(Lancamento.origem_bc==origem_bc)
        if natureza:filtros.append(Lancamento.natureza==natureza)
        if codigo_id:filtros.append(Lancamento.codigo_aplb_id==codigo_id)
        if status:
            filtros.append(Lancamento.status==status)
        elif not include_cancelados:
            filtros.append(Lancamento.status!="CANCELADO")
        if valor_min is not None:filtros.append(Lancamento.valor>=moeda(valor_min))
        if valor_max is not None:filtros.append(Lancamento.valor<=moeda(valor_max))
        if texto:
            like=f"%{texto.strip()}%";filtros.append(or_(Lancamento.especificacao.ilike(like),Lancamento.favorecido.ilike(like),Lancamento.documento.ilike(like),CodigoAPLB.descricao.ilike(like),CodigoAPLB.codigo.ilike(like)))
        if filtros:q=q.where(and_(*filtros))
        q=q.order_by(Lancamento.data_movimento.desc(),Lancamento.id.desc()).limit(limit)
        rows=s.execute(q).all()
        return [{"id":l.id,"data":l.data_movimento,"codigo":c.codigo if c else "","codigo_descricao":c.descricao if c else "","B/C":l.origem_bc,"natureza":l.natureza,"especificacao":l.especificacao,"favorecido":l.favorecido or "","documento":l.documento or "","valor":float(l.valor),"conta":ct.nome if ct else "","status":l.status,"origem":l.origem_lancamento,"criado_em":l.criado_em} for l,c,ct in rows]


def corrigir_lancamento(lancamento_id,usuario_id,motivo,**campos):
    with session_scope() as s:
        l=s.get(Lancamento,lancamento_id)
        if not l or l.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Lançamento não encontrado na unidade ativa.")
        if periodo_competencia_fechado(l.competencia, l.data_movimento): raise ValueError("Lançamento pertence a competência fechada.")
        ant={"data":l.data_movimento,"codigo_id":l.codigo_aplb_id,"B/C":l.origem_bc,"natureza":l.natureza,"especificacao":l.especificacao,"valor":str(l.valor),"status":l.status}
        for k,v in campos.items():
            if hasattr(l,k) and v is not None:setattr(l,k,v)
        l.fingerprint=fingerprint(l.conta_financeira_id,l.data_movimento,l.valor,l.documento,l.especificacao)
        novo={"data":l.data_movimento,"codigo_id":l.codigo_aplb_id,"B/C":l.origem_bc,"natureza":l.natureza,"especificacao":l.especificacao,"valor":str(l.valor),"status":l.status}
    registrar_auditoria(usuario_id,"CORRIGIR_LANCAMENTO","lancamentos",lancamento_id,ant,novo,motivo)


def cancelar_lancamento(lancamento_id, usuario_id, motivo):
    motivo=(motivo or "").strip()
    if not motivo:
        raise ValueError("Informe o motivo do cancelamento.")
    with session_scope() as s:
        l=s.get(Lancamento,lancamento_id)
        if not l or l.tesouraria_id != get_active_tesouraria_id():
            raise ValueError("Lançamento não encontrado na unidade ativa.")
        if l.status=="CANCELADO":
            return lancamento_id
        if periodo_competencia_fechado(l.competencia, l.data_movimento):
            raise ValueError("Lançamento pertence a competência fechada. Reabra o período antes de cancelar.")
        ant={"status":l.status,"data":l.data_movimento,"valor":str(l.valor),"natureza":l.natureza,"origem_bc":l.origem_bc,"especificacao":l.especificacao}
        l.status="CANCELADO"
        novo={"status":"CANCELADO","data":l.data_movimento,"valor":str(l.valor),"natureza":l.natureza,"origem_bc":l.origem_bc,"especificacao":l.especificacao}
    registrar_auditoria(usuario_id,"CANCELAR_LANCAMENTO","lancamentos",lancamento_id,ant,novo,motivo)
    return lancamento_id


def estornar_lancamento(lancamento_id,usuario_id,motivo):
    motivo=(motivo or "").strip()
    if not motivo:
        raise ValueError("Informe o motivo do estorno.")
    with session_scope() as s:
        l=s.get(Lancamento,lancamento_id)
        if not l or l.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Lançamento não encontrado na unidade ativa.")
        if l.status=="CANCELADO":raise ValueError("Lançamento cancelado não pode ser estornado.")
        data_mov=l.data_movimento;codigo=l.codigo_aplb_id;bc=l.origem_bc;nat="ENTRADA" if l.natureza=="SAIDA" else "SAIDA";esp=f"ESTORNO DO LANÇAMENTO {l.id}: {l.especificacao}";valor=l.valor;conta=l.conta_financeira_id;fav=l.favorecido;doc=l.documento;comp=l.competencia
    rid=criar_lancamento(data_mov,codigo,bc,nat,esp,valor,conta,fav,doc,comp,"APROVADO","ESTORNO",usuario_id,lancamento_id)
    registrar_auditoria(usuario_id,"ESTORNAR_LANCAMENTO","lancamentos",lancamento_id,novo={"estorno_id":rid},motivo=motivo)
    return rid


def saldos(inicio=None,fim=None):
    with session_scope() as s:
        q=select(Lancamento.origem_bc,Lancamento.natureza,func.coalesce(func.sum(Lancamento.valor),0)).where(Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))
        if inicio:
            q=q.where(Lancamento.data_movimento>=inicio)
            if fim:q=q.where(Lancamento.data_movimento<=fim)
        elif fim:
            # Para cargas mensais consolidadas, a competência é a referência oficial.
            # Lançamentos manuais sem competência continuam obedecendo à data real.
            comp_fim=f"{fim.year:04d}-{fim.month:02d}"
            q=q.where(or_(Lancamento.competencia<=comp_fim,and_(Lancamento.competencia.is_(None),Lancamento.data_movimento<=fim)))
        rows=s.execute(q.group_by(Lancamento.origem_bc,Lancamento.natureza)).all()
        iniciais=[]
        # Saldo de abertura compõe o saldo acumulado, mas não é receita do mês.
        if inicio is None:
            qi=select(SaldoInicial,ContaFinanceira).join(ContaFinanceira,ContaFinanceira.id==SaldoInicial.conta_financeira_id).where(tenant_where(SaldoInicial.tesouraria_id))
            if fim:qi=qi.where(SaldoInicial.data_referencia<=fim)
            iniciais=s.execute(qi).all()
    out={"B":Decimal("0"),"C":Decimal("0")}
    for si,conta in iniciais:
        bc="B" if conta.tipo=="BANCO" else "C"
        out[bc]=out.get(bc,Decimal("0"))+Decimal(si.valor)
    for bc,nat,total in rows:
        out[bc]=out.get(bc,Decimal("0"))+(Decimal(total) if nat=="ENTRADA" else -Decimal(total))
    out["GERAL"]=out.get("B",0)+out.get("C",0)
    return out


def criar_previsao(data_prevista,natureza,valor,descricao,codigo_id=None,favorecido=None,recorrencia=None,probabilidade=1.0,status="PREVISTO",usuario_id=None):
    with session_scope() as s:
        x=FluxoProjetado(tesouraria_id=get_active_tesouraria_id(),data_prevista=data_prevista,natureza=natureza,valor=moeda(valor),codigo_aplb_id=codigo_id,descricao=descricao,favorecido=favorecido,recorrencia=recorrencia,probabilidade=float(probabilidade),status=status);s.add(x);s.flush();rid=x.id
    registrar_auditoria(usuario_id,"CRIAR_PREVISAO","fluxo_projetado",rid,novo={"data":data_prevista,"natureza":natureza,"valor":str(valor)});return rid


def listar_fluxo_projetado(inicio=None,fim=None):
    with session_scope() as s:
        q=select(FluxoProjetado,CodigoAPLB).outerjoin(CodigoAPLB,CodigoAPLB.id==FluxoProjetado.codigo_aplb_id).where(tenant_where(FluxoProjetado.tesouraria_id))
        if inicio:q=q.where(FluxoProjetado.data_prevista>=inicio)
        if fim:q=q.where(FluxoProjetado.data_prevista<=fim)
        rows=s.execute(q.order_by(FluxoProjetado.data_prevista)).all()
        return [{"id":x.id,"data":x.data_prevista,"natureza":x.natureza,"valor":float(x.valor),"valor_ponderado":float(x.valor)*float(x.probabilidade or 1),"codigo":c.codigo if c else "","descricao":x.descricao,"favorecido":x.favorecido or "","probabilidade":x.probabilidade,"status":x.status} for x,c in rows]


def salvar_patrimonio(descricao,numero=None,categoria=None,data_aquisicao=None,valor=None,fornecedor=None,nota_fiscal=None,local_uso=None,responsavel=None,situacao="ATIVO",lancamento_id=None,usuario_id=None,estado_conservacao=None,vida_util_anos=None,fornecedor_id=None):
    descricao=(descricao or "").strip()
    if not descricao:
        raise ValueError("Informe a descrição do bem.")
    numero=(numero or "").strip() or None
    with session_scope() as s:
        tid=get_active_tesouraria_id()
        if numero and s.scalar(select(Patrimonio.id).where(Patrimonio.tesouraria_id==tid, Patrimonio.numero_patrimonial==numero)):
            raise ValueError("Já existe um bem com este número patrimonial nesta filial.")
        p=Patrimonio(
            tesouraria_id=tid, numero_patrimonial=numero, descricao=descricao, categoria=(categoria or "").strip() or None,
            data_aquisicao=data_aquisicao, valor=moeda(valor) if valor is not None else None,
            fornecedor=(fornecedor or "").strip() or None, fornecedor_id=fornecedor_id,
            nota_fiscal=(nota_fiscal or "").strip() or None, local_uso=(local_uso or "").strip() or None,
            responsavel=(responsavel or "").strip() or None, situacao=situacao or "ATIVO",
            estado_conservacao=(estado_conservacao or "").strip() or None,
            vida_util_anos=int(vida_util_anos) if vida_util_anos not in (None, "") else None,
            lancamento_origem_id=lancamento_id,
        )
        s.add(p);s.flush();rid=p.id
    registrar_auditoria(usuario_id,"CRIAR_PATRIMONIO","patrimonio",rid,novo={
        "numero":numero,"descricao":descricao,"valor":str(valor) if valor is not None else None,
        "situacao":situacao,"estado_conservacao":estado_conservacao,"vida_util_anos":vida_util_anos,
        "fornecedor_id":fornecedor_id,"lancamento_id":lancamento_id,
    });return rid


def listar_patrimonio():
    with session_scope() as s:
        return [{
            "id":p.id,"numero":p.numero_patrimonial or "","descricao":p.descricao,"categoria":p.categoria or "",
            "aquisição":p.data_aquisicao,"valor":float(p.valor or 0),"fornecedor":p.fornecedor or "",
            "fornecedor_id":p.fornecedor_id,"nota_fiscal":p.nota_fiscal or "","local":p.local_uso or "",
            "responsável":p.responsavel or "","conservação":p.estado_conservacao or "",
            "vida_útil_anos":p.vida_util_anos,"situação":p.situacao,"lancamento_origem_id":p.lancamento_origem_id
        } for p in s.scalars(select(Patrimonio).where(tenant_where(Patrimonio.tesouraria_id)).order_by(Patrimonio.descricao)).all()]


def fechar_mes(ano,mes,usuario_id):
    """V16: fecha a competência, preservando um snapshot reversível dos status."""
    from services.security import permitido
    # usuario_id=None é reservado para rotinas internas/testes; a interface sempre informa o usuário.
    if usuario_id is not None and not permitido("", "FECHAR", usuario_id):
        raise PermissionError("Usuário sem permissão para fechar competência.")
    comp=f"{ano:04d}-{mes:02d}"
    ini=date(ano,mes,1); fim=date(ano+1,1,1) if mes==12 else date(ano,mes+1,1)
    filtro=_filtro_mes_competencia(ano,mes)
    with session_scope() as s:
        existente=s.scalar(select(FechamentoMensal).where(FechamentoMensal.ano==ano,FechamentoMensal.mes==mes,tenant_where(FechamentoMensal.tesouraria_id)))
        if existente and existente.status=="FECHADO":
            raise ValueError("Esta competência já está fechada.")
        pend=s.scalar(select(func.count(Lancamento.id)).where(filtro,Lancamento.status.in_(("RASCUNHO","EM_CONFERENCIA")))) or 0
        if pend: raise ValueError(f"Existem {pend} lançamento(s) ainda não aprovados na competência.")
        rows=s.scalars(select(Lancamento).where(filtro,Lancamento.status.in_(("APROVADO","CONCILIADO")))).all()
        status_antes={str(x.id):x.status for x in rows}
        ent=sum((Decimal(x.valor) for x in rows if x.natureza=="ENTRADA"),Decimal("0"))
        sai=sum((Decimal(x.valor) for x in rows if x.natureza=="SAIDA"),Decimal("0"))
        snap={"versao":15,"competencia":comp,"gerado_em":datetime.utcnow().isoformat()+"Z",
              "totais":{"entradas":str(ent),"saidas":str(sai),"resultado":str(ent-sai),"quantidade":len(rows)},
              "saldos_fim":{"B":str(saldos(fim=fim-timedelta(days=1)).get("B",0)),"C":str(saldos(fim=fim-timedelta(days=1)).get("C",0)),"GERAL":str(saldos(fim=fim-timedelta(days=1)).get("GERAL",0))},
              "status_antes":status_antes}
        f=existente or FechamentoMensal(tesouraria_id=get_active_tesouraria_id(),ano=ano,mes=mes)
        if not existente:s.add(f)
        f.status="FECHADO";f.snapshot_json=json.dumps(snap,ensure_ascii=False);f.fechado_por=usuario_id;f.fechado_em=datetime.utcnow()
        f.reaberto_por=None;f.reaberto_em=None;f.motivo_reabertura=None
        for x in rows:x.status="FECHADO"
    registrar_auditoria(usuario_id,"FECHAR_MES","fechamentos_mensais",motivo=comp,novo={"competencia":comp,"quantidade":len(status_antes),"entradas":str(ent),"saidas":str(sai)})


def reabrir_mes(ano,mes,usuario_id,motivo):
    """V16: reabertura é exclusiva de Administrador e restaura o snapshot."""
    from services.security import eh_admin_ativo
    # usuario_id=None é reservado para rotinas internas/testes; na interface, reabertura é só Administrador.
    if usuario_id is not None and not eh_admin_ativo(usuario_id):
        raise PermissionError("Somente Administrador pode reabrir competência fechada.")
    motivo=(motivo or "").strip()
    if not motivo: raise ValueError("Informe o motivo da reabertura.")
    with session_scope() as s:
        f=s.scalar(select(FechamentoMensal).where(FechamentoMensal.ano==ano,FechamentoMensal.mes==mes,tenant_where(FechamentoMensal.tesouraria_id)))
        if not f or f.status!="FECHADO":raise ValueError("Não existe competência fechada para reabrir.")
        try:snap=json.loads(f.snapshot_json or "{}")
        except Exception:snap={}
        mapa=snap.get("status_antes",{})
        restaurados=0
        if mapa:
            for sid,status in mapa.items():
                l=s.get(Lancamento,int(sid))
                if l and l.status=="FECHADO":
                    l.status=status if status in ("APROVADO","CONCILIADO") else "APROVADO";restaurados+=1
        else:
            filtro=_filtro_mes_competencia(ano,mes)
            rows=s.scalars(select(Lancamento).where(filtro,Lancamento.status=="FECHADO")).all()
            for l in rows:l.status="APROVADO";restaurados+=1
        f.status="ABERTO";f.reaberto_por=usuario_id;f.reaberto_em=datetime.utcnow();f.motivo_reabertura=motivo
    registrar_auditoria(usuario_id,"REABRIR_MES","fechamentos_mensais",motivo=motivo,novo={"competencia":f"{ano:04d}-{mes:02d}","restaurados":restaurados})



def _filtro_mes_competencia(ano: int, mes: int):
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    comp = f"{ano:04d}-{mes:02d}"
    return and_(Lancamento.tesouraria_id == get_active_tesouraria_id(), or_(
        Lancamento.competencia == comp,
        and_(Lancamento.competencia.is_(None), Lancamento.data_movimento >= inicio, Lancamento.data_movimento < fim),
    ))


def resumo_dashboard(ano: int, mes: int):
    """Resumo consolidado do dashboard a partir da base oficial."""
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)

    sal = saldos(fim=fim - timedelta(days=1))
    filtro_mes = _filtro_mes_competencia(ano, mes)
    with session_scope() as s:
        entradas_mes = s.scalar(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                filtro_mes,
                Lancamento.natureza == "ENTRADA",
                Lancamento.status.in_(STATUS_OFICIAIS),
            )
        ) or 0
        saidas_mes = s.scalar(
            select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                filtro_mes,
                Lancamento.natureza == "SAIDA",
                Lancamento.status.in_(STATUS_OFICIAIS),
            )
        ) or 0
        proj_ent = s.scalar(
            select(func.coalesce(func.sum(FluxoProjetado.valor * FluxoProjetado.probabilidade), 0)).where(
                FluxoProjetado.data_prevista >= inicio,
                FluxoProjetado.data_prevista < fim,
                FluxoProjetado.natureza == "ENTRADA",
                FluxoProjetado.status.in_(("PREVISTO", "CONFIRMADO")),
                tenant_where(FluxoProjetado.tesouraria_id),
            )
        ) or 0
        proj_sai = s.scalar(
            select(func.coalesce(func.sum(FluxoProjetado.valor * FluxoProjetado.probabilidade), 0)).where(
                FluxoProjetado.data_prevista >= inicio,
                FluxoProjetado.data_prevista < fim,
                FluxoProjetado.natureza == "SAIDA",
                FluxoProjetado.status.in_(("PREVISTO", "CONFIRMADO")),
                tenant_where(FluxoProjetado.tesouraria_id),
            )
        ) or 0

        pend_conf = s.scalar(select(func.count(ItemConferencia.id)).join(ImportacaoExtrato, ImportacaoExtrato.id==ItemConferencia.importacao_id).where(ItemConferencia.status == "PENDENTE", tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        pend_conc = s.scalar(select(func.count(Conciliacao.id)).join(Lancamento, Lancamento.id==Conciliacao.lancamento_id).where(Conciliacao.status != "CONCILIADO", tenant_where(Lancamento.tesouraria_id))) or 0
        rasc = s.scalar(select(func.count(Lancamento.id)).where(Lancamento.status.in_(("RASCUNHO", "EM_CONFERENCIA")), tenant_where(Lancamento.tesouraria_id))) or 0
        imp_conf = s.scalar(select(func.count(ImportacaoExtrato.id)).where(ImportacaoExtrato.status == "EM_CONFERENCIA", tenant_where(ImportacaoExtrato.tesouraria_id))) or 0
        total_oficiais = s.scalar(select(func.count(Lancamento.id)).where(Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))) or 0
        codigos_ativos = s.scalar(select(func.count(CodigoAPLB.id)).where(CodigoAPLB.ativo.is_(True))) or 0
        contas_ativas = s.scalar(select(func.count(ContaFinanceira.id)).where(ContaFinanceira.ativo.is_(True), tenant_where(ContaFinanceira.tesouraria_id))) or 0
        patrimonio_ativo = s.scalar(select(func.count(Patrimonio.id)).where(Patrimonio.situacao == "ATIVO", tenant_where(Patrimonio.tesouraria_id))) or 0
        fechado = bool(s.scalar(select(FechamentoMensal.id).where(
            FechamentoMensal.ano == ano,
            FechamentoMensal.mes == mes,
            FechamentoMensal.status == "FECHADO",
            FechamentoMensal.tesouraria_id == get_active_tesouraria_id(),
        )))

    entradas_mes = Decimal(entradas_mes)
    saidas_mes = Decimal(saidas_mes)
    proj_ent = Decimal(str(proj_ent))
    proj_sai = Decimal(str(proj_sai))
    saldo_total = Decimal(sal.get("GERAL", 0))
    return {
        "saldo_banco": Decimal(sal.get("B", 0)),
        "saldo_caixa": Decimal(sal.get("C", 0)),
        "saldo_total": saldo_total,
        "entradas_mes": entradas_mes,
        "saidas_mes": saidas_mes,
        "resultado_mes": entradas_mes - saidas_mes,
        "projetado_entradas": proj_ent,
        "projetado_saidas": proj_sai,
        "saldo_projetado": saldo_total + proj_ent - proj_sai,
        "itens_conferencia_pendentes": int(pend_conf),
        "conciliacoes_pendentes": int(pend_conc),
        "lancamentos_rascunho": int(rasc),
        "importacoes_em_conferencia": int(imp_conf),
        "total_lancamentos_oficiais": int(total_oficiais),
        "codigos_ativos": int(codigos_ativos),
        "contas_ativas": int(contas_ativas),
        "patrimonio_ativo": int(patrimonio_ativo),
        "periodo_fechado": fechado,
    }


def serie_mensal_dashboard(ano: int, mes: int, meses: int = 6):
    """Entradas e saídas oficiais dos últimos N meses, inclusive o mês escolhido."""
    periodos = []
    a, m = ano, mes
    for _ in range(meses):
        periodos.append((a, m))
        m -= 1
        if m == 0:
            m = 12
            a -= 1
    periodos.reverse()

    saida = []
    with session_scope() as s:
        for a, m in periodos:
            inicio = date(a, m, 1)
            fim = date(a + 1, 1, 1) if m == 12 else date(a, m + 1, 1)
            filtro_mes = _filtro_mes_competencia(a, m)
            ent = s.scalar(select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                filtro_mes,
                Lancamento.natureza == "ENTRADA",
                Lancamento.status.in_(STATUS_OFICIAIS),
            )) or 0
            sai = s.scalar(select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
                filtro_mes,
                Lancamento.natureza == "SAIDA",
                Lancamento.status.in_(STATUS_OFICIAIS),
            )) or 0
            saida.append({"periodo": f"{m:02d}/{a}", "entradas": float(ent), "saidas": float(sai)})
    return saida


def listar_centros_custo(ativos=True):
    with session_scope() as s:
        q=select(CentroCusto).where(tenant_where(CentroCusto.tesouraria_id)).order_by(CentroCusto.codigo,CentroCusto.nome)
        if ativos:q=q.where(CentroCusto.ativo.is_(True))
        return [{"id":x.id,"codigo":x.codigo,"nome":x.nome,"descricao":x.descricao or "","ativo":x.ativo} for x in s.scalars(q).all()]

def salvar_centro_custo(codigo,nome,descricao=None,centro_id=None,ativo=True,usuario_id=None):
    codigo=(codigo or "").strip().upper(); nome=(nome or "").strip()
    if not codigo or not nome: raise ValueError("Informe código e nome do centro de custo.")
    with session_scope() as s:
        if centro_id:
            x=s.get(CentroCusto,centro_id)
            if not x or x.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Centro de custo não encontrado.")
            ant={"codigo":x.codigo,"nome":x.nome,"ativo":x.ativo}
            x.codigo=codigo;x.nome=nome;x.descricao=descricao;x.ativo=bool(ativo);rid=x.id;acao="ALTERAR_CENTRO_CUSTO"
        else:
            if s.scalar(select(CentroCusto.id).where(CentroCusto.codigo==codigo, tenant_where(CentroCusto.tesouraria_id))): raise ValueError("Código de centro de custo já cadastrado nesta tesouraria.")
            x=CentroCusto(tesouraria_id=get_active_tesouraria_id(),codigo=codigo,nome=nome,descricao=descricao,ativo=bool(ativo));s.add(x);s.flush();rid=x.id;ant=None;acao="CRIAR_CENTRO_CUSTO"
    registrar_auditoria(usuario_id,acao,"centros_custo",rid,ant,{"codigo":codigo,"nome":nome,"ativo":bool(ativo)})
    return rid
