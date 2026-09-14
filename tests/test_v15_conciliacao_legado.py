from types import SimpleNamespace
from services.conciliacao import _historico_tecnico, _natureza_extrato
from services.importacao_extrato import _movimento_tecnico, _natureza_por_historico


def test_saldo_espacado_e_tecnico():
    assert _historico_tecnico('0000 00000 999 S A L D O')
    assert _movimento_tecnico({'historico':'0000 00000 999 S A L D O'})


def test_natureza_legada_por_historico():
    assert _natureza_extrato(SimpleNamespace(historico_original='14/01/2026 Transferência enviada 123', natureza='ENTRADA')) == 'SAIDA'
    assert _natureza_extrato(SimpleNamespace(historico_original='13/01/2026 Transferência recebida 123', natureza='ENTRADA')) == 'ENTRADA'
    assert _natureza_por_historico('Pagamento de Boleto 11.401', 'ENTRADA') == 'SAIDA'
