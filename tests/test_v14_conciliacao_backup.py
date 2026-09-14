from datetime import date
from decimal import Decimal
from pathlib import Path

from database.db import init_db, session_scope
from models.entities import ContaFinanceira, CodigoAPLB, Lancamento, ImportacaoExtrato, ItemConferencia
from services.conciliacao import diagnostico_periodo
from services.backup import gerar_backup_completo, validar_backup, testar_restauracao as simular_restauracao
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria


def test_v14_conciliacao_data_natureza_valor(tmp_path):
    init_db()
    ensure_default_tesourarias()
    central=next(x for x in listar_tesourarias(None, True) if x["codigo"]=="CENTRAL")
    set_active_tesouraria(central["id"])
    with session_scope() as s:
        conta=s.query(ContaFinanceira).first()
        if not conta:
            conta=ContaFinanceira(nome='Banco Teste',tipo='BANCO',ativo=True,tesouraria_id=central['id']);s.add(conta);s.flush()
        cod=s.query(CodigoAPLB).first()
        if not cod:
            cod=CodigoAPLB(codigo='T001',descricao='Teste',ativo=True);s.add(cod);s.flush()
        l=Lancamento(data_movimento=date(2049,1,5),competencia='2049-01',codigo_aplb_id=cod.id,origem_bc='B',natureza='ENTRADA',especificacao='Recebimento teste',valor=Decimal('123.45'),conta_financeira_id=conta.id,status='APROVADO',origem_lancamento='TESTE',tesouraria_id=central['id'])
        s.add(l);s.flush()
        imp=ImportacaoExtrato(nome_arquivo='teste.csv',tipo_arquivo='CSV',hash_arquivo='x'*64,competencia='2049-01',conta_financeira_id=conta.id,status='EM_CONFERENCIA',tesouraria_id=central['id'])
        s.add(imp);s.flush()
        s.add(ItemConferencia(importacao_id=imp.id,data_movimento=date(2049,1,5),historico_original='Recebimento teste',valor=Decimal('123.45'),natureza='ENTRADA',origem_bc='B',status='PENDENTE',fingerprint='y'*64))
        conta_id=conta.id
    d=diagnostico_periodo('2049-01',conta_id)
    assert d['conciliaveis'] >= 1
    assert abs(d['totais']['dif_entrada']) < 0.001


def test_v14_backup_integridade_e_simulacao(tmp_path):
    init_db()
    p=gerar_backup_completo(tmp_path)
    assert p.suffix == '.zip'
    v=validar_backup(p)
    assert v['valido'] is True
    r=simular_restauracao(p)
    assert r['sucesso'] is True
    assert r['total_registros'] == v['total_registros']
