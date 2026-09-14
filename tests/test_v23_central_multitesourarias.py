from datetime import date
from decimal import Decimal

from database.db import init_db
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria, criar_tesouraria
from services.financeiro import listar_lancamentos, listar_codigos, salvar_codigo, criar_lancamento, saldos
from services.prestacoes import criar_prestacao, listar_prestacoes, decidir_prestacao


def _setup():
    init_db(); seed_initial_data(); ensure_default_tesourarias()
    return listar_tesourarias(None, True)


def test_v23_central_e_teste_nascem_separados():
    rows=_setup()
    central=next(x for x in rows if x['codigo']=='CENTRAL')
    teste=next(x for x in rows if x['codigo']=='TESTE')
    assert central['ambiente']=='PRODUCAO'
    assert teste['ambiente']=='TESTE'
    set_active_tesouraria(central['id'])
    assert len(listar_lancamentos(limit=500)) > 0
    set_active_tesouraria(teste['id'])
    assert listar_lancamentos(limit=500) == []
    assert saldos()['GERAL'] == Decimal('0')


def test_v23_lancamento_filiada_nao_vaza_para_central():
    rows=_setup(); central=next(x for x in rows if x['codigo']=='CENTRAL')
    filial_id=criar_tesouraria('FILIAL-TESTE','Filial Teste V23')
    set_active_tesouraria(filial_id)
    codigo_id=salvar_codigo('V231','Codigo Filial V23',permite_saida=True)
    rid=criar_lancamento(date(2047,1,2),codigo_id,'B','SAIDA','Teste isolado V23',Decimal('55.00'),competencia='2047-01')
    assert any(x['id']==rid for x in listar_lancamentos(limit=50))
    set_active_tesouraria(central['id'])
    assert not any(x['id']==rid for x in listar_lancamentos(limit=5000))


def test_v23_prestacao_aprovar_rejeitar_devolver_com_historico():
    rows=_setup()
    filial_id=criar_tesouraria('FILIAL-PC','Filial Prestacao V23')
    set_active_tesouraria(filial_id)
    codigo_id=salvar_codigo('V232','Receita Filial V23',permite_entrada=True,permite_saida=True)
    criar_lancamento(date(2047,2,3),codigo_id,'B','ENTRADA','Receita prestação V23',Decimal('100.00'),competencia='2047-02')
    pid=criar_prestacao(filial_id,'2047-02',None,'Envio inicial')
    p=next(x for x in listar_prestacoes(filial_id) if x['id']==pid)
    assert p['status']=='ENVIADA' and p['entradas']=='100.00'
    decidir_prestacao(pid,'DEVOLVIDA','Corrigir documento comprobatório.',None)
    p=next(x for x in listar_prestacoes(filial_id) if x['id']==pid)
    assert p['status']=='DEVOLVIDA' and 'Corrigir' in p['parecer']
