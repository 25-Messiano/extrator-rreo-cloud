from database.db import init_db, session_scope
from models.entities import Usuario
from services.security import (
    alterar_senha,
    criar_usuario,
    hash_password,
    permitido,
    verify_password,
)
from services.administracao import atualizar_usuario


def _admin():
    init_db()
    with session_scope() as s:
        a=s.query(Usuario).filter(Usuario.login=="admin_v16").first()
        if not a:
            a=Usuario(nome="Admin V16",login="admin_v16",senha_hash=hash_password("AdminV16Seguro123"),perfil="ADMINISTRADOR",ativo=True)
            s.add(a);s.flush()
        return a.id


def test_perfis_e_protecao_ultimo_admin():
    aid=_admin()
    uid=criar_usuario("Consulta V16","consulta_v16","ConsultaV16_123","CONSULTA",email="consulta_v16@example.com",usuario_id=aid)
    assert permitido("", "CONSULTAR", uid)
    assert permitido("", "RELATORIOS", uid)
    assert not permitido("", "LANCAR", uid)
    atualizar_usuario(uid,permissoes=["CONSULTAR","AUDITORIA"],usuario_id=aid)
    assert permitido("", "AUDITORIA", uid)
    assert not permitido("", "RELATORIOS", uid)


def test_senha_redefinida_e_auditavel():
    aid=_admin()
    uid=criar_usuario("Tesouraria V16","tes_v16","TesourariaV16_123","TESOURARIA",email="tes_v16@example.com",usuario_id=aid)
    alterar_senha(uid,"NovaTesourariaV16_456",usuario_id_executor=aid)
    with session_scope() as s:
        u=s.get(Usuario,uid)
        assert verify_password("NovaTesourariaV16_456",u.senha_hash)


def test_nao_remove_ultimo_admin_ativo():
    aid=_admin()
    # Se houver outro admin criado por outro teste/seed, desativa-o para tornar o cenário determinístico.
    with session_scope() as s:
        for u in s.query(Usuario).filter(Usuario.perfil=="ADMINISTRADOR",Usuario.id!=aid).all():
            u.ativo=False
    try:
        atualizar_usuario(aid,perfil="CONSULTA",ativo=True,usuario_id=aid)
        assert False, "deveria bloquear rebaixamento do último administrador"
    except ValueError as exc:
        assert "último Administrador" in str(exc)
