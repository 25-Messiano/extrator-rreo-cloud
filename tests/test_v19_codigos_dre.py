from database.db import init_db, session_scope
from models.entities import CodigoAPLB, GrupoDRE, GrupoCodigoVinculo
from services.financeiro import (
    salvar_codigo, salvar_grupo, vincular_codigo_grupo, mover_codigo_grupo,
    configurar_codigos_grupo, auditoria_configuracao_dre, definir_codigo_ativo,
)


def _ids(suf='1'):
    init_db()
    c1=salvar_codigo('77'+suf+'1','CODIGO TESTE V19 A '+suf,'SAIDA')
    c2=salvar_codigo('77'+suf+'2','CODIGO TESTE V19 B '+suf,'SAIDA')
    g1=salvar_grupo('9.'+suf+'1','GRUPO TESTE A '+suf,ordem=901)
    g2=salvar_grupo('9.'+suf+'2','GRUPO TESTE B '+suf,ordem=902)
    return c1,c2,g1,g2


def test_um_codigo_um_grupo_e_movimentacao():
    c1,c2,g1,g2=_ids()
    vincular_codigo_grupo(g1,c1)
    try:
        vincular_codigo_grupo(g2,c1)
        assert False, 'deveria bloquear dupla vinculacao'
    except ValueError as exc:
        assert 'já está vinculado' in str(exc)
    mover_codigo_grupo(c1,g2)
    with session_scope() as s:
        ativos=s.query(GrupoCodigoVinculo).filter_by(codigo_aplb_id=c1,ativo=True).all()
        assert len(ativos)==1 and ativos[0].grupo_dre_id==g2


def test_configuracao_multipla_e_inativacao_preserva_catalogo():
    c1,c2,g1,g2=_ids('2')
    configurar_codigos_grupo(g1,[c1,c2])
    diag=auditoria_configuracao_dre()
    assert not diag['duplicados']
    definir_codigo_ativo(c2,False)
    with session_scope() as s:
        cod=s.get(CodigoAPLB,c2)
        assert cod is not None and cod.ativo is False
        assert s.query(GrupoCodigoVinculo).filter_by(codigo_aplb_id=c2,ativo=True).count()==0
