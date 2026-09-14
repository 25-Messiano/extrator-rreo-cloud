from datetime import date
from decimal import Decimal

from database.db import init_db, session_scope
from models.entities import CodigoAPLB, Lancamento
from services.financeiro import salvar_codigo, criar_lancamento, codigo_permite_natureza
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria, get_active_tesouraria_id
from relatorios.resumos_oficiais import resumo_codigo_ano


def _setup():
    init_db(); ensure_default_tesourarias(); seed_initial_data(); central=next(x for x in listar_tesourarias(None,True) if x["codigo"]=="CENTRAL"); set_active_tesouraria(central["id"])


def test_codigos_especiais_e_entradas_podem_operar_nas_duas_naturezas():
    _setup()
    with session_scope() as s:
        for codigo in ('0703','0801','0804'):
            c=s.query(CodigoAPLB).filter_by(codigo=codigo, tesouraria_id=get_active_tesouraria_id()).one()
            assert c.permite_entrada is True
            assert c.permite_saida is True


def test_admin_define_saida_sem_entrada_e_permissao_fica_gravada():
    _setup()
    cid=salvar_codigo('V221','TESTE SOMENTE SAIDA',None,permite_entrada=False,permite_saida=True)
    assert codigo_permite_natureza(cid,'SAIDA') is True
    assert codigo_permite_natureza(cid,'ENTRADA') is False
    with session_scope() as s:
        c=s.get(CodigoAPLB,cid)
        assert c.natureza_padrao == 'SAIDA'


def test_mesmo_codigo_pode_aparecer_em_entrada_e_saida_sem_duplicar_valor():
    _setup()
    cid=salvar_codigo('V222','TESTE AMBOS',None,permite_entrada=True,permite_saida=True)
    criar_lancamento(date(2046,2,1),cid,'B','ENTRADA','Entrada V22',Decimal('100.00'),None,competencia='2046-02')
    criar_lancamento(date(2046,2,2),cid,'B','SAIDA','Saida V22',Decimal('40.00'),None,competencia='2046-02')
    d=resumo_codigo_ano(2046,'B')
    ent=next(x for x in d['entradas'] if x['codigo']=='V222')
    sai=next(x for x in d['saidas'] if x['codigo']=='V222')
    assert ent['meses'][2] == Decimal('100.00')
    assert sai['meses'][2] == Decimal('40.00')
    assert d['totais_entrada'][2] == Decimal('100.00')
    assert d['totais_saida'][2] == Decimal('40.00')
    assert d['ok'] is True


def test_estorno_preserva_reversao_mesmo_com_codigo_somente_saida():
    _setup()
    cid=salvar_codigo('V223','TESTE ESTORNO',None,permite_entrada=False,permite_saida=True)
    rid=criar_lancamento(date(2046,3,1),cid,'B','SAIDA','Saida V22 estorno',Decimal('25.00'),None,competencia='2046-03')
    from services.financeiro import estornar_lancamento
    est=estornar_lancamento(rid,None,'teste de reversão')
    with session_scope() as s:
        l=s.get(Lancamento,est)
        assert l.natureza == 'ENTRADA'
        assert l.origem_lancamento == 'ESTORNO'
