from services.tenancy import app_version, listar_tesourarias
from services.security import usuario_pode_acessar_tesouraria


def test_v253_version_and_profiles_exist():
    assert app_version() in ('V25.3', 'V25.4', 'V25.5', 'V25.6', 'V25.7', 'V25.8', 'V25.9', 'V25.10','V25.11','V25.12','V25.13', 'V26', 'V26.1', 'V26.2', 'V26.3', 'V26.4', 'V26.5', 'V26.6', 'V26.7', 'V26.8', 'V26.9', 'V26.10')
    unidades = listar_tesourarias(None)
    codigos = {u['codigo'] for u in unidades}
    assert 'TESTE' in codigos
    assert 'CENTRAL' in codigos


def test_v253_admin_operational_access_hardened_in_v2512():
    # Desde V25.12 o Administrador da Central não opera filiais; troca de perfil é obrigatória.
    unidades = [u for u in listar_tesourarias(None) if u['tipo'] != 'CENTRAL']
    if unidades:
        assert usuario_pode_acessar_tesouraria(1, unidades[0]['id']) is False
