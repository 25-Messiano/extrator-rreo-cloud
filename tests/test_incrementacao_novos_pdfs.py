from core.tipos_rodada import incremental_ja_concluido


def test_incrementacao_reabre_sem_pdf_quando_arquivo_novo_existe():
    row = {"status_rreo": "OK", "status_fnde": "SEM_PDF"}
    assert incremental_ja_concluido(row, True, True, True, False) is True
    assert incremental_ja_concluido(row, True, True, True, True) is False
