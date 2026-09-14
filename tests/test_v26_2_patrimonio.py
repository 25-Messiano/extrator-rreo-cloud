from datetime import date

from database.db import init_db, session_scope
from models.entities import Tesouraria
from services.tenancy import set_active_tesouraria
from services.financeiro import salvar_codigo, criar_lancamento, listar_patrimonio
from services.administracao import atualizar_patrimonio
from services.patrimonio import (
    listar_aquisicoes_patrimoniais_pendentes,
    cadastrar_de_lancamento,
    listar_para_relatorio,
    relatorio_excel_bytes,
    relatorio_pdf_bytes,
)


def _tenant():
    init_db()
    with session_scope() as s:
        t = s.query(Tesouraria).filter(Tesouraria.codigo == 'PAT-TEST').first()
        if not t:
            t = Tesouraria(codigo='PAT-TEST', nome='Patrimonio Teste', tipo='FILIADA', ambiente='TESTE', ativa=True)
            s.add(t); s.flush()
        tid=t.id
    set_active_tesouraria(tid)
    return tid


def test_codigo_patrimonial_lancamento_e_relatorios():
    _tenant()
    cid = salvar_codigo('9901', 'MATERIAL PERMANENTE TESTE', permite_saida=True, permite_entrada=False, gera_patrimonio=True)
    lid = criar_lancamento(date(2026,9,10), cid, 'B', 'SAIDA', 'Notebook patrimônio', 3500, status='APROVADO', favorecido='Fornecedor X', documento='NF-1')
    pend = listar_aquisicoes_patrimoniais_pendentes()
    assert any(x['lancamento_id'] == lid for x in pend)
    pid = cadastrar_de_lancamento(lid, numero='PAT-9901', descricao='Notebook patrimônio', categoria='Computadores')
    assert not any(x['lancamento_id'] == lid for x in listar_aquisicoes_patrimoniais_pendentes())
    assert any(x['id'] == pid for x in listar_patrimonio())
    assert any(x['Número'] == 'PAT-9901' for x in listar_para_relatorio('EM_USO'))
    atualizar_patrimonio(pid, situacao='OBSOLETO', observacao_movimento='Fim de vida útil')
    assert not any(x['Número'] == 'PAT-9901' for x in listar_para_relatorio('EM_USO'))
    assert any(x['Número'] == 'PAT-9901' for x in listar_para_relatorio('OBSOLETOS'))
    assert len(relatorio_pdf_bytes(listar_para_relatorio('OBSOLETOS'), 'TESTE')) > 1000
    assert len(relatorio_excel_bytes(listar_para_relatorio('OBSOLETOS'))) > 1000
