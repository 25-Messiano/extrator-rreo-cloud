from sqlalchemy import select

from database.db import init_db, session_scope
from models.entities import Usuario, Tesouraria, UsuarioTesouraria
from services.security import (
    contextos_legados_sem_email,
    hash_password,
    ensure_operational_admins,
    authenticate_email,
)
from services.tenancy import criar_tesouraria_com_admin


def _novo_usuario(nome, login, perfil, email=None):
    with session_scope() as s:
        u = Usuario(
            nome=nome,
            login=login,
            email=email,
            senha_hash=hash_password('SenhaTesteV261_123'),
            perfil=perfil,
            ativo=True,
        )
        s.add(u); s.flush(); return u.id


def test_contexto_migrado_some_da_lista_de_primeiro_acesso():
    init_db()
    with session_scope() as s:
        t=Tesouraria(codigo='MIG-V261',nome='Filial Migrada V261',tipo='FILIADA',ambiente='PRODUCAO',ativa=True)
        s.add(t); s.flush(); tid=t.id
        u=Usuario(nome='Migrado V261',login='migrado_v261',email=None,senha_hash=hash_password('SenhaTesteV261_123'),perfil='TESOURARIA',ativo=True)
        s.add(u); s.flush(); uid=u.id
        s.add(UsuarioTesouraria(usuario_id=uid,tesouraria_id=tid,papel='ADMIN_UNIDADE',ativo=True))
    assert any(x['tid']==tid for x in contextos_legados_sem_email())
    with session_scope() as s:
        s.get(Usuario,uid).email='migrado-v261@example.com'
    assert not any(x['tid']==tid for x in contextos_legados_sem_email())

def test_primeiro_acesso_lista_somente_contexto_pendente():
    init_db()
    with session_scope() as s:
        t=Tesouraria(codigo='LEG-V261',nome='Filial Legada V261',tipo='FILIADA',ambiente='PRODUCAO',ativa=True)
        s.add(t); s.flush(); tid=t.id
        u=Usuario(nome='Legado V261',login='legado_v261',email=None,senha_hash=hash_password('SenhaTesteV261_123'),perfil='TESOURARIA',ativo=True)
        s.add(u); s.flush()
        s.add(UsuarioTesouraria(usuario_id=u.id,tesouraria_id=tid,papel='ADMIN_UNIDADE',ativo=True))
    ctx=contextos_legados_sem_email()
    assert any(x['tid']==tid and 'Filial Legada V261' in x['label'] for x in ctx)


def test_nova_filial_ja_nasce_com_admin_por_email_sem_admin_123():
    init_db()
    tid, uid = criar_tesouraria_com_admin(
        'NOVA-V261','Nova Filial V261','nova-v261@example.com','SenhaNovaV261_123',
        responsavel='Responsável Teste'
    )
    ensure_operational_admins()
    assert authenticate_email('nova-v261@example.com','SenhaNovaV261_123')['id'] == uid
    with session_scope() as s:
        t=s.get(Tesouraria,tid)
        assert t and t.codigo=='NOVA-V261'
        links=s.scalars(select(UsuarioTesouraria).where(UsuarioTesouraria.tesouraria_id==tid,UsuarioTesouraria.ativo.is_(True))).all()
        assert len(links)==1
        usuarios=s.scalars(select(Usuario).where(Usuario.id.in_([x.usuario_id for x in links]))).all()
        assert len(usuarios)==1
        assert usuarios[0].email=='nova-v261@example.com'
        assert not usuarios[0].login.startswith('admin__')
