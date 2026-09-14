from datetime import date

from database.db import init_db, session_scope
from models.entities import Patrimonio, PatrimonioMovimento, Tesouraria
from services.tenancy import set_active_tesouraria
from services.patrimonio import listar_movimentacoes_competencia, resumo_movimentacao_competencia


def _setup():
    init_db()
    with session_scope() as s:
        t = s.query(Tesouraria).filter(Tesouraria.codigo == "TESTE-PAT-V264").first()
        if not t:
            t = Tesouraria(codigo="TESTE-PAT-V264", nome="Teste Patrimonio V264", tipo="FILIADA", ambiente="TESTE", ativa=True)
            s.add(t); s.flush()
        tid = t.id
        s.query(PatrimonioMovimento).filter(PatrimonioMovimento.patrimonio_id.in_(s.query(Patrimonio.id).filter(Patrimonio.tesouraria_id==tid))).delete(synchronize_session=False)
        s.query(Patrimonio).filter(Patrimonio.tesouraria_id==tid).delete(synchronize_session=False)
        p = Patrimonio(tesouraria_id=tid, numero_patrimonial="001", descricao="Notebook", categoria="Equipamento", data_aquisicao=date(2026,3,10), valor=1000, situacao="OBSOLETO")
        s.add(p); s.flush()
        s.add(PatrimonioMovimento(patrimonio_id=p.id, tipo="OBSOLESCENCIA", data_movimento=date(2026,9,5), situacao_anterior="ATIVO", situacao_nova="OBSOLETO", observacao="Fim de vida"))
    set_active_tesouraria(tid)
    return tid


def test_aquisicao_aparece_na_competencia_da_data_de_aquisicao():
    _setup()
    rows = listar_movimentacoes_competencia(2026, 3)
    assert any(r["Tipo"] == "AQUISICAO" and r["Número"] == "001" for r in rows)


def test_obsolescencia_aparece_na_competencia_da_movimentacao():
    _setup()
    rows = listar_movimentacoes_competencia(2026, 9)
    assert any(r["Tipo"] == "OBSOLESCENCIA" and r["Situação anterior"] == "ATIVO" and r["Situação nova"] == "OBSOLETO" for r in rows)
    resumo = resumo_movimentacao_competencia(2026, 9)
    assert resumo["tipos"].get("OBSOLESCENCIA") == 1


def test_isolamento_por_tesouraria_na_movimentacao():
    tid = _setup()
    with session_scope() as s:
        outra = s.query(Tesouraria).filter(Tesouraria.codigo == "OUTRA-PAT-V264").first()
        if not outra:
            outra = Tesouraria(codigo="OUTRA-PAT-V264", nome="Outra", tipo="FILIADA", ambiente="TESTE", ativa=True)
            s.add(outra); s.flush()
        s.add(Patrimonio(tesouraria_id=outra.id, numero_patrimonial="999", descricao="Outro bem", data_aquisicao=date(2026,3,1), valor=5, situacao="ATIVO"))
    set_active_tesouraria(tid)
    rows = listar_movimentacoes_competencia(2026,3)
    assert all(r["Número"] != "999" for r in rows)
