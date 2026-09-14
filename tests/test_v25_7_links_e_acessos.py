from pathlib import Path


def test_todos_page_links_apontam_para_arquivos_existentes():
    import re
    root=Path(__file__).resolve().parents[1]
    pages={p.name for p in (root/'pages').glob('*.py')}
    refs=[]
    for p in [root/'app.py',root/'ui/common.py']+list((root/'pages').glob('*.py')):
        txt=p.read_text(encoding='utf-8')
        refs += [(p.name,m.group(1)) for m in re.finditer(r'pages/([^"\']+\.py)',txt)]
    missing=[x for x in refs if x[1] not in pages]
    assert missing == []


def test_operational_admins_are_separate(monkeypatch,tmp_path):
    monkeypatch.setenv('DATABASE_URL',f"sqlite:///{tmp_path/'v257.db'}")
    # imports happen after env so settings/db use temp base
    from database.db import init_db, session_scope
    from services.tenancy import ensure_default_tesourarias
    from services.security import ensure_operational_admins, authenticate_for_tenant
    from models.entities import Tesouraria
    from sqlalchemy import select
    init_db(); ensure_default_tesourarias()
    # create Araci because clean test db only has CENTRAL/TESTE
    with session_scope() as s:
        if not s.scalar(select(Tesouraria).where(Tesouraria.codigo=='ARACI-01')):
            s.add(Tesouraria(codigo='ARACI-01',nome='Tesouraria APLB Araci',tipo='FILIADA',ambiente='PRODUCAO',ativa=True))
    ensure_operational_admins()
    with session_scope() as s:
        araci=s.scalar(select(Tesouraria).where(Tesouraria.codigo=='ARACI-01'))
        teste=s.scalar(select(Tesouraria).where(Tesouraria.codigo=='TESTE'))
        aid,tid=araci.id,teste.id
    ua=authenticate_for_tenant('admin','123',aid)
    ut=authenticate_for_tenant('admin','123',tid)
    assert ua and ut
    assert ua['id'] != ut['id']
    assert ua['perfil']=='TESOURARIA' and ut['perfil']=='TESOURARIA'
