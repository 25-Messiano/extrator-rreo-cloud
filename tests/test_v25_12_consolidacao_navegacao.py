from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def _page_sets():
    tree = ast.parse((ROOT / 'ui' / 'common.py').read_text(encoding='utf-8'))
    found = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in {'CENTRAL_ONLY_PAGES', 'OPERATIONAL_ONLY_PAGES'}:
                found[n.targets[0].id] = set(ast.literal_eval(n.value))
    return found


def test_native_streamlit_navigation_is_disabled():
    cfg = (ROOT / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'showSidebarNavigation = false' in cfg


def test_all_pages_have_explicit_context_except_shared_pages():
    sets = _page_sets()
    central = sets['CENTRAL_ONLY_PAGES']
    operational = sets['OPERATIONAL_ONLY_PAGES']
    all_pages = {p.name for p in (ROOT / 'pages').glob('*.py')}
    shared = {'31_Prestacoes_Contas.py', '35_Minha_Conta.py'}
    assert not (central & operational)
    assert all_pages - central - operational == shared
    assert {'37_Importar_Movimento_PDF.py', '38_Importar_Extratos_PDF.py'} <= operational


def test_central_topbar_uses_authenticated_context_not_title_whitelist():
    src = (ROOT / 'ui' / 'common.py').read_text(encoding='utf-8')
    assert 'ctx=_session_context()' in src
    assert 'if ctx == "CENTRAL"' in src
    assert 'central_titles=' not in src


def test_operational_admin_alias_is_generic_for_future_filiais():
    src = (ROOT / 'services' / 'security.py').read_text(encoding='utf-8')
    assert 'def _tenant_admin_login' in src
    assert 'admin__ARACI_01' not in src
    assert 'admin__TESTE' not in src
    assert 'Tesouraria.tipo != "CENTRAL"' in src


def test_central_admin_is_not_operational_user_of_filiais():
    sec = (ROOT / 'services' / 'security.py').read_text(encoding='utf-8')
    ten = (ROOT / 'services' / 'tenancy.py').read_text(encoding='utf-8')
    assert 'return t.tipo == "CENTRAL"' in sec
    assert 'antigo.ativo = False' in ten
    assert 'Nenhum usuário da CENTRAL é transformado em operador da nova filial' in ten


def test_version_25_13():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() in ('V25.13','V26', 'V26.1', 'V26.2', 'V26.3', 'V26.4', 'V26.5', 'V26.6', 'V26.7', 'V26.8', 'V26.9', 'V26.10')


def test_future_filial_gets_own_operational_admin_alias():
    from services.tenancy import criar_tesouraria, set_active_tesouraria
    from services.security import ensure_operational_admins, authenticate_for_tenant, usuario_pode_acessar_tesouraria
    tid = criar_tesouraria('FUTURA-12', 'Tesouraria Futura 12', cidade='Araci', uf='BA')
    ensure_operational_admins()
    u = authenticate_for_tenant('admin', '123', tid)
    assert u is not None
    assert u['perfil'] == 'TESOURARIA'
    assert u['login'].startswith('admin__FUTURA_12')
    assert usuario_pode_acessar_tesouraria(u['id'], tid) is True
    # Administrador central (id 1 no banco de testes) não recebe acesso operacional à nova filial.
    assert usuario_pode_acessar_tesouraria(1, tid) is False
    set_active_tesouraria(None)
