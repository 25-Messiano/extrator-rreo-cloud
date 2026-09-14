from datetime import date
from decimal import Decimal

from database.db import init_db, session_scope
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria
from models.entities import ImportacaoExtrato
from services.financeiro import listar_contas
from services.importacao_extrato import criar_importacao, listar_itens, reprocessar_importacao_com_ia, listar_importacoes
import services.importacao_extrato as impmod


def test_v13_reprocessa_sem_lancar(monkeypatch):
    init_db()
    seed_initial_data(); ensure_default_tesourarias()
    central=next(x for x in listar_tesourarias(None, True) if x["codigo"]=="CENTRAL")
    set_active_tesouraria(central["id"])
    conta=next(x for x in listar_contas() if x['tipo']=='BANCO')
    mov=[{'data':date(2047,1,10),'historico':'PAGAMENTO TESTE IA V13','documento':'ABC','valor':Decimal('44.10'),'natureza':'SAIDA'}]
    iid=criar_importacao('teste_v13.pdf',b'teste-v13',mov,None,'B','2047-01',conta['id'])
    monkeypatch.setattr(impmod,'ia_disponivel',lambda: True)
    monkeypatch.setattr(impmod,'classificar_movimentos',lambda xs:[dict(xs[0],codigo_ia_id=None,favorecido_id=None,favorecido='',especificacao_ia='Pagamento teste IA V13',confianca_ia=0.72,origem_classificacao='OPENAI',justificativa_ia='Sem correspondência segura',modelo_ia='mock-v13')])
    r=reprocessar_importacao_com_ia(iid,None)
    assert r['processados']==1 and r['baixa_confianca']==1
    item=listar_itens(iid)[0]
    assert item['origem_classificacao']=='OPENAI' and item['modelo_ia']=='mock-v13'
    assert item['status'] in ('PENDENTE','CONFERIR_DUPLICIDADE','DUPLICADO_BLOQUEADO')
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,iid)
        assert imp.status=='EM_CONFERENCIA'


def test_v13_arquiva_lote_legado():
    init_db()
    seed_initial_data(); ensure_default_tesourarias()
    central=next(x for x in listar_tesourarias(None, True) if x["codigo"]=="CENTRAL")
    set_active_tesouraria(central["id"])
    with session_scope() as s:
        x=ImportacaoExtrato(nome_arquivo='legado.pdf',tipo_arquivo='PDF',hash_arquivo='legacy-v13',status='EM_CONFERENCIA')
        s.add(x);s.flush();rid=x.id
    init_db()
    assert rid not in [x['id'] for x in listar_importacoes()]
    with session_scope() as s:
        assert s.get(ImportacaoExtrato,rid).status=='ARQUIVADO_TECNICO'
