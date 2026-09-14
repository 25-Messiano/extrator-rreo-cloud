from datetime import date
from decimal import Decimal
from services import ai_extrato

def test_v12_classificacao_mock(monkeypatch):
    monkeypatch.setattr(ai_extrato, '_catalogos', lambda: ([{'id':1,'codigo':'0002','descricao':'COELBA'}],[{'id':9,'codigo':'FOR-000009','nome':'COELBA','tipo':'FORNECEDOR'}]))
    monkeypatch.setattr(ai_extrato, '_response_json', lambda *a, **k: {'classificacoes':[{'indice':0,'codigo_aplb':'0002','favorecido_codigo':'FOR-000009','favorecido_nome':'COELBA','especificacao':'Energia elétrica','confianca':0.98,'justificativa':'Histórico identifica COELBA'}]})
    m=[{'data':date(2026,3,10),'historico':'PAG COELBA','documento':'1','valor':Decimal('100.00'),'natureza':'SAIDA'}]
    r=ai_extrato.classificar_movimentos(m)[0]
    assert r['codigo_ia_id']==1 and r['favorecido_id']==9 and r['confianca_ia']==0.98
    assert r['data']==date(2026,3,10) and r['valor']==Decimal('100.00')
