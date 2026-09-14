from datetime import date
from decimal import Decimal

from database.db import init_db, session_scope
from models.entities import Usuario, ImportacaoExtrato, ItemConferencia, ContaFinanceira
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria, criar_tesouraria
from services.financeiro import (
    listar_codigos, criar_lancamento, resumo_dashboard, listar_lancamentos,
    salvar_conta, salvar_favorecido, listar_favorecidos, salvar_centro_custo,
    listar_centros_custo, salvar_patrimonio, listar_patrimonio,
)
from services.administracao import listar_saldos_iniciais, monitoramento_resumo
from services.importacao_extrato import listar_importacoes


def _setup():
    init_db(); seed_initial_data(); ensure_default_tesourarias()
    rows=listar_tesourarias(None, True)
    central=next(x for x in rows if x['codigo']=='CENTRAL')
    teste=next(x for x in rows if x['codigo']=='TESTE')
    filial=next((x for x in rows if x['codigo']=='ARACI-X'), None)
    if not filial:
        fid=criar_tesouraria('ARACI-X','Tesouraria APLB Araci X',cidade='ARACI',uf='BA')
        filial=next(x for x in listar_tesourarias(None, True) if x['id']==fid)
    return central,teste,filial


def test_teste_nao_enxerga_dados_da_filial_em_modulos_operacionais():
    _central, teste, filial=_setup()
    codigo=listar_codigos()[0]
    set_active_tesouraria(filial['id'])
    conta=salvar_conta('Banco Araci','BANCO')
    salvar_favorecido('Fornecedor Araci',documento='DOC-ARACI')
    salvar_centro_custo('CC01','Centro Araci')
    salvar_patrimonio('Notebook Araci',numero='PAT-1',valor=1000)
    criar_lancamento(date(2049,1,10),codigo['id'],'B','ENTRADA','Receita exclusiva Araci',Decimal('123.45'),conta_id=conta,competencia='2049-01')

    set_active_tesouraria(teste['id'])
    d=resumo_dashboard(2049,1)
    assert d['saldo_total']==Decimal('0')
    assert d['entradas_mes']==Decimal('0')
    assert d['saidas_mes']==Decimal('0')
    assert d['total_lancamentos_oficiais']==0
    assert d['contas_ativas']==0
    assert d['patrimonio_ativo']==0
    assert listar_lancamentos(limit=100)==[]
    assert listar_favorecidos()==[]
    assert listar_centros_custo()==[]
    assert listar_patrimonio()==[]
    assert listar_saldos_iniciais()==[]
    assert listar_importacoes()==[]
    mon=monitoramento_resumo()
    assert mon['lancamentos_total']==0
    assert mon['lancamentos_oficiais']==0
    assert mon['importacoes_em_conferencia']==0


def test_mesmos_identificadores_podem_existir_em_filiais_diferentes():
    _central, teste, filial=_setup()
    set_active_tesouraria(filial['id'])
    if not any(x['codigo']=='IGUAL' for x in listar_centros_custo(False)):
        salvar_centro_custo('IGUAL','Centro filial')
    set_active_tesouraria(teste['id'])
    salvar_centro_custo('IGUAL','Centro teste')
    assert [x['codigo'] for x in listar_centros_custo(False)].count('IGUAL')==1
