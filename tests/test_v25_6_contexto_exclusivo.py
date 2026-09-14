from pathlib import Path


def test_common_define_contextos_exclusivos():
    txt = Path('ui/common.py').read_text(encoding='utf-8')
    assert 'CENTRAL_ONLY_PAGES' in txt
    assert 'OPERATIONAL_ONLY_PAGES' in txt
    assert 'Credenciais da Central não entram em perfis operacionais' in txt
    assert 'Trocar usuário' in txt


def test_app_separa_dashboard_central_operacional():
    txt = Path('app.py').read_text(encoding='utf-8')
    assert 'CENTRAL DAS TESOURARIAS' in txt
    assert 'A Central não possui saldo' in txt
    assert 'saldos()' in txt


def test_prestacao_central_nao_envia_como_filial():
    txt = Path('pages/31_Prestacoes_Contas.py').read_text(encoding='utf-8')
    assert 'ten.get("tipo") != "CENTRAL"' in txt
