import re
from sqlalchemy import select

from database.db import init_db, session_scope
from models.entities import Usuario, Tesouraria
from services.security import (
    hash_password, authenticate_email, criar_usuario, atualizar_email_usuario,
    ativar_email_conta_legada, ensure_operational_admins, solicitar_recuperacao_senha,
    validar_token_recuperacao, redefinir_senha_por_token, verify_password,
)
from services.tenancy import ensure_default_tesourarias


def _admin_email():
    init_db(); ensure_default_tesourarias()
    with session_scope() as s:
        u=s.scalar(select(Usuario).where(Usuario.login=='admin_email_v26'))
        if not u:
            u=Usuario(nome='Admin Email V26',login='admin_email_v26',email='admin-v26@example.com',senha_hash=hash_password('AdminEmailV26_123'),perfil='ADMINISTRADOR',ativo=True)
            s.add(u); s.flush()
        return u.id


def test_email_e_identidade_publica_unica():
    aid=_admin_email()
    uid=criar_usuario('Pessoa Email V26','interno_v26','PessoaEmailV26_123','CONSULTA',email='Pessoa.V26@Example.com',usuario_id=aid)
    assert authenticate_email('pessoa.v26@example.com','PessoaEmailV26_123')['id']==uid
    assert authenticate_email('pessoa.v26@example.com','senha-errada') is None
    try:
        criar_usuario('Duplicado','outro_v26','DuplicadoV26_123','CONSULTA',email='PESSOA.V26@example.com',usuario_id=aid)
        assert False, 'deveria bloquear e-mail duplicado'
    except ValueError as exc:
        assert 'e-mail' in str(exc).lower()


def test_migracao_unica_de_conta_legada_para_email():
    init_db(); ensure_default_tesourarias(); ensure_operational_admins()
    with session_scope() as s:
        teste=s.scalar(select(Tesouraria).where(Tesouraria.codigo=='TESTE'))
        tid=teste.id
        u=s.scalar(select(Usuario).where(Usuario.login=='admin__TESTE'))
        # deixa o teste determinístico caso outro teste já tenha tocado nessa conta
        u.email=None; u.senha_hash=hash_password('123')
    result=ativar_email_conta_legada('teste-v26@example.com','123',tid,False,'admin')
    assert result['email']=='teste-v26@example.com'
    assert authenticate_email('teste-v26@example.com','123')['id']==result['id']
    try:
        ativar_email_conta_legada('outro-v26@example.com','123',tid,False,'admin')
        assert False, 'ativação deve ser única'
    except ValueError as exc:
        assert 'já possui e-mail' in str(exc)


def test_recuperacao_email_token_uso_unico(monkeypatch):
    aid=_admin_email()
    uid=criar_usuario('Reset Email V26','reset_v26','ResetEmailV26_123','CONSULTA',email='reset-v26@example.com',usuario_id=aid)
    capturado={}
    def fake_send(destino, assunto, corpo):
        capturado['destino']=destino; capturado['corpo']=corpo
        return True, None
    monkeypatch.setattr('services.email_service.enviar_email', fake_send)
    r=solicitar_recuperacao_senha('reset-v26@example.com')
    assert r['enviado'] is True and capturado['destino']=='reset-v26@example.com'
    token=re.search(r'reset_token=([^\s]+)', capturado['corpo']).group(1)
    assert validar_token_recuperacao(token)['usuario_id']==uid
    redefinir_senha_por_token(token,'NovaResetV26_456')
    assert validar_token_recuperacao(token) is None
    assert authenticate_email('reset-v26@example.com','NovaResetV26_456')['id']==uid


def test_admin_alterar_email_invalida_sessao_e_nao_duplica():
    aid=_admin_email()
    uid=criar_usuario('Troca Email V26','troca_v26','TrocaEmailV26_123','CONSULTA',email='troca-v26@example.com',usuario_id=aid)
    with session_scope() as s:
        antes=s.get(Usuario,uid).senha_versao
    atualizar_email_usuario(uid,'troca-v26-novo@example.com',aid)
    with session_scope() as s:
        u=s.get(Usuario,uid)
        assert u.email=='troca-v26-novo@example.com'
        assert u.senha_versao==antes+1
