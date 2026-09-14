from datetime import date
from decimal import Decimal
import pytest
from database.db import init_db, session_scope
from models.entities import ContaFinanceira, CodigoAPLB, Lancamento
from services.financeiro import fechar_mes, reabrir_mes, criar_lancamento, periodo_competencia_fechado
from services.administracao import diagnostico_fechamento


def _base():
    init_db()
    with session_scope() as s:
        conta=s.query(ContaFinanceira).filter(ContaFinanceira.tipo=='BANCO').first()
        if not conta:
            conta=ContaFinanceira(nome='Banco V15',tipo='BANCO',ativo=True);s.add(conta);s.flush()
        cod=s.query(CodigoAPLB).first()
        if not cod:
            cod=CodigoAPLB(codigo='V150',descricao='Teste V15',ativo=True);s.add(cod);s.flush()
        return conta.id,cod.id


def test_v15_fecha_por_competencia_e_reabre_restaurando_status():
    conta,cod=_base()
    with session_scope() as s:
        antigos=s.query(Lancamento).filter(Lancamento.competencia=='2048-05').all()
        for x in antigos:s.delete(x)
    a=criar_lancamento(date(2048,4,30),cod,'B','ENTRADA','V15 entrada',100,conta,competencia='2048-05',status='APROVADO')
    b=criar_lancamento(date(2048,5,2),cod,'B','SAIDA','V15 saida',40,conta,competencia='2048-05',status='CONCILIADO')
    d=diagnostico_fechamento(2048,5)
    assert d['pode_fechar'] is True
    fechar_mes(2048,5,None)
    assert periodo_competencia_fechado('2048-05',date(2048,4,30)) is True
    with session_scope() as s:
        assert s.get(Lancamento,a).status=='FECHADO'
        assert s.get(Lancamento,b).status=='FECHADO'
    with pytest.raises(ValueError):
        criar_lancamento(date(2048,4,29),cod,'B','ENTRADA','bloqueado',1,conta,competencia='2048-05')
    reabrir_mes(2048,5,None,'Teste controlado de reabertura')
    with session_scope() as s:
        assert s.get(Lancamento,a).status=='APROVADO'
        assert s.get(Lancamento,b).status=='CONCILIADO'
